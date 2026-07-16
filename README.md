# 📄 pdf2md — PDF / Markdown → Clean Markdown Converter

**pdf2md** คือ CLI tool สำหรับแปลงไฟล์ PDF และ Markdown ให้เป็น Markdown ที่สะอาด พร้อมใช้งานใน pipeline ต่างๆ ไม่ว่าจะส่งให้ LLM, เก็บใน RAG, หรือใช้ใน documentation workflow

พัฒนาโดย **Pao (Builder)** ตาม spec จาก **Lin** โดย **An** review — เป็นส่วนหนึ่งของ Louis Ecosystem

```
pdf2md input.pdf -o output.md --clean --chunk
pdf2md note.md --clean -o ready_for_llm.md
```

---

## 🚀 Installation

### Dependencies

```txt
pdfplumber>=0.10.0
PyMuPDF>=1.23.0
```

### Setup

```bash
# 1. Clone หรือคัดลอกโปรเจคไปที่เครื่อง
#    (โปรเจคอยู่ที่ ~/03-Resources/scripts/pdf-to-md/)

# 2. สร้าง virtual environment (แนะนำ)
python3 -m venv venv
source venv/bin/activate

# 3. ติดตั้ง dependencies
pip install -r requirements.txt

# 4. เพิ่ม alias ใน .zshrc (ทำครั้งเดียว)
#    เพิ่มบรรทัดนี้:
#    pdf2md() { python3 /path/to/pdf-to-md/script.py "$@" }
#
#    หรือใช้ alias ที่มีอยู่แล้ว:
#    pdf2md input.pdf
```

> **หมายเหตุ:** ถ้าใช้ virtual environment ต้อง activate ทุกครั้งก่อนใช้ หรือตั้ง alias ให้ชี้ไปที่ python3 ใน venv โดยตรง

---

## ⚡ Quick Start

### แปลง PDF → Markdown (พื้นฐานที่สุด)

```bash
pdf2md เอกสาร.pdf
```

ผลลัพธ์: ได้ไฟล์ `เอกสาร.md` ใน directory เดียวกัน

### แปลง + ลบหัวกระดาษ/ท้ายกระดาษ + ระบุไฟล์ output

```bash
pdf2md report.pdf --clean -o clean_report.md
```

### แปลง + chunk สำหรับ RAG ingestion

```bash
pdf2md หนังสือ.pdf --clean --chunk --chunk-size 1500
```

### แปลงเฉพาะหน้าที่ต้องการ

```bash
pdf2md เอกสาร.pdf -p 3-7,10,12-15
```

---

## 📖 Usage Guide

### Basic Conversion

```bash
pdf2md input.pdf
```

- Input: PDF หรือ Markdown (`.md`, `.markdown`)
- Output: ไฟล์ `.md` ชื่อเดียวกัน (ถ้า input เป็น `.md` จะเติม `_processed` ต่อท้ายเพื่อป้องกันการทับไฟล์ต้นฉบับ)
- สั่งงานผ่าน alias `pdf2md` หรือ `python3 script.py` หรือ `python -m pdf_to_md`

### `--clean` / `-c` — Clean Mode

ลบ elements ที่ไม่ต้องการออกจาก output:

- **Headers / Running heads** — ข้อความที่ซ้ำกันบริเวณด้านบนของทุกหน้า
- **Footers** — ข้อความที่ซ้ำกันบริเวณด้านล่างของทุกหน้า
- **Page numbers** — เลขหน้าที่เป็นตัวเลขเดี่ยว, `Page N of M`, `- N -`
- **Hyphenation** — ต่อคำที่ถูกตัดครึ่งด้วย hyphen ข้ามบรรทัด
- **Non-printable / Zero-width characters** — กำจัดอักขระที่มองไม่เห็น

```bash
pdf2md หนังสือ.pdf -c
pdf2md หนังสือ.pdf --clean
```

> **กลไก:** `--clean` จะทำ two-pass — รอบแรกสแกนทุกหน้าเพื่อสร้าง profile ของ header/footer (ข้อความที่ซ้ำกัน ≥ 5 หน้า) จากนั้นรอบสองจึงลบออก ส่งผลให้ช้าเล็กน้อย แต่แม่นยำกว่า heuristic ทั่วไป

### `--chunk` — Chunk Mode

แบ่งเนื้อหาออกเป็น chunks ตาม natural break พร้อม metadata:

```bash
pdf2md หนังสือ.pdf --chunk
```

