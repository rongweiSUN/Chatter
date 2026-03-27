#!/bin/bash
set -e

SIGN_IDENTITY="Xiu Dev"
BUNDLE_ID="com.xiu.voiceinput"
APP_NAME="随口说"

echo "=== 构建 ${APP_NAME}.app ==="

# 关闭正在运行的实例
pkill -f "${APP_NAME}" 2>/dev/null || true
sleep 1

# 清理旧构建
rm -rf build
rm -rf dist 2>/dev/null || true

# 构建
python setup.py py2app 2>&1 | grep -E '(error|Error|Done!)'

if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "❌ 构建失败"
    exit 1
fi

echo "=== 签名 ==="
codesign --force --deep --sign "${SIGN_IDENTITY}" "dist/${APP_NAME}.app" 2>&1
echo "✅ 签名完成"

# 验证签名
codesign --verify --verbose "dist/${APP_NAME}.app" 2>&1

echo ""
echo "=== 完成 ==="
echo "应用位置: dist/${APP_NAME}.app"
echo ""
echo "启动: open dist/${APP_NAME}.app"
