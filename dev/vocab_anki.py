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
        "tags": ["cambridge"],
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

# ---------- Bing Image Fetcher ----------
def fetch_image_bing(word):
    """Return a list of candidate image URLs from Bing Images for `word`.

    This collects `murl` values from `a.iusc` JSON blobs and falls back to
    regex extraction. The caller should attempt downloads and retry.
    """
    query = requests.utils.quote(word)
    url = f"https://www.bing.com/images/search?q={query}&form=HDRSC2"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    try:
        log(f"Searching images for: {word}")
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
        word = pyperclip.paste().strip().lower()

        if not word or " " in word and len(word.split()) > 5:
            log("Clipboard không phải từ / phrase hợp lệ")
            return

        if note_exists(word):
            log(f"Đã tồn tại: {word}")
            return

        log(f"Đang crawl Cambridge: {word}")
        data = fetch_cambridge(word)

        if not data or not data["definition"]:
            log("Không lấy được dữ liệu Cambridge")
            return
        
        log(f"Đang tìm ảnh minh họa...")
        candidates = fetch_image_bing(word)
        image_html = ""

        if candidates:
            image_html = add_image_to_anki(word, candidates, max_retries=10)

        log(f"IMAGE HTML: {image_html}")
        add_note({
            "word": word,
            "image": image_html,
            **data
        })

        log(f"Đã add thật sự: {word}")

    except Exception as e:
        log(f"Lỗi: {e}")


def main():
    log("===================================")
    log("Auto Anki Cambridge Helper")
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