Output จะมีลักษณะ:
```markdown
<!-- chunk-id: 1 -->
<!-- chunk-heading: บทที่ 1 ความรู้เบื้องต้น -->
<!-- chunk-page-range: 1-3 -->
เนื้อหาของ chunk แรก...

<!-- chunk-id: 2 -->
<!-- chunk-heading: 1.1 พื้นฐานที่ควรรู้ -->
<!-- chunk-page-range: 3-5 -->
เนื้อหาของ chunk ที่สอง...
```

**ลำดับความสำคัญในการแบ่ง chunk:**
1. **Headings** (`#`, `##`, ...) — ตัดที่หัวข้อใหม่
2. **Paragraphs** (`\n\n`) — ตัดที่ขึ้นย่อหน้าใหม่
3. **Sentences** (`.!?`) — ตัดที่จบประโยค
4. **Hard cut** — ตัดตามจำนวนตัวอักษร (แทรกคำเตือน)

### `--chunk-size N` — กำหนดขนาด Chunk

```bash
pdf2md หนังสือ.pdf --chunk --chunk-size 1000  # 1000 ตัวอักษรต่อ chunk
pdf2md หนังสือ.pdf --chunk --chunk-size 5000  # 5000 ตัวอักษรต่อ chunk
```

- Default: `2000` ตัวอักษร
- มีผลเมื่อใช้ `--chunk` เท่านั้น
- แต่ละ chunk จะพยายามไม่เกินค่านี้ โดยเลือกตัดที่ natural break ที่ใกล้ที่สุด

### `--fast` — Fast Mode (PyMuPDF-only)

ใช้ PyMuPDF อย่างเดียว ไม่ใช้ pdfplumber:

```bash
pdf2md เอกสาร.pdf --fast
pdf2md เอกสาร.pdf --fast -o fast_output.md
```

| โหมด | ความเร็ว | ตาราง | การตรวจจับหัวข้อ |
|------|---------|-------|-----------------|
| ปกติ (default) | 1x | ✅ GFM tables | ✅ Font-size + heuristic |
| `--fast` | 10–50x เร็วขึ้น | ❌ ไม่มีโครงสร้างตาราง | ✅ Font-size (จาก PyMuPDF dict) |

> **ควรใช้ `--fast` เมื่อ:** ไฟล์ PDF มีเนื้อหาส่วนใหญ่เป็นข้อความ ไม่มีตาราง หรือต้องการความเร็วสูงในการประมวลผลจำนวนมาก

### `-p` / `--pages` — เลือกเฉพาะหน้าที่ต้องการ

```bash
pdf2md เอกสาร.pdf -p 1-5,8,10-12
pdf2md เอกสาร.pdf --pages 3,7,9-11
```

- รูปแบบ: `1-5,8,10-12` (1-based)
- รองรับทั้งช่วง (hyphen) และรายการ (comma)
- Default: ทุกหน้า

### `--table-strategy` — กลยุทธ์การจัดการตาราง

```bash
pdf2md เอกสาร.pdf --table-strategy markdown   # GFM tables (default)
pdf2md เอกสาร.pdf --table-strategy simple      # Tab/comma-separated inline
pdf2md เอกสาร.pdf --table-strategy skip        # ไม่เอา table ออกมา
```

| Strategy | Output | เหมาะกับ |
|----------|--------|---------|
| `markdown` | ตาราง GFM (`\|` pipes) | LLM, GitHub, เหตุผลทั่วไป |
| `simple` | Tab-separated inline | RAG chunking, text processing |
| `skip` | ไม่มีตาราง | เอกสารที่ focus ที่ข้อความอย่างเดียว |

### `--output` / `-o` — กำหนด Path Output

```bash
pdf2md input.pdf -o output.md                          # ระบุชื่อไฟล์
pdf2md input.pdf -o ./output/                          # ระบุ directory
pdf2md input.pdf --output /home/user/clean/result.md   # full path
```

- ถ้าไม่ระบุ: output จะอยู่ที่ directory เดียวกับ input
- ถ้าระบุเป็น directory: จะสร้างไฟล์ชื่อเดียวกับ input ไว้ในนั้น
- ถ้า input เป็น `.md`: default output จะเติม `_processed` เพื่อไม่ให้ทับไฟล์ต้นฉบับ

### `--heading-detection` / `--no-heading` — การตรวจจับหัวข้อ

```bash
pdf2md เอกสาร.pdf                       # detect headings (default)
pdf2md เอกสาร.pdf --no-heading          # output ราบ ไม่มี # 
pdf2md เอกสาร.pdf --heading-detection   # เหมือน default
```

- **`heading-detection`** (default): ตรวจจับ headings จาก font size, all-caps, title case
- **`no-heading`**: output เป็น plain text ทั้งหมด ไม่มี `#` markers — เหมาะกับกรณีที่ Heading detection ทำให้เกิด false positives

### `--preserve-layout` — รักษารูปแบบบรรทัดเดิม

