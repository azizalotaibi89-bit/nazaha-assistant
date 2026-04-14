#!/bin/bash
# ===================================
# رفع مشروع نزاهة على GitHub
# ===================================

PROJECT="$HOME/Documents/Claude/Projects/نزاهه/nazaha-assistant"
REPO="https://github.com/azizalotaibi89-bit/nazaha-assistant.git"

echo "🚀 جاري رفع المشروع على GitHub..."
cd "$PROJECT" || { echo "❌ المجلد غير موجود"; read -p "اضغط Enter للإغلاق"; exit 1; }

# تنظيف أي قفل قديم
rm -f .git/index.lock 2>/dev/null

# إعداد git
git config user.email "a.alotaibi89@gmail.com"
git config user.name "Abdulaziz Alotaibi"

# تهيئة
git init 2>/dev/null
git branch -M main 2>/dev/null

# إضافة الملفات
git add .
git commit -m "init: nazaha assistant - RAG chatbot for Kuwait Anti-Corruption Authority" 2>/dev/null || echo "لا تغييرات جديدة"

# الرفع
git remote remove origin 2>/dev/null
git remote add origin "$REPO"

echo ""
echo "📤 جاري الرفع... (قد يطلب منك كلمة مرور GitHub)"
echo "   اسم المستخدم: azizalotaibi89-bit"
echo "   كلمة المرور: استخدم Personal Access Token"
echo ""

git push -u origin main

echo ""
echo "✅ تم الرفع بنجاح!"
echo "🌐 الرابط: https://github.com/azizalotaibi89-bit/nazaha-assistant"
read -p "اضغط Enter للإغلاق"
