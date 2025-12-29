from pathlib import Path
import time
import requests
import pyperclip
import keyboard
from bs4 import BeautifulSoup
import sys

CONFIG_FILE = Path("./auto_anki_config.txt")
sys.stdout.reconfigure(encoding="utf-8")

if not CONFIG_FILE.exists():
    print("auto_anki_config.txt not found")
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
            "Synonyms": data.get("synonyms", "")
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

        add_note({
            "word": word,
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

def log(msg):
    print(f"[AUTO-ANKI] {msg}", flush=True)

if __name__ == "__main__":
    main()