```bash
pdf2md เอกสาร.pdf --preserve-layout
```

- Default: รวมบรรทัดที่ติดกันเป็น paragraph เดียว (เหมาะกับ LLM consumption)
- `--preserve-layout`: คงรูปแบบบรรทัดเดิมจาก PDF (เหมาะกับกรณีต้องรักษา layout ดั้งเดิม)
- เมื่อ input เป็น `.md` อยู่แล้ว ค่านี้จะถูกเปิดให้อัตโนมัติ

### `--verbose` / `-v` — แสดง Log โดยละเอียด

```bash
pdf2md เอกสาร.pdf -v
pdf2md เอกสาร.pdf --verbose --clean --chunk
```

แสดงข้อมูลไปยัง stderr:
```
[pdf_to_md] Input:  เอกสาร.pdf
[pdf_to_md] Output: เอกสาร.md
[pdf_to_md] Pages:  all
[pdf_to_md] Fast:   False
[pdf_to_md] Clean:  True
[pdf_to_md] Table:  markdown
[pdf_to_md] Chunk:  True (size=2000)
[pdf_to_md] Building header/footer profile (first pass)...
[pdf_to_md] Profile: 2 headers, 1 footers, 1 running heads
[pdf_to_md] Body font size: ~11.0pt
[pdf_to_md] Page 1 — 12 elements
[pdf_to_md] Page 2 — 8 elements
[pdf_to_md] Done! 10 pages, 23,456 chars in 1.23s
[pdf_to_md] Output: /home/user/เอกสาร.md
```

### `--version` — แสดงเวอร์ชัน

```bash
pdf2md --version
# pdf_to_md v0.1.0
```

---

## 🔗 Pipeline Examples

### 1. แปลง PDF → ส่ง LLM โดยตรง

```bash
pdf2md งานวิจัย.pdf --clean -o paper.md && cat paper.md | llm -m gemini-2.5-pro
```

### 2. Clean + Chunk สำหรับ RAG Ingestion

```bash
pdf2md คู่มือการใช้งาน.pdf --clean --chunk --chunk-size 1500 -o ./rag_input/
```

ผลลัพธ์: chunks แต่ละ chunk มี `<!-- chunk-heading -->` และ `<!-- chunk-page-range: -->` สำหรับ citation ใน RAG pipeline

### 3. เลือกเฉพาะหน้าที่ต้องการ + Output ไปยัง Directory

```bash
pdf2md หนังสือเรียน.pdf -p 10-50 --clean --chunk -o ./chapters/
```

### 4. Fast Scan เอกสารจำนวนมาก (ไม่สนตาราง)

```bash
for file in ./docs/*.pdf; do
    pdf2md "$file" --fast -o "./md/${file:r}.md"
done
```

### 5. Markdown → Cleaned/Chunked Markdown

```bash
pdf2md draft.md --clean --chunk -o ready_for_llm.md
```

---

## 🏗️ Architecture Overview

### Hybrid Engine

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│  PDF Input  │────▶│  Page Router     │────▶│  Formatter   │
│  or MD File │     │  (per page)      │     │  → Markdown  │
└─────────────┘     └──────────────────┘     └──────────────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │pdfplumber│ │PyMuPDF  │ │  (fallback│
       │(tables)  │ │(text)   │ │   chain)  │
       └──────────┘ └──────────┘ └──────────┘
```

**Core module structure:**

| Module | หน้าที่ |
|--------|--------|
| `cli.py` | รับ arguments, validate, สร้าง namespace |
| `parser.py` | เปิด PDF, hybrid routing (pdfplumber ↔ fitz), page spec parsing, heading detection heuristic |
| `cleaner.py` | ลบ headers/footers/page numbers, rejoin hyphens, normalize unicode |
| `formatter.py` | แปลง PageElements → Markdown string, GFM tables, font-size heading re-classification |
| `chunker.py` | แบ่ง Markdown เป็น chunks (heading → paragraph → sentence → hard cut) |

### Generator Pattern

`parse_pdf()` เป็น **generator function** — yield page elements ทีละหน้า ไม่จำเป็นต้องโหลดเอกสารทั้งหมดเข้า memory:

```python
for page_elements in parse_pdf(pdf_path, pages=page_list):
    page_md = to_markdown(page_elements, ...)
    f.write(page_md)
