from pathlib import Path
import time
import requests
import pyperclip
import keyboard
import re
import hashlib
import json
import base64
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
import sys
import traceback
from datetime import datetime

CONFIG_FILE = Path("./auto_anki_config.txt")
sys.stdout.reconfigure(encoding="utf-8")

if not CONFIG_FILE.exists():
    print("auto_anki_config.txt not found " + str(CONFIG_FILE))
    input("Press Enter to exit...")
    exit(1)

config = {}

def load_config():
    for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        config[k.strip()] = v.strip()
    return config

config = load_config()

ANKI_URL = config.get("ANKI_URL", "http://127.0.0.1:8765")
DECK = config.get("DECK", "Default")
MODEL = config.get("MODEL", "Basic")
HOTKEY = config.get("HOTKEY", "ctrl+alt+a")
ALLOW_DUPLICATE = config.get("ALLOW_DUPLICATE", "true").lower() == "true"

# ---------- Vocab (Gemini + languages) ----------
VOCAB_SOURCE = config.get("VOCAB_SOURCE", "hybrid").strip().lower()  # cambridge|gemini|hybrid
PHRASE_MAX_WORDS_CAMBRIDGE = int(config.get("PHRASE_MAX_WORDS_CAMBRIDGE", "5"))
SOURCE_LANG = config.get("SOURCE_LANG", "en").strip().lower()
TARGET_LANGS = [x.strip() for x in config.get("TARGET_LANGS", "vi").split(",") if x.strip()]

VOCAB_GEMINI_URL = (config.get("VOCAB_GEMINI_URL") or config.get(
    "GEMINI_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
)).strip()
VOCAB_GEMINI_API_KEY = (config.get("VOCAB_GEMINI_API_KEY") or config.get("GEMINI_API_KEY", "")).strip()
VOCAB_PROMPT_FILE = Path(config.get("VOCAB_PROMPT_FILE", "./vocab_prompt.txt"))


# ---------- Anki ----------
def anki(action, params=None):
    payload = {
        "action": action,
        "version": 6,
        "params": params or {}
    }
    r = requests.post(ANKI_URL, json=payload)
    r.raise_for_status()
    res = r.json()
    if res.get("error"):
        raise Exception(f"AnkiConnect error: {res['error']}")
    return res["result"]


def note_exists(word):
    query = f'Word:"{word}"'
    return len(anki("findNotes", {"query": query})) > 0


def add_note(data):
    word = data["word"].strip()
    cloze = make_cloze(word)
    tags = data.get("tags") or ["vocab"]

    note = {
        "deckName": DECK,
        "modelName": MODEL,
        "fields": {
            "Word": word,
            "Cloze": cloze,
            "Phonetic symbol": data.get("ipa", ""),
            "Audio": "",
            "Definition": data.get("definition", ""),
            "Extra information": data.get("examples", ""),
            "Synonyms": data.get("synonyms", ""),
            "Image": data.get("image", "")
        },
        "tags": tags,
        "options": {
            "allowDuplicate": ALLOW_DUPLICATE
        }
    }

    anki("addNote", {"note": note})

def make_cloze(text: str) -> str:
    parts = text.split()
    return " ".join(make_cloze_word(p) for p in parts)

def make_cloze_word(word):
    if len(word) <= 3:
        return "_" * len(word)
    if len(word) <= 5:
        return word[0] + "_" * (len(word) - 1)
    return word[0] + "_" * (len(word) - 2) + word[-1]


# ---------- Cambridge ----------
def fetch_cambridge(word):
    url = f"https://dictionary.cambridge.org/dictionary/english/{word.replace(' ', '-')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None

    soup = BeautifulSoup(r.text, "lxml")

    # IPA (UK)
    ipa = ""
    ipa_tag = soup.select_one(".ipa.dipa")
    if ipa_tag:
        ipa = ipa_tag.text.strip()

    # Definition
    definition = ""
    def_tag = soup.select_one(".def.ddef_d.db")
    if def_tag:
        definition = def_tag.text.strip()

    # Examples
    examples = []
    for ex in soup.select(".examp.dexamp"):
        examples.append(ex.text.strip())
    examples = "\n".join(examples[:3])

    # Synonyms
    synonyms = []
    for syn in soup.select(".xref.syn"):
        synonyms.append(syn.text.strip())
    synonyms = ", ".join(set(synonyms))

    return {
        "ipa": ipa,
        "definition": definition,
        "examples": examples,
        "synonyms": synonyms
    }


# ---------- Gemini (vocab/phrase) ----------
def load_vocab_prompt(user_input: str, target_langs: list[str]) -> str:
    prompt_path = VOCAB_PROMPT_FILE
    if not prompt_path.is_absolute():
        prompt_path = Path.cwd() / prompt_path
    base = prompt_path.read_text(encoding="utf-8")
    return (base
            .replace("{{INPUT}}", user_input)
            .replace("{{TARGET_LANGS}}", ",".join(target_langs)))


