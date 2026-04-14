"""
ingest.py — معالج ملفات PDF لهيئة نزاهة
يستخرج النصوص، يطبّق تطبيع عربي، ويقسّمها إلى chunks مع تتبع المصدر والصفحة والمادة
الناتج: chunks.json
"""

import fitz  # PyMuPDF
import json
import re
import os
import sys
from pathlib import Path

# ─── تطبيع النص العربي ────────────────────────────────────────────────────────
def normalize_arabic(text: str) -> str:
    """تطبيع شامل للنص العربي للبحث الدقيق"""
    # إزالة التشكيل والحركات
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)
    # تطبيع أشكال الألف (أ إ آ ٱ أ) → ا
    text = re.sub(r'[أإآٱ\u0622\u0623\u0625\u0671]', 'ا', text)
    # تطبيع التاء المربوطة ة → ه
    text = re.sub(r'ة', 'ه', text)
    # تطبيع الألف المقصورة ى → ي
    text = re.sub(r'ى', 'ي', text)
    # إزالة التطويل (ـ)
    text = re.sub(r'ـ', '', text)
    # تنظيف المسافات المتعددة
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ─── أنماط اكتشاف الأقسام ────────────────────────────────────────────────────
SECTION_PATTERNS = [
    re.compile(r'(الباب\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|\d+))'),
    re.compile(r'(الفصل\s+(?:الأول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|\d+))'),
    re.compile(r'(المادة\s+\(?(?:\d+)\)?)'),
    re.compile(r'(مادة\s+\(?(?:\d+)\)?)'),
    re.compile(r'(أولاً|ثانياً|ثالثاً|رابعاً|خامساً|سادساً|سابعاً|ثامناً|تاسعاً|عاشراً)'),
]

def detect_section(text: str) -> str:
    """استخراج أقرب عنوان قسم أو مادة من مقطع نصي"""
    for pattern in SECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return ""


# ─── استخراج النص من PDF ─────────────────────────────────────────────────────
def extract_pages(pdf_path: str) -> list[dict]:
    """استخراج قائمة {page, text} من ملف PDF"""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc, start=1):
        text = page.get_text("text")
        text = re.sub(r'\n{3,}', '\n\n', text)  # تنظيف أسطر فارغة كثيرة
        text = text.strip()
        if text:
            pages.append({"page": i, "text": text})
    doc.close()
    return pages


# ─── تقسيم إلى chunks ────────────────────────────────────────────────────────
CHUNK_SIZE_WORDS = 450      # عدد الكلمات التقريبي للـ chunk
OVERLAP_WORDS    = 60       # overlap بين الـ chunks

def split_into_chunks(pages: list[dict], source: str) -> list[dict]:
    """تقسيم صفحات PDF إلى chunks مع تتبع الصفحة والقسم"""
    chunks = []
    chunk_id = 0

    # دمج كل الصفحات في stream واحد مع تتبع الصفحات
    words_buffer = []   # (word, page_num)
    for p in pages:
        for word in p["text"].split():
            words_buffer.append((word, p["page"]))

    i = 0
    current_section = ""
    while i < len(words_buffer):
        # أخذ chunk بحجم CHUNK_SIZE_WORDS كلمة
        window = words_buffer[i: i + CHUNK_SIZE_WORDS]
        if not window:
            break

        chunk_words  = [w for w, _ in window]
        chunk_text   = " ".join(chunk_words)
        page_start   = window[0][1]
        page_end     = window[-1][1]

        # اكتشاف القسم داخل هذا الـ chunk
        detected = detect_section(chunk_text)
        if detected:
            current_section = detected

        chunks.append({
            "id": chunk_id,
            "text": chunk_text,
            "normalized_text": normalize_arabic(chunk_text),
            "source": source,
            "page": page_start,
            "page_end": page_end,
            "section": current_section,
        })

        chunk_id += 1
        i += CHUNK_SIZE_WORDS - OVERLAP_WORDS  # تحريك بـ step = size - overlap

    return chunks


# ─── الدالة الرئيسية ─────────────────────────────────────────────────────────
SOURCE_LABELS = {
    "Nazaha Law no 2 of 2016 - FINAL (AR).pdf": "قانون هيئة مكافحة الفساد رقم 2 لسنة 2016",
    "مرسوم تعديل قانون هيئة مكافحة الفساد.pdf": "مرسوم تعديل قانون هيئة مكافحة الفساد",
    "مرسوم-رقم-300-لسنة-2016-بإصدار-الائحة-التنفيذية-للهيئة.pdf": "اللائحة التنفيذية لهيئة مكافحة الفساد - المرسوم 300/2016",
}

def main():
    output     = Path("chunks.json")
    all_chunks = []

    # دعم: python ingest.py file1.pdf file2.pdf ... أو مجلد
    args = sys.argv[1:]
    pdf_files = []

    if not args:
        # بحث في مجلد pdfs/ افتراضياً
        pdf_files = list(Path("pdfs").glob("*.pdf"))
    else:
        for arg in args:
            p = Path(arg)
            if p.is_file() and p.suffix.lower() == ".pdf":
                pdf_files.append(p)
            elif p.is_dir():
                pdf_files.extend(p.glob("*.pdf"))

    if not pdf_files:
        print("❌ لم يتم العثور على ملفات PDF")
        sys.exit(1)

    for pdf_path in pdf_files:
        filename = pdf_path.name
        label    = SOURCE_LABELS.get(filename, filename.replace(".pdf", ""))
        print(f"📄 معالجة: {label}")

        pages  = extract_pages(str(pdf_path))
        chunks = split_into_chunks(pages, label)
        all_chunks.extend(chunks)
        print(f"   ✅ {len(pages)} صفحة → {len(chunks)} chunk")

    # إعادة ترقيم IDs
    for idx, chunk in enumerate(all_chunks):
        chunk["id"] = idx

    output.write_text(json.dumps(all_chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n✅ تم الحفظ: {output} ({len(all_chunks)} chunk إجمالاً)")


if __name__ == "__main__":
    main()
