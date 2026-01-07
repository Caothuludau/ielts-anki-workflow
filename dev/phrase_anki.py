import keyboard
import pyperclip
import time
import requests
import re
from pathlib import Path
import sys
import base64
import os
from urllib.parse import quote_plus
import traceback
from datetime import datetime
import json
from bs4 import BeautifulSoup
# ================= CONFIG =================

sys.stdout.reconfigure(encoding="utf-8")
CONFIG_FILE = Path("./auto_anki_config.txt")
def load_config():
    if not CONFIG_FILE.exists():
        print("auto_anki_config.txt not found")
        input("Press Enter to exit...")
        exit(1)

    config = {}
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
# Task 1 defaults
DECK_TASK1 = config.get("DECK_TASK1", "Review Task 1")
MODEL_TASK1 = config.get("MODEL_TASK1", "IELTS Writing Revise")
HOTKEY_TASK1 = config.get("HOTKEY_TASK1", "ctrl+alt+r")
# Task 2 defaults
DECK_TASK2 = config.get("DECK_TASK2", "Review Task 2")
MODEL_TASK2 = config.get("MODEL_TASK2", "IELTS Writing Task 2")
HOTKEY_TASK2 = config.get("HOTKEY_TASK2", "ctrl+alt+t")
GEMINI_URL = config.get(
    "GEMINI_URL",
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
)
GEMINI_API_KEY = config.get("GEMINI_API_KEY", "")
PROMPT_FILE = Path(config.get("PROMPT_FILE", "./prompt.txt"))

if not GEMINI_API_KEY:
    print("GEMINI_API_KEY not set in auto_anki_config.txt")
    input("Press Enter to exit...")
    exit(1)

# ==========================================

def anki(action, params=None):
    payload = {
        "action": action,
        "version": 6,
        "params": params or {}
    }
    try:
        log(f"ANKI request action={action} params_keys={list((params or {}).keys())}")
        r = requests.post(ANKI_URL, json=payload, timeout=15)
    except Exception as e:
        log(f"ANKI request failed: {e}", level="ERROR")
        log_exception(e)
        raise

    try:
        res = r.json()
    except Exception as e:
        log(f"ANKI returned non-JSON (status {r.status_code})", level="ERROR")
        log(f"Response text (truncated): {r.text[:1000]}")
        raise

    log(f"ANKI response error={res.get('error') is not None}")
    if res.get("error"):
        log(f"ANKI error detail: {res.get('error')}", level="ERROR")
        raise Exception(res["error"])
    return res["result"]


def load_prompt(user_input: str) -> str:
    base = PROMPT_FILE.read_text(encoding="utf-8")
    return base.replace("{{INPUT}}", user_input)


