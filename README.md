> Note: This README was drafted with the assistance of AI. The content accurately reflects the tool’s functionality. I plan to rewrite and refine this documentation manually in the future.
# auto-anki-ielts-flashcard

**auto-anki-ielts-flashcard** là công cụ giúp **tự động tạo flashcard Anki chất lượng cao** cho việc học từ vựng tiếng Anh và luyện IELTS Writing, nhằm loại bỏ các thao tác thủ công lặp đi lặp lại khi học.

Thay vì:
- Tra từ
- Copy IPA
- Viết definition
- Tạo cloze
- Dán vào Anki

Bạn chỉ cần:
> **Copy nội dung → nhấn hotkey → card được tạo tự động trong Anki**

Tool được thiết kế để **không phá flow học**, ưu tiên tốc độ và tính nhất quán hơn là giao diện.

---

## 🎯 Mục tiêu của công cụ

- Giảm tối đa thời gian tạo flashcard thủ công
- Giữ người học tập trung vào **việc học**, không phải nhập liệu
- Tạo card theo cấu trúc ổn định, phù hợp cho học dài hạn
- Tối ưu cho người luyện **IELTS Writing** và học từ vựng học thuật

---

## ✨ Tính năng chính

### 1️⃣ Tạo flashcard từ vựng (Vocabulary)

Dùng khi học **từ đơn hoặc cụm từ ngắn**.

**Cách dùng:**
1. Copy một từ tiếng Anh
2. Nhấn hotkey đã cấu hình
3. Card được tạo tự động trong Anki

**Tool sẽ tự động:**
- Lấy phiên âm IPA (UK)
- Lấy definition
- Lấy ví dụ
- Lấy synonyms
- Tạo cloze phù hợp
- Đưa toàn bộ vào Anki theo Card Type đã định nghĩa

Phù hợp cho:
- Từ vựng học thuật
- Từ mới khi đọc báo, sách, essay
- Học từ rời nhưng vẫn có ngữ cảnh

---

### 2️⃣ Ôn tập câu IELTS Writing (Sentence Revision)

Dùng khi học **từ hoặc cụm từ trong ngữ cảnh câu**.

**Cách dùng:**
1. Đặt từ/cụm từ cần học trong dấu `< >`
2. Copy toàn bộ câu
3. Nhấn hotkey tương ứng

**Ví dụ:**
```

Some people argue that shops should be permitted to sell food and beverages that are <scientifically proven> to be harmful to human health.

```

**Tool sẽ:**
- Gọi Gemini (free tier)
- Sinh:
  - Câu cloze
  - Đáp án đầy đủ
  - Gợi ý nghĩa ngắn bằng tiếng Việt
- Tạo flashcard dạng điền từ (type-in) trong Anki

Phù hợp cho:
- IELTS Writing Task 1 & Task 2
- Collocations
- Cụm từ học thuật theo ngữ cảnh thật

---

## ⚙️ Yêu cầu hệ thống

- Windows
- Anki (đang chạy)
- AnkiConnect add-on
- Kết nối Internet
- Gemini API key (free tier là đủ)

---

## 🛠️ Cài đặt

### 1️⃣ Cài AnkiConnect

- Mở Anki
- Tools → Add-ons → Get Add-ons
- Nhập mã: `2055492159`
- Khởi động lại Anki

---

### 2️⃣ Chuẩn bị file cấu hình

Tạo file `auto_anki_config.txt` **cùng thư mục với file .exe**:

```ini
ANKI_URL=http://127.0.0.1:8765

# Vocabulary
DECK=Open Source English
MODEL=Open Source
HOTKEY=ctrl+alt+a
ALLOW_DUPLICATE=true

# Vocab source + multilingual
VOCAB_SOURCE=hybrid
PHRASE_MAX_WORDS_CAMBRIDGE=5
SOURCE_LANG=en
TARGET_LANGS=vi,ja

# Gemini (used for IELTS and for vocab when needed)
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_URL=https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent

# Prompt templates
PROMPT_FILE=prompt.txt
VOCAB_PROMPT_FILE=vocab_prompt.txt

# IELTS Writing
DECK_TASK1=Review
MODEL_TASK1=IELTS Writing Revise
HOTKEY_TASK1=ctrl+alt+r
```

---

**Lưu ý:**

* Tên Deck và Model **phải trùng tuyệt đối** với Anki
* Sai chữ hoa/thường sẽ khiến tool không hoạt động

---

## 🚀 Cách sử dụng

### Vocabulary

1. Copy một từ tiếng Anh
2. Nhấn `Ctrl + Alt + A`
3. Flashcard được thêm vào Anki

---

### IELTS Writing

1. Copy câu có `<từ hoặc cụm từ>`
2. Nhấn `Ctrl + Alt + R`
3. Card cloze được tạo tự động

---

## 📦 Build từ source

```bash
powershell -ExecutionPolicy Bypass -File .\install_python.ps1
python -m pip install PyInstaller   
powershell -ExecutionPolicy Bypass -File .\build_local.ps1

```

File `.exe` sẽ nằm trong thư mục `dist/`.

---

## ⚠️ Lưu ý

* Tool phải đang chạy thì hotkey mới hoạt động
* Một số antivirus có thể cảnh báo file `.exe` (false positive)
* HTML của Cambridge Dictionary có thể thay đổi trong tương lai
![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-windows-lightgrey)
![Anki](https://img.shields.io/badge/anki-required-orange)
