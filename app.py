"""
app.py — خادم Flask لمستشار نزاهة
BM25 search + Claude API SSE streaming
"""

import json
import os
import re
import traceback

import anthropic
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS
from rank_bm25 import BM25Okapi

app = Flask(__name__)
CORS(app)

# ─── تطبيع النص العربي ────────────────────────────────────────────────────────
def normalize_arabic(text: str) -> str:
    text = re.sub(r'[\u064B-\u065F\u0670]', '', text)   # إزالة التشكيل
    text = re.sub(r'[أإآٱ\u0622\u0623\u0625\u0671]', 'ا', text)  # توحيد الألف
    text = re.sub(r'ة', 'ه', text)                       # التاء المربوطة
    text = re.sub(r'ى', 'ي', text)                       # الألف المقصورة
    text = re.sub(r'ـ', '', text)                        # التطويل
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ─── تحميل الـ Index ──────────────────────────────────────────────────────────
CHUNKS: list[dict] = []
BM25_INDEX = None

def load_index():
    global CHUNKS, BM25_INDEX
    chunks_path = os.path.join(os.path.dirname(__file__), "chunks.json")
    with open(chunks_path, "r", encoding="utf-8") as f:
        CHUNKS = json.load(f)
    corpus = [c["normalized_text"].split() for c in CHUNKS]
    BM25_INDEX = BM25Okapi(corpus)
    print(f"✅ Index محمّل: {len(CHUNKS)} chunk من {len(set(c['source'] for c in CHUNKS))} مصدر")

load_index()


# ─── BiDi تصحيح تشفير الخط ────────────────────────────────────────────────────
# بعض الوثائق تستخدم خط mylotus/Lotus-Light الذي يخزّن أزواج الحروف بترتيب معكوس
# هذه القائمة تحوّل الاستعلام الصحيح إلى الشكل المخزّن في الفهرس
_BIDI_SWAPS = [
    ('في',  'يف'),   # حرف الجر "في" → يف
    ('تج',  'جت'),   # ت+ج (تجاوز → جتاوز)
    ('تح',  'حت'),   # ت+ح (تحت → حتت)
    ('لم',  'مل'),   # ل+م (المرور → امـلرور)
    ('لج',  'جل'),   # ل+ج (الجلسة → اجللسة)
    ('لح',  'حل'),   # ل+ح (الحمراء → احلمراء)
    ('لد',  'دل'),   # ل+د (الحد → احلد via لح+د)
    ('سر',  'رس'),   # س+ر (السرعة → الرسعة)
    ('صى',  'ىص'),   # ص+ى (الأقصى → الاقىص)
]

def garble_for_bidi(text: str) -> str:
    """تحويل النص العربي الصحيح إلى الشكل المشوّه المخزّن في الفهرس (لخطوط mylotus)"""
    result = text
    for correct, garbled in _BIDI_SWAPS:
        result = result.replace(correct, garbled)
    return result


# ─── دالة البحث ───────────────────────────────────────────────────────────────
def search(query: str, k: int = 6) -> list[dict]:
    """BM25 search مع Arabic normalization + BiDi query expansion"""
    norm_q   = normalize_arabic(query)
    garbled_q = normalize_arabic(garble_for_bidi(query))

    tokens         = norm_q.split()
    garbled_tokens = garbled_q.split()

    if not tokens:
        return []

    scores1 = BM25_INDEX.get_scores(tokens)

    if garbled_tokens != tokens:
        scores2  = BM25_INDEX.get_scores(garbled_tokens)
        combined = [max(s1, s2) for s1, s2 in zip(scores1, scores2)]
    else:
        combined = scores1

    ranked = sorted(range(len(combined)), key=lambda i: combined[i], reverse=True)
    results = []
    for idx in ranked[:k]:
        if combined[idx] > 0:
            results.append(CHUNKS[idx])
    return results


