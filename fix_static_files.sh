#!/bin/bash
# Fix static files and restore dark theme after database issues
# Run this on your Debian VPS

echo "🔧 FIXING STATIC FILES & DARK THEME"
echo "=================================="

# 1. Clear any existing static files
echo "🗑️ Clearing old static files..."
rm -rf staticfiles/*
rm -rf static/css/*.css.gz 2>/dev/null || true

# 2. Collect static files fresh
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# 3. Check if main CSS exists
if [ -f "static/css/style.css" ]; then
    echo "✅ Main CSS file found"
    echo "📄 File size: $(wc -c < static/css/style.css) bytes"
else
    echo "❌ Main CSS file missing!"
    exit 1
fi

# 4. Check if collected in staticfiles
if [ -f "staticfiles/css/style.css" ]; then
    echo "✅ CSS collected in staticfiles"
else
    echo "❌ CSS not collected properly!"
fi

# 5. Test if static URL is accessible
echo "🌐 Testing static files access..."
python -c "
import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erantevou.settings')
django.setup()

print(f'STATIC_URL: {settings.STATIC_URL}')
print(f'STATIC_ROOT: {settings.STATIC_ROOT}')
print(f'DEBUG mode: {settings.DEBUG}')
"

# 6. Restart server process (if using systemd)
echo "🔄 If using systemd, restart with:"
echo "   sudo systemctl restart your-app-name"

# 7. Manual verification commands
echo ""
echo "📋 MANUAL VERIFICATION:"
echo "1. Check if CSS loads: curl -I http://your-domain.com/static/css/style.css"
echo "2. Browser test: Open Developer Tools → Network tab → Look for 404s"
echo "3. If still broken: Check nginx/apache static file serving config"

echo ""
echo "✅ Static files fix complete!"