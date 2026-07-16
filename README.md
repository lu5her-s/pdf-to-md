# 📄 pdf2md
### PDF & Markdown to Clean Markdown CLI Converter
---

**pdf2md** is an elite, deterministic CLI tool designed to transform PDF documents and raw Markdown files into clean, ready-to-use Markdown. Whether you are building an LLM pipeline, a RAG system, or professional documentation, **pdf2md** delivers high-fidelity output without the unpredictability of AI.

**pdf2md** คือเครื่องมือ CLI ระดับพรีเมียมสำหรับการแปลงไฟล์ PDF และ Markdown ให้เป็น Markdown ที่สะอาดและพร้อมใช้งาน ถูกออกแบบมาเพื่อรองรับการทำงานใน Pipeline สมัยใหม่ ไม่ว่าจะเป็นการเตรียมข้อมูลสำหรับ LLM, ระบบ RAG หรือการทำเอกสารทางเทคนิค โดยเน้นความแม่นยำแบบ Deterministic ที่คาดเดาได้ 100% โดยไม่ต้องพึ่งพา AI

---

## ⚡ Quick Start | เริ่มต้นใช้งานด่วน

### Basic Conversion | การแปลงไฟล์พื้นฐาน

Convert a PDF to Markdown with standard settings.
แปลงไฟล์ PDF เป็น Markdown ด้วยค่าเริ่มต้น

```bash
pdf2md document.pdf
```
*Output: `document.md`*

### Premium Cleaning | การทำความสะอาดเนื้อหาขั้นสูง

Remove artifacts such as headers, footers, and page numbers.
ลบส่วนเกินที่ไม่จำเป็น เช่น หัวกระดาษ ท้ายกระดาษ และเลขหน้า

```bash
pdf2md report.pdf --clean
```
*Output: `report_cleaned.md`*

---

## 🛠️ Installation | การติดตั้ง

### Prerequisites | สิ่งที่ต้องเตรียม
- Python 3.8+
- PyMuPDF (fitz)
- pdfplumber

### Setup | ขั้นตอนการตั้งค่า
1. Clone the repository to your local machine.
   คัดลอกโปรเจคไปยังเครื่องของคุณ
2. Install the required dependencies.
   ติดตั้ง Dependencies ที่จำเป็น
   ```bash
   pip install -r requirements.txt
   ```
3. (Recommended) Create an alias in your `.zshrc` or `.bashrc`.
   (แนะนำ) สร้าง Alias ในไฟล์ Config ของ Shell
   ```bash
   alias pdf2md='python3 /path/to/pdf-to-md/script.py'
   ```

---

## 📖 Usage & Logic | การใช้งานและหลักการทำงาน

### Smart Suffix Behavior | ระบบการตั้งชื่อไฟล์อัตโนมัติ

**pdf2md** intelligently handles output filenames to prevent accidental overwrites.
**pdf2md** มีระบบจัดการชื่อไฟล์เอาต์พุตที่ชาญฉลาดเพื่อป้องกันการเขียนทับไฟล์ต้นฉบับโดยไม่ตั้งใจ

| Input Type | Flag | Default Output Name |
| :--- | :--- | :--- |
| **PDF** | *None* | `filename.md` |
| **PDF** | `--clean` | `filename_cleaned.md` |
| **Markdown** | *None* | `filename_processed.md` |
| **Markdown** | `--clean` | `filename_cleaned.md` |

---

## 🚩 Flags & Options | คำสั่งและตัวเลือกเพิ่มเติม

| Flag | Purpose | รายละเอียด |
| :--- | :--- | :--- |
| `-c`, `--clean` | Artifact removal | ลบหัว/ท้ายกระดาษ และเลขหน้า |
| `--chunk` | Split by natural breaks | แบ่งเนื้อหาเป็นส่วนๆ (Chunks) สำหรับ RAG |
| `--chunk-size N` | Max chunk length | กำหนดจำนวนอักขระสูงสุดต่อหนึ่ง Chunk |
| `-p`, `--pages` | Page selection | เลือกเฉพาะหน้าที่ต้องการ (เช่น 1-5,10) |
| `--fast` | High-speed mode | เน้นความเร็ว (ข้ามการประมวลผลตาราง) |
| `--table-strategy` | Table formatting | เลือกรูปแบบตาราง (markdown, simple, skip) |
| `-o`, `--output` | Define output path | กำหนดเส้นทางไฟล์เอาต์พุต |
| `-v`, `--verbose` | Detailed logging | แสดงรายละเอียดการทำงานทีละขั้นตอน |

---

## 🏗️ Architecture | โครงสร้างสถาปัตยกรรม

The engine follows a strict deterministic pipeline to ensure maximum reliability for production environments.
ระบบประมวลผลผ่าน Pipeline ที่ออกแบบมาอย่างเข้มงวด เพื่อความเสถียรสูงสุดในการใช้งานจริง

1. **Parser**: Hybrid engine combining **pdfplumber** (for tables) and **PyMuPDF** (for high-speed text extraction).
2. **Cleaner**: Two-pass algorithm that profiles recurring headers/footers before removal.
3. **Formatter**: Logic-based conversion that restores document hierarchy and headings.
4. **Chunker**: Semantic-aware splitter that respects headings and paragraph boundaries.

---

## 📝 Examples | ตัวอย่างการใช้งาน

### Research Paper for LLM | เตรียมงานวิจัยสำหรับส่งให้ LLM
```bash
pdf2md paper.pdf --clean --output paper_ready.md
```

### Knowledge Base Ingestion | การเตรียมข้อมูลสำหรับระบบ Knowledge Base
```bash
pdf2md manual.pdf --clean --chunk --chunk-size 1500
```

---

## 🔧 Troubleshooting | การแก้ไขปัญหา

- **Empty Output?**: Ensure the PDF is text-based and not a scanned image. Use OCR tools first if needed.
  **ไฟล์ว่าง?**: ตรวจสอบว่า PDF มี Text Layer หรือไม่ หากเป็นไฟล์จากการสแกน ควรใช้เครื่องมือ OCR ก่อน
- **Permission Denied?**: Check your write permissions for the target directory.
  **สิทธิ์ไม่เพียงพอ?**: ตรวจสอบสิทธิ์ในการเขียนไฟล์ใน Directory เป้าหมาย

---

Built by **Pao** · Reviewed by **An** · Spec by **Lin** · Part of **Louis Ecosystem**
v0.1.0