# ─── System Prompt ────────────────────────────────────────────────────────────
BASE_SYSTEM = """أنت مستشار قانوني متخصص في التشريعات والقوانين الكويتية.

قاعدة البيانات لديك تحتوي على مقاطع من أكثر من 85 تشريعاً كويتياً، أبرزها:
القانون المدني، قانون التجارة، قانون المرافعات، قانون الإفلاس، قانون الشركات،
قانون الجزاء الكويتي، قانون الإجراءات والمحاكمات الجزائية، قانون مكافحة المخدرات،
قانون مكافحة الفساد ولائحته التنفيذية، قانون غسل الأموال، قانون مكافحة الإرهاب،
قانون الأحوال الشخصية (مدني وجعفري)، قانون الأحداث، قانون العمل في القطاع الأهلي،
قانون التأمينات الاجتماعية، قانون المرور، قانون حماية البيئة، قانون الجنسية الكويتية،
دستور دولة الكويت، قانون انتخابات مجلس الأمة، قانون هيئة أسواق المال،
قانون هيئة تنظيم الاتصالات، قانون المطبوعات والنشر، قانون الإعلام الإلكتروني،
قانون حقوق المؤلف، قانون حقوق الطفل، قانون التوثيق، قانون الإثبات،
قانون مزاولة مهنة الطب، قانون حماية الأموال العامة، قانون الكشف عن العمولات،
قانون مكافحة الاتجار بالأشخاص، قانون البلدية، قانون التسجيل العقاري،
قانون الإيجار، قانون المعاملات الإلكترونية، قانون تنظيم القضاء، وغيرها.

قواعد الإجابة:
- تجيب بناءً على المقاطع المرجعية المقدمة.
- تتحدث بثقة وتعطي رأيك القانوني المهني المباشر دون تحفظات أو إخلاء مسؤولية.
- تذكر دائماً المصدر (رقم المادة أو الصفحة أو القسم) عند الإجابة.
- إذا لم تجد الإجابة في المقاطع المرجعية المقدمة، قل ذلك في جملة واحدة مباشرة، ولا تدّعي أن هذا القانون غير موجود لديك لمجرد عدم وروده في المقاطع الظاهرة.
- لا تقل أبداً "لا تتوفر لدي ملفات لقوانين أخرى" — فقاعدة البيانات تغطي أكثر من 85 قانوناً.
- استخدم اللغة العربية الفصحى الواضحة.
- نسّق الإجابة بوضوح: استخدم **عناوين بولد** و– نقاط للقوائم عند الحاجة.
- لا تعيد ذكر السؤال، اذهب مباشرة للإجابة.

المقاطع المرجعية:
{context}"""


# ─── Routes ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data     = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    history  = data.get("history") or []   # [{role, content}, ...]

    if not question:
        return jsonify({"error": "السؤال فارغ"}), 400

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY غير مضبوط على الخادم"}), 500

    # ── البحث ──────────────────────────────────────────────────────────────────
    results = search(question)

    if results:
        parts = []
        for r in results:
            page_label = f"ص{r['page']}" if r["page"] == r.get("page_end", r["page"]) \
                         else f"ص{r['page']}-{r['page_end']}"
            section_label = f" | {r['section']}" if r["section"] else ""
            parts.append(f"[{r['source']} | {page_label}{section_label}]\n{r['text']}")
        context = "\n\n────────────\n\n".join(parts)
    else:
        context = "لا توجد مقاطع ذات صلة في قاعدة البيانات."

    system_prompt = BASE_SYSTEM.format(context=context)

    # ── بيانات المصادر للـ frontend ────────────────────────────────────────────
    sources = []
    seen = set()
    for r in results:
        key = (r["source"], r["page"], r["section"])
        if key not in seen:
            seen.add(key)
            sources.append({
                "source":  r["source"],
                "page":    r["page"],
                "section": r["section"],
            })

    # ── SSE Generator ──────────────────────────────────────────────────────────
    def generate():
        try:
            # أرسل المصادر أولاً
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources}, ensure_ascii=False)}\n\n"

            client   = anthropic.Anthropic(api_key=api_key)
            messages = list(history) + [{"role": "user", "content": question}]

            with client.messages.stream(
                model      = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
                max_tokens = 2048,
                system     = system_prompt,
                messages   = messages,
            ) as stream:
                for text_chunk in stream.text_stream:
                    yield f"data: {json.dumps({'type': 'text', 'content': text_chunk}, ensure_ascii=False)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except anthropic.AuthenticationError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'مفتاح API غير صحيح'}, ensure_ascii=False)}\n\n"
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":   "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":      "keep-alive",
        },
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok", "chunks": len(CHUNKS)})


# ─── Entry Point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
