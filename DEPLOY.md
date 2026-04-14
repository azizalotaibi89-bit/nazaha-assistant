# دليل نشر مستشار نزاهة على Render

## المتطلبات
- حساب GitHub (مجاني)
- حساب Render (مجاني على render.com)
- مفتاح Claude API من console.anthropic.com

---

## الخطوة 1 — إعداد الملفات المحلية

### ضع شعار نزاهة:
انسخ صورة الشعار (PNG) إلى:
```
nazaha-assistant/static/logo.png
```
> الصورة الموجودة حالياً مجرد placeholder — ستستبدلها بالشعار الرسمي

### ضع صورة الخلفية (اختياري):
انسخ صورة الخلفية إلى:
```
nazaha-assistant/static/bg.jpg
```
> إذا لم تضع صورة، سيستخدم الموقع gradient داكن تلقائياً

---

## الخطوة 2 — رفع على GitHub

```bash
# من داخل مجلد nazaha-assistant
cd nazaha-assistant

git init
git add .
git commit -m "init: nazaha RAG assistant"

# أنشئ repo جديد على github.com اسمه nazaha-assistant ثم:
git remote add origin https://github.com/YOUR_USERNAME/nazaha-assistant.git
git branch -M main
git push -u origin main
```

---

## الخطوة 3 — النشر على Render

1. ادخل [render.com](https://render.com) وسجّل دخول
2. اضغط **New → Web Service**
3. اختر **Connect a repository** → اختر `nazaha-assistant`
4. Render سيكتشف `render.yaml` تلقائياً ويضبط الإعدادات

### إضافة API Key:
في صفحة الـ service على Render:
- اذهب إلى **Environment** → **Add Environment Variable**
- Key: `ANTHROPIC_API_KEY`
- Value: مفتاحك من console.anthropic.com

5. اضغط **Deploy** وانتظر 2-3 دقائق

---

## الخطوة 4 — التحقق

بعد اكتمال النشر، افتح الرابط الذي أعطاك إياه Render وتأكد من:
- ظهور صفحة المستشار
- اختبر سؤال مثل: "ما صلاحيات هيئة نزاهة؟"

---

## إضافة ملفات جديدة لاحقاً

```bash
# شغّل ingest.py على الملفات الجديدة
python ingest.py "الملف_الجديد.pdf"

# ارفع chunks.json المحدّث
git add chunks.json
git commit -m "update: add new documents"
git push
```
> Render سيُعيد النشر تلقائياً بعد كل push

---

## هيكل المشروع

```
nazaha-assistant/
├── app.py              ← خادم Flask الرئيسي
├── ingest.py           ← معالج PDF → chunks.json
├── chunks.json         ← قاعدة بيانات الـ chunks (55 chunk من 3 مصادر)
├── requirements.txt    ← مكتبات Python
├── render.yaml         ← إعدادات Render التلقائية
├── .gitignore
├── templates/
│   └── index.html      ← واجهة الدردشة الكاملة
└── static/
    ├── logo.png        ← شعار نزاهة ← ضعه هنا
    └── bg.jpg          ← صورة الخلفية ← ضعها هنا (اختياري)
```
