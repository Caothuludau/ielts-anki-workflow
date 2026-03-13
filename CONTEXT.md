# Project context: auto-anki-ielts

## What this project is

This repo is a small Windows-focused automation tool that creates Anki cards from your clipboard using global hotkeys.

It supports two main workflows:

- **Vocabulary cards (Cambridge Dictionary)**: copy a word/short phrase → press a hotkey → scrape Cambridge (IPA/definition/examples/synonyms) + optionally fetch an illustration image from Bing Images → add a note to Anki via AnkiConnect.
- **IELTS writing revision cards (Gemini)**: copy a sentence containing a target phrase wrapped in `<...>` → press a hotkey → call Gemini with a strict prompt → parse the model output into fields → optionally attach an image → add a cloze-style revision note to Anki via AnkiConnect.

The codebase is currently **script-driven** (no package/module layout): the primary logic lives in a few Python files under `dev/`.

## Repository entry points

- `dev/vocab_anki.py`
  - Runs a background hotkey listener (default `ctrl+alt+a`).
  - On trigger: reads clipboard, scrapes Cambridge, searches Bing Images, stores the image into Anki media (AnkiConnect `storeMediaFile`), then adds a note (AnkiConnect `addNote`).
  - Uses an inline cloze generation for the `Word` field (masking characters).

- `dev/phrase_anki.py`
  - Runs a background hotkey listener for IELTS writing revision:
    - Task 1 hotkey (default `ctrl+alt+r`)
    - Task 2 hotkey (default `ctrl+alt+t`)
  - On trigger: reads clipboard (must contain `<...>`), loads `prompt.txt`, calls Gemini, parses labeled sections, optionally fetches an image from Bing Images, then adds a note via AnkiConnect.

- `dev/exam.py`
  - Minimal test script that tries a hard-coded `addNote` request to confirm AnkiConnect is reachable and that deck/model exist.

## How the Anki integration works

Both main scripts talk to **AnkiConnect** at `ANKI_URL` (default `http://127.0.0.1:8765`) by POSTing JSON like:

- `findNotes` (used in `dev/vocab_anki.py` to avoid duplicates for a `Word`)
- `storeMediaFile` (used in `dev/vocab_anki.py` to save downloaded image bytes into Anki’s media folder)
- `addNote` (used by both to create the card)

This means:

- Anki must be running.
- The AnkiConnect add-on must be installed/enabled.
- The specified deck/model and field names must exist in your Anki collection.

## Configuration

Configuration is read from a local file next to where you run the script/exe:

- **Config file**: `auto_anki_config.txt`
- **Loaded by**: `dev/vocab_anki.py` and `dev/phrase_anki.py`

Key config keys used by `dev/vocab_anki.py`:

- `ANKI_URL`
- `DECK`, `MODEL`
- `HOTKEY`
- `ALLOW_DUPLICATE` (controls AnkiConnect `allowDuplicate`)

Key config keys used by `dev/phrase_anki.py`:

- `ANKI_URL`
- `DECK_TASK1`, `MODEL_TASK1`, `HOTKEY_TASK1`
- `DECK_TASK2`, `MODEL_TASK2`, `HOTKEY_TASK2`
- `GEMINI_API_KEY` (required)
- `GEMINI_URL` (defaults to `gemini-2.0-flash:generateContent`)
- `PROMPT_FILE` (path to `prompt.txt`)

An example config currently exists at `dev/auto_anki_config.txt`.

## Gemini prompt and output contract (IELTS workflow)

- **Prompt template**: `dev/prompt.txt`
  - The code substitutes `{{INPUT}}` with the clipboard text.
  - The prompt enforces strict formatting and rules (e.g., replace only the marked phrase with `___`, Vietnamese hint constraints).

- **Parser**: `parse_output()` in `dev/phrase_anki.py`
  - Expects labeled sections:
    - `Sentence:`
    - `Cloze:`
    - `Answer:`
    - `Hint:`
    - optional `Image:`
  - If any required section is missing, the script raises an error and logs the raw output.

## Web scraping / image fetching

- **Cambridge** (vocab workflow): `dev/vocab_anki.py` uses BeautifulSoup selectors to extract:
  - IPA (UK) from `.ipa.dipa`
  - definition from `.def.ddef_d.db`
  - example sentences from `.examp.dexamp` (first 3)
  - synonyms from `.xref.syn`

- **Bing Images** (both workflows):
  - Searches Bing Images and extracts candidate URLs from `a.iusc` elements (JSON in attribute `m`) and/or regex fallbacks.
  - Downloads candidate images and only accepts responses with `Content-Type: image/*`.
  - For vocab, images are stored in Anki media via `storeMediaFile` and inserted as `<img src="...">`.
  - For IELTS, the script can attach image bytes using the `picture` field in the `addNote` payload (AnkiConnect supports this).

## Dependencies (inferred from imports)

There isn’t a pinned dependency file in the repo root right now (no `requirements.txt` found). From the scripts, you likely need:

- `requests`
- `pyperclip`
- `keyboard`
- `beautifulsoup4`
- an HTML parser such as `lxml` (used by BeautifulSoup in both scripts)

Plus:

- Windows (for global hotkeys as used here)
- Anki + AnkiConnect add-on
- Gemini API key for the IELTS workflow

## Build / distribution

There are PyInstaller spec files:

- `vocab_anki.spec` and `phrase_anki.spec` (repo root)
- plus spec files under `dev/` (`dev/vocab_anki.spec`, etc.)

They build one-file console executables that point at the `dev/*.py` scripts.

## Operational notes / gotchas

- The scripts assume **Anki field names** exactly match what they send (e.g., vocab uses fields like `Word`, `Cloze`, `Phonetic symbol`, `Extra information`, `Synonyms`, `Image`).
- `dev/phrase_anki.py` includes two `log()` function definitions; the second one overrides the first (so timestamped logging is used).
- `dev/vocab_anki.py` checks duplicates by querying `Word:"{word}"`. Depending on your model/query semantics, you may need to adjust if duplicates slip through.
- Scrapers rely on Cambridge/Bing HTML structure, which can change.