def call_gemini(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "X-goog-api-key": GEMINI_API_KEY
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

    try:
        log(f"Calling Gemini (prompt length={len(prompt)})")
        r = requests.post(
            GEMINI_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
    except Exception as e:
        log(f"Gemini request failed: {e}", level="ERROR")
        log_exception(e)
        raise

    if r.status_code == 429:
        log("Gemini rate limited (429), skipping", level="WARN")
        return None

    try:
        r.raise_for_status()
    except Exception as e:
        log(f"Gemini returned status {r.status_code}", level="ERROR")
        log(f"Gemini response text (truncated): {r.text[:2000]}")
        raise

    data = r.json()
    log(f"Gemini response keys: {list(data.keys())}")

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        log("Unexpected Gemini response structure", level="ERROR")
        log(f"Full response (truncated): {str(data)[:2000]}")
        raise ValueError(f"Unexpected Gemini response: {data}") from e


def parse_output(text: str):
    def extract(label):
        m = re.search(rf"{label}:\s*(.+?)(?:\n\n|$)", text, re.S)
        return m.group(1).strip() if m else None

    sentence = extract("Sentence")
    cloze = extract("Cloze")
    answer = extract("Answer")
    hint = extract("Hint")
    image_label = extract("Image")

    # Sentence, Cloze, Answer, Hint are required
    if not all([sentence, cloze, answer, hint]):
        log("parse_output: missing one of Sentence/Cloze/Answer/Hint", level="ERROR")
        log(f"Gemini raw output (truncated): {str(text)[:2000]}")
        raise ValueError("Gemini output invalid: missing Sentence/Cloze/Answer/Hint")

    return {
        "Sentence": sentence,
        "Cloze": cloze,
        "Answer": answer,
        "Definition": hint,
        "Image": image_label or ""
    }


def fetch_image_for_phrase(phrase: str, max_retries: int = 10):
    """Search Bing Images for `phrase` and return (filename, bytes) or (None, None).
    Attempts up to `max_retries` distinct image URLs found on the search page.
    """
    if not phrase:
        return None, None

    query = quote_plus(phrase)
    search_url = f"https://www.bing.com/images/search?q={query}&form=HDRSC2"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        log(f"Searching images for phrase: {phrase}")
        log(f"Image search URL: {search_url}")
        r = requests.get(search_url, headers=headers, timeout=10)
        r.raise_for_status()
    except Exception:
        log(f"Image search failed for {phrase}", level="WARN")
        return None, None

    # First try parsing page anchors with class 'iusc' (contains JSON with murl)
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
        # if BeautifulSoup fails, fall back to regex
        pass

    # Fallback: regex search for murl
    if not candidates:
        matches = re.findall(r'"murl":"(https?://[^"]+)"', r.text)
        if matches:
            candidates.extend(matches)
        else:
            matches2 = re.findall(r'murl&gt;&quot;:&quot;(https?://[^&]+)&', r.text)
            if matches2:
                candidates.extend(matches2)

    # dedupe while preserving order
    seen = set()
    matches = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            matches.append(u)

    log(f"Found {len(matches)} candidate image URLs")

    tried = 0
    for img_url in matches:
        if tried >= max_retries:
            break
        tried += 1
        log(f"Trying image #{tried}: {img_url}")
        try:
            ir = requests.get(img_url, headers=headers, timeout=10)
            if ir.status_code == 200:
                ctype = ir.headers.get("Content-Type", "")
                log(f"Image response content-type: {ctype}")
                if ctype.startswith("image") and ir.content:
                    # try to compute extension
                    ext = ".jpg"
                    if "png" in ctype:
                        ext = ".png"
                    elif "gif" in ctype:
                        ext = ".gif"
                    # safe filename
                    safe_name = re.sub(r"[^0-9A-Za-z._-]", "_", phrase)[:60]
                    filename = f"{safe_name}{ext}"
                    return filename, ir.content
        except Exception:
            log(f"Failed to fetch image URL: {img_url}", level="DEBUG")
            continue

    return None, None

def add_note(fields):
    # default to task1 deck/model unless overridden in fields (caller will pass correct deck/model)
    deck = fields.pop("_deck", DECK_TASK1)
    model = fields.pop("_model", MODEL_TASK1)
    log(f"Adding note: deck={deck} model={model} image_present={'_image_bytes' in fields}")

    note = {
        "deckName": deck,
        "modelName": model,
        "fields": {
            "Sentence": fields.get("Sentence", ""),
            "Cloze": fields.get("Cloze", ""),
            "Answer": fields.get("Answer", ""),
            "Definition": fields.get("Definition", ""),
            "Image": fields.get("Image", "")
        },
        "tags": ["ielts"],
        "options": {"allowDuplicate": False}
    }

    # If image bytes were provided, include them for Anki to save and insert into the Image field
    image_bytes = fields.get("_image_bytes")
    image_filename = fields.get("_image_filename")
    if image_bytes and image_filename:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        note["picture"] = [{
            "filename": image_filename,
            "data": b64,
            "fields": ["Image"]
        }]
    try:
        anki("addNote", {"note": note})
        log(f"add_note: success for deck={deck} model={model}")
    except Exception as e:
        log(f"add_note: failed to add note to Anki: {e}", level="ERROR")
        log_exception(e)
        raise

busy = False

def on_hotkey():
    # kept for backward compatibility (no-arg hotkey)
    on_hotkey_for_task(1)


def on_hotkey_for_task(task: int = 1):
    global busy
    if busy:
        log("Busy, skipping")
        return

    busy = True
    try:
        process_clipboard(task)
    finally:
        busy = False


def process_clipboard(task: int = 1):
    time.sleep(1.5)
    text = pyperclip.paste().strip()

    if "<" not in text or ">" not in text:
        log("Input must contain <target phrase>")
        return

    prompt = load_prompt(text)
    result = call_gemini(prompt)

    if not result:
        return  # stop here, no retry

    fields = parse_output(result)

    # determine deck/model based on task
    if task == 1:
        fields["_deck"] = DECK_TASK1
        fields["_model"] = MODEL_TASK1
        fields["tags"] = ["task1", "ielts"]
    else:
        fields["_deck"] = DECK_TASK2
        fields["_model"] = MODEL_TASK2
        fields["tags"] = ["task2", "ielts"]

    # Try to fetch an illustration: prefer explicit Image label, else use Answer
    image_search = fields.get("Image") or fields.get("Answer")
    filename, img_bytes = fetch_image_for_phrase(image_search, max_retries=10)
    if filename and img_bytes:
        # insert HTML tag into Image field and pass bytes for attachment
        fields["Image"] = f"<img src=\"{filename}\">"
        fields["_image_bytes"] = img_bytes
        fields["_image_filename"] = filename

    # capture deck name before add_note pops it
    deck_name = fields.get("_deck")
    add_note(fields)
    log(f"Added IELTS sentence card to {deck_name}")

def log(msg):
    print(f"[AUTO-ANKI] {msg}", flush=True)


def log(msg, level="INFO"):
    print(f"[AUTO-ANKI] {datetime.now().isoformat()} {level}: {msg}", flush=True)


def log_exception(e: Exception):
    tb = traceback.format_exc()
    print(f"[AUTO-ANKI] {datetime.now().isoformat()} ERROR: {e}\n{tb}", flush=True)

def main():
    log("===================================")
    log("Auto Anki – IELTS Writing Helper")
    log(f"Hotkey Task1: {HOTKEY_TASK1}")
    log(f"Hotkey Task2: {HOTKEY_TASK2}")
    log("Workflow:")
    log("1. Copy sentence (with <target phrase>)")
    log("2. Press hotkey")
    log("3. Card will be added to Anki")
    log("Close this window to stop")
    log("===================================")

    # register both task hotkeys
    keyboard.add_hotkey(HOTKEY_TASK1, lambda: on_hotkey_for_task(1))
    keyboard.add_hotkey(HOTKEY_TASK2, lambda: on_hotkey_for_task(2))
    keyboard.wait()

if __name__ == "__main__":
    main()