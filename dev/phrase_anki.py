import keyboard
import pyperclip
import time
import requests
import re
from pathlib import Path
import sys
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
DECK = config.get("DECK_TASK1", "Review Task 1")
MODEL = config.get("MODEL_TASK1", "IELTS Writing Revise")
HOTKEY = config.get("HOTKEY_TASK1", "ctrl+alt+r")
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
    r = requests.post(ANKI_URL, json=payload)
    res = r.json()
    if res.get("error"):
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

    r = requests.post(
        GEMINI_URL,
        headers=headers,
        json=payload,
        timeout=30
    )

    if r.status_code == 429:
        log("Gemini rate limited, skipping")
        return None

    r.raise_for_status()

    data = r.json()

    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise ValueError(f"Unexpected Gemini response: {data}")


def parse_output(text: str):
    def extract(label):
        m = re.search(rf"{label}:\s*(.+?)(?:\n\n|$)", text, re.S)
        return m.group(1).strip() if m else None

    cloze = extract("Cloze output")
    answer = extract("Answer")
    hint = extract("Hint")

    if not all([cloze, answer, hint]):
        raise ValueError("Gemini output format invalid")

    return {
        "Cloze": cloze,
        "Answer": answer,
        "Definition": hint
    }

def add_note(fields):
    note = {
        "deckName": DECK,
        "modelName": MODEL,
        "fields": fields,
        "tags": ["ielts", "task1"],
        "options": {"allowDuplicate": False}
    }
    anki("addNote", {"note": note})

busy = False

def on_hotkey():
    global busy
    if busy:
        log("Busy, skipping")
        return

    busy = True
    try:
        process_clipboard()
    finally:
        busy = False


def process_clipboard():
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
    add_note(fields)
    log("Added IELTS sentence card")

def log(msg):
    print(f"[AUTO-ANKI] {msg}", flush=True)

def main():
    log("===================================")
    log("Auto Anki – IELTS Task 1 Helper")
    log(f"Hotkey: {HOTKEY}")
    log("Workflow:")
    log("1. Copy sentence (with <target phrase>)")
    log("2. Press hotkey")
    log("3. Card will be added to Anki")
    log("Close this window to stop")
    log("===================================")

    keyboard.add_hotkey(HOTKEY, on_hotkey)
    keyboard.wait()

if __name__ == "__main__":
    main()