def call_vocab_gemini(prompt: str) -> str | None:
    if not VOCAB_GEMINI_API_KEY:
        return None

    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": VOCAB_GEMINI_API_KEY
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    r = requests.post(VOCAB_GEMINI_URL, headers=headers, json=payload, timeout=30)

    if r.status_code == 429:
        log("Gemini rate limited (429), skipping", level="WARN")
        return None

    r.raise_for_status()
    data = r.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response: {str(data)[:2000]}") from e


def parse_vocab_output(text: str, target_langs: list[str]):
    raw = text.strip()

    # strip markdown fences if Gemini wrapped the JSON
    if raw.startswith("```"):
        # try to find the first '{' and last '}'
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]

    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Gemini vocab JSON parse failed: {e}; raw={raw[:500]}") from e

    term = (obj.get("term") or "").strip()
    ipa = (obj.get("ipa_uk") or "").strip()
    definition_en = (obj.get("definition_en") or "").strip()

    if not definition_en:
        raise ValueError("Gemini output invalid: missing definition_en")

    translations_obj = obj.get("translations") or {}
    if not isinstance(translations_obj, dict):
        translations_obj = {}

    # keep only requested languages (if provided)
    if target_langs:
        wanted = set(target_langs)
        translations = {k: v for k, v in translations_obj.items() if k in wanted}
    else:
        translations = translations_obj

    examples_list = obj.get("examples_en") or []
    if not isinstance(examples_list, list):
        examples_list = []
    examples = "\n".join([str(ln).strip() for ln in examples_list if str(ln).strip()])

    synonyms_list = obj.get("synonyms") or []
    if isinstance(synonyms_list, list):
        synonyms = ", ".join([str(s).strip() for s in synonyms_list if str(s).strip()])
    else:
        synonyms = str(synonyms_list).strip()

    visual_query = (obj.get("visualSearchQuery") or "").strip()

    return {
        "term": term,
        "ipa": ipa,
        "definition_en": definition_en,
        "translations": translations,
        "examples": examples,
        "synonyms": synonyms,
        "image_query": visual_query
    }


def format_definition_with_translations(definition_en: str, translations: dict) -> str:
    definition_en = (definition_en or "").strip()
    if not translations:
        return definition_en
    lines = [definition_en, "", "Translations:"]
    for code, val in translations.items():
        lines.append(f"- {code}: {val}")
    return "\n".join(lines).strip()


# ---------- Bing Image Fetcher ----------
def fetch_image_bing(search_query: str):
    """Return a list of candidate image URLs from Bing Images for `search_query`.

    This collects `murl` values from `a.iusc` JSON blobs and falls back to
    regex extraction. The caller should attempt downloads and retry.
    """
    query = requests.utils.quote(search_query)
    url = (
        f"https://www.bing.com/images/search?"
        f"q={query}&form=HDRSC2&mkt=en-US&setLang=en"
    )

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        log(f"Searching images for: {search_query}")
        log(f"Image search URL: {url}")
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log(f"Image search failed: {e}", level="WARN")
        log_exception(e)
        return []

    candidates = []
    try:
        soup = BeautifulSoup(r.text, "lxml")
        for a in soup.select("a.iusc"):
            m_attr = a.get("m")
            if not m_attr:
                continue
            try:
                data = json.loads(m_attr)
                murl = data.get("murl") or data.get("turl")
                if murl:
                    candidates.append(murl)
            except Exception:
                continue
    except Exception:
        pass

    if not candidates:
        matches = re.findall(r'"murl":"(https?://[^\"]+)"', r.text)
        if matches:
            candidates.extend(matches)
        else:
            matches2 = re.findall(r'murl&gt;&quot;:&quot;(https?://[^&]+)&', r.text)
            if matches2:
                candidates.extend(matches2)

    # dedupe while preserving order
    seen = set()
    out = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            out.append(u)

    log(f"Found {len(out)} candidate image URLs")
    return out