```

ประโยชน์: เหมาะกับเอกสารขนาดใหญ่ (หลายร้อยหน้า) — ใช้ memory ต่ำ

### Deterministic / No LLM

**pdf2md ทำงานแบบ deterministic ล้วนๆ — ไม่มีการเรียกใช้ AI หรือ LLM ใดๆ** ทุกขั้นตอนใช้ heuristic และ algorithm ที่คาดการณ์ได้: เหมาะสำหรับ pipeline ที่ต้องการ reproducibility

---

## 🔢 Exit Codes

| Code | ความหมาย | สาเหตุที่พบบ่อย |
|------|---------|----------------|
| `0` | ✅ Success | ทำงานเสร็จสมบูรณ์ |
| `1` | ❌ File Error | ไฟล์ input ไม่พบ, ไม่ใช่ไฟล์, หรือนามสกุลไม่รองรับ |
| `2` | ❌ Argument Error | รูปแบบ `--pages` ไม่ถูกต้อง, `--chunk-size` < 1 |
| `3` | ❌ Processing Error | PDF parsing ล้มเหลว, Markdown processing error |
| `4` | ❌ Permission Error | ไม่มีสิทธิ์อ่านไฟล์ input |
| `5` | ❌ Encrypted PDF | PDF มีการป้องกันด้วยรหัสผ่าน — tool นี้ไม่รองรับ |

---

## ⚠️ Security Notes

### Processing Untrusted PDFs
PDF files can contain malicious content. While pdf2md uses well-maintained parsing
libraries, processing PDFs from untrusted sources carries inherent risk.
- **Only process PDFs from sources you trust.**
- Consider running pdf2md in a sandboxed environment (Docker, container) when
  processing documents from external sources.

### Output File Overwrite
By default, pdf2md **silently overwrites** existing output files. Use `-o` with
caution — ensure the output path doesn't point to an important file.

### Invisible Characters
Use `--clean` to strip zero-width spaces, invisible Unicode characters, and
soft hyphens from the output — recommended when output is destined for LLM or
RAG pipelines.

---

## 🔧 Troubleshooting

### "ไม่มีข้อความออกมาเลย / output ว่าง"

สาเหตุที่เป็นไปได้:
- **Scanned PDF** — PDF เป็นภาพ (image-based) ไม่มี text layer → ต้องใช้ OCR ก่อน
  - แนะนำ: ใช้ `ocrmypdf` หรือ OCR tool อื่นแปลงให้มี text layer ก่อน
  - pdf2md จะแสดงคำเตือนถ้าตรวจพบว่า文档เป็น scanned
- **PDF มีการป้องกัน** — ไฟล์ถูกเข้ารหัส → ใช้ `qpdf --decrypt` เพื่อปลดล็อกก่อน

### "ตารางไม่ครบ / แสดงไม่ถูกต้อง"

- ลองเปลี่ยน `--table-strategy` เป็น `simple` หรือ `skip`
- PDF ที่มีตารางซับซ้อน (merged cells, ตารางซ้อนตาราง) อาจต้องใช้วิธีอื่น
- PDF ที่ไม่มีขอบตารางชัดเจน pdfplumber อาจตรวจจับไม่เจอ

### "มีข้อความแปลกๆ หรืออักขระประหลาด"

- ใช้ `--clean` เพื่อลบ non-printable characters
- PDF บางตัวมี Unicode normalization issues — tool จะ normalize เป็น NFC ให้อัตโนมัติ
- ถ้ายังมีปัญหา: ลองแปลงด้วย `pdftotext` (poppler-utils) แล้วใช้ `pdf2md` ในโหมด `.md` input

### "pdf2md: command not found"

- ยังไม่ได้เพิ่ม alias → ตรวจสอบ `.zshrc` หรือเพิ่ม:
  ```zsh
  pdf2md() { python3 /home/lu5her/03-Resources/scripts/pdf-to-md/script.py "$@" }
  ```
- หรือใช้ direct call:
  ```bash
  python3 /home/lu5her/03-Resources/scripts/pdf-to-md/script.py เอกสาร.pdf
  ```

### "ModuleNotFoundError: No module named 'pdfplumber'"

```bash
pip install -r /home/lu5her/03-Resources/scripts/pdf-to-md/requirements.txt
```

หรือถ้าใช้ virtual environment:
```bash
source /home/lu5her/03-Resources/scripts/pdf-to-md/.venv/bin/activate
```

### "ทำงานช้ามาก"

- ใช้ `--fast` เพื่อข้าม pdfplumber — เร็วขึ้น 10–50x (แต่จะไม่มีตาราง)
- `--clean` ทำให้ช้าลงเพราะต้องทำ two-pass
- ถ้าไม่ต้องการ `--clean` หรือ `--chunk` ไม่ต้องใส่ — tool จะทำงาน faster path ทันที

---

> ⚡ Built by **Pao** · Reviewed by **An** · Spec by **Lin** · Part of **Louis Ecosystem**
>
> 📅 v0.1.0 — Deterministic PDF/ Markdown → Clean Markdown Converter
