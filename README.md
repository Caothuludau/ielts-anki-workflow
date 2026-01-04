# auto-anki-ielts

Automate creating high-quality Anki cards for English vocabulary and IELTS Writing sentences.

This tool lets you:
- Copy a word or phrase → press a hotkey → Anki card is created automatically
- Turn IELTS sentences into cloze-deletion revision cards using Gemini
- Avoid repetitive manual Anki work and focus on actual learning

---

## ✨ Features

### 1️⃣ Vocabulary from Cambridge Dictionary
- Copy an English word or short phrase
- Press a hotkey
- Automatically:
  - Fetch IPA (UK)
  - Definition
  - Example sentences
  - Synonyms
  - Generate a smart cloze
  - Add everything to Anki

### 2️⃣ IELTS Writing Sentence Revision
- Copy a sentence with a target phrase marked using `< >`
- Press a hotkey
- The tool:
  - Calls Gemini (free tier)
  - Generates:
    - Cloze sentence
    - Full answer
    - Short Vietnamese hint
  - Adds a revision card to Anki
---

## ⚙️ Requirements
- Windows
- Anki (running)
- AnkiConnect add-on
- Internet connection
- Gemini API key (free tier is enough)

---

## 🛠️ Setup

### 1️⃣ Install AnkiConnect
- Anki → Tools → Add-ons → Get Add-ons
- Code: `2055492159`

### 2️⃣ Prepare config file

Create `auto_anki_config.txt` next to the executable:

```ini
ANKI_URL=http://127.0.0.1:8765

# Vocabulary feature
DECK=Open Source English
MODEL=Open Source
HOTKEY=ctrl+alt+a

# IELTS feature
DECK_TASK1=Review
MODEL_TASK1=IELTS Writing Revise
HOTKEY_TASK1=ctrl+alt+r

# Gemini
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent
PROMPT_FILE=prompt.txt
```

🚀 Usage
  **Vocabulary**
  1. Copy an English word
  2. Press Ctrl + Alt + A
  3. Card is added to Anki

**IELTS Writing**
  1. Copy a sentence with <target phrase>
  2. Press Ctrl + Alt + R
  3. Cloze revision card is added

📦 Build from Source
  ```ini
  python -m PyInstaller --onefile --console auto_anki.py
  ```
  The executable will be in the dist/ folder.

⚠️ Notes
  Hotkeys require the app to be running
  Some antivirus software may flag the .exe (false positive)
  Cambridge Dictionary HTML may change in the future

❤️ Final Words
  This is not a startup.
  This is not a SaaS.
  It’s a small tool built to remove unnecessary friction from serious language learning.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![Anki](https://img.shields.io/badge/anki-required-orange)