def add_image_to_anki(word, image_urls, max_retries: int = 10):
    """Try to download image(s) from `image_urls` and store the first valid
    image in Anki media. `image_urls` may be a single URL or an iterable.

    Tries up to `max_retries` candidate URLs and logs each attempt.
    """
    if not image_urls:
        return ""

    if isinstance(image_urls, str):
        candidates = [image_urls]
    else:
        candidates = list(image_urls)

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    tried = 0
    for img_url in candidates:
        if tried >= max_retries:
            break
        tried += 1
        log(f"Trying image #{tried}: {img_url}")
        try:
            r = requests.get(img_url, headers=headers, timeout=10)
            if r.status_code != 200:
                log(f"Image URL returned status {r.status_code}", level="DEBUG")
                continue

            ctype = r.headers.get("Content-Type", "")
            log(f"Image response content-type: {ctype}")
            if not ctype.startswith("image") or not r.content:
                log("Not an image or empty response", level="DEBUG")
                continue

            # Try to determine extension from URL path
            path = urlparse(img_url).path
            if path:
                ext = unquote(path).split('.')[-1].split('?')[0]
            else:
                ext = ''

            if not ext or '/' in ext or len(ext) > 5:
                # derive from content-type
                if "png" in ctype:
                    ext = 'png'
                elif "gif" in ctype:
                    ext = 'gif'
                else:
                    ext = 'jpg'

            filename = f"{hashlib.md5(word.encode()).hexdigest()}.{ext}"
            b64 = base64.b64encode(r.content).decode('ascii')

            anki("storeMediaFile", {
                "filename": filename,
                "data": b64
            })

            log(f"Stored media as {filename}")
            return f'<img src="{filename}">'

        except Exception as e:
            log(f"Failed to download/store image: {e}", level="DEBUG")
            log_exception(e)
            continue

    log("No valid image found after retries", level="WARN")
    return ""

# ---------- Hotkey ----------
def on_hotkey():
    try:
        raw = pyperclip.paste().strip()
        word = raw.lower()
        word_count = len([p for p in word.split() if p.strip()])

        if not word or word_count > 30:
            log("Clipboard không phải từ / phrase hợp lệ")
            return

        if note_exists(word):
            log(f"Đã tồn tại: {word}")
            return

        use_gemini = False
        if VOCAB_SOURCE == "gemini":
            use_gemini = True
        elif VOCAB_SOURCE == "hybrid" and word_count > PHRASE_MAX_WORDS_CAMBRIDGE:
            use_gemini = True

        data = None
        tags = []

        if not use_gemini and VOCAB_SOURCE in ("cambridge", "hybrid"):
            log(f"Đang crawl Cambridge: {word}")
            data = fetch_cambridge(word)
            tags.append("cambridge")

        gemini_payload = None
        if use_gemini or not data or not data.get("definition"):
            log("Đang gọi Gemini cho vocab/phrase...")
            prompt = load_vocab_prompt(raw, TARGET_LANGS)
            gemini_text = call_vocab_gemini(prompt)
            if gemini_text:
                gemini_payload = parse_vocab_output(gemini_text, TARGET_LANGS)
                tags.append("gemini")

        if not data:
            data = {"ipa": "", "definition": "", "examples": "", "synonyms": ""}

        # Merge Gemini into Cambridge (prefer Cambridge IPA if present; prefer Cambridge definition if present)
        if gemini_payload:
            merged_definition_en = data.get("definition") or gemini_payload.get("definition_en", "")
            merged_definition = format_definition_with_translations(
                merged_definition_en,
                gemini_payload.get("translations", {})
            )
            data["definition"] = merged_definition
            if not data.get("ipa"):
                data["ipa"] = gemini_payload.get("ipa", "")
            if not data.get("examples"):
                data["examples"] = gemini_payload.get("examples", "")
            if not data.get("synonyms"):
                data["synonyms"] = gemini_payload.get("synonyms", "")

        if not data or not data["definition"]:
            log("Không lấy được dữ liệu vocab")
            return
        
        log(f"Đang tìm ảnh minh họa...")
        image_query = word
        if gemini_payload and gemini_payload.get("image_query"):
            image_query = gemini_payload["image_query"]

        # Bias image search toward conceptual, photo-like images and away from text-heavy assets
        bing_query = f"{image_query} -text -poster -dictionary -document -quote -typography"

        candidates = fetch_image_bing(bing_query)
        image_html = ""

        if candidates:
            image_html = add_image_to_anki(word, candidates, max_retries=10)

        log(f"IMAGE HTML: {image_html}")
        add_note({
            "word": word,
            "image": image_html,
            "tags": list(dict.fromkeys(["vocab"] + tags)),
            **data
        })

        log(f"Đã add thật sự: {word}")

    except Exception as e:
        log(f"Lỗi: {e}", level="ERROR")
        log_exception(e)


def main():
    log("===================================")
    log("Auto Anki Vocab Helper")
    log(f"Hotkey: {HOTKEY}")
    log("Copy word -> press hotkey")
    log("Close this window to stop")
    log("===================================")  

    keyboard.add_hotkey(HOTKEY, on_hotkey)
    keyboard.wait()

def log(msg, level="INFO"):
    print(f"[AUTO-ANKI] {datetime.now().isoformat()} {level}: {msg}", flush=True)


def log_exception(e: Exception):
    tb = traceback.format_exc()
    print(f"[AUTO-ANKI] {datetime.now().isoformat()} ERROR: {e}\n{tb}", flush=True)

if __name__ == "__main__":
    main()
