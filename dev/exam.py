import requests

ANKI_URL = "http://127.0.0.1:8765"
DECK = "Open Source English"
MODEL = "Open Source"

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

def main():
    print("Đang test addNote vào Anki...")

    result = anki("addNote", {
        "note": {
            "deckName": DECK,
            "modelName": MODEL,
            "fields": {
                "Word": "testword",
                "Cloze": "te__d",
                "Phonetic symbol": "",
                "Audio": "",
                "Definition": "This is a test definition",
                "Extra information": "This is extra info",
                "Synonyms": "test, trial"
            },
            "tags": ["debug"]
        }
    })

    print("KẾT QUẢ:", result)
    print("Nếu không có exception thì card đã được add thật sự.")

if __name__ == "__main__":
    main()
