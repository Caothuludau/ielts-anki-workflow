# auto-anki-ielts

Automate creating high-quality Anki cards for English vocabulary and IELTS Writing Task 1 sentences.

This tool lets you:
- Copy a word or phrase → press a hotkey → Anki card is created automatically
- Turn IELTS Task 1 sentences into cloze-deletion revision cards using Gemini
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

### 2️⃣ IELTS Writing Task 1 Sentence Revision
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

## 🧠 Why This Exists

Creating Anki cards manually is:
- Slow
- Repetitive
- Mentally draining

This project exists to:
- Reduce friction
- Enforce consistent card quality
- Let you spend time *thinking*, not formatting

Built by someone who actually uses Anki daily.

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

# IELTS Task 1 feature
DECK_TASK1=Review Task 1
MODEL_TASK1=IELTS Writing Revise
HOTKEY_TASK1=ctrl+alt+r

# Gemini
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent
PROMPT_FILE=prompt.txt
🚀 Usage
Vocabulary
Copy an English word

Press Ctrl + Alt + A

Card is added to Anki

IELTS Task 1
Copy a sentence with <target phrase>

Press Ctrl + Alt + R

Cloze revision card is added

📦 Build from Source
bash
Copy code
python -m PyInstaller --onefile --console auto_anki.py
The executable will be in the dist/ folder.

⚠️ Notes
Hotkeys require the app to be running

Some antivirus software may flag the .exe (false positive)

Cambridge Dictionary HTML may change in the future

📜 License
MIT License.
Use it, modify it, break it, improve it.

❤️ Final Words
This is not a startup.
This is not a SaaS.

It’s a small tool built to remove unnecessary friction from serious language learning.

yaml
Copy code

---

## 4️⃣ DECOR NHẸ NHÀNG (KHÔNG LỐ)

Nếu muốn nhìn repo “xịn” hơn một tí:

### Badges (tuỳ chọn)

```markdown
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![Anki](https://img.shields.io/badge/anki-required-orange)
