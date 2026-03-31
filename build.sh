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
python3 setup.py py2app 2>&1 | grep -E '(error|Error|Done!)'

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
echo "=== 制作 DMG ==="

DMG_NAME="${APP_NAME}"
DMG_PATH="dist/${DMG_NAME}.dmg"
DMG_TEMP="dist/dmg_tmp"

rm -f "${DMG_PATH}"
rm -rf "${DMG_TEMP}"

mkdir -p "${DMG_TEMP}"
cp -R "dist/${APP_NAME}.app" "${DMG_TEMP}/"
ln -s /Applications "${DMG_TEMP}/Applications"

hdiutil create -volname "${APP_NAME}" \
    -srcfolder "${DMG_TEMP}" \
    -ov -format UDZO \
    "${DMG_PATH}"

rm -rf "${DMG_TEMP}"

codesign --force --sign "${SIGN_IDENTITY}" "${DMG_PATH}" 2>&1
echo "✅ DMG 签名完成"

echo ""
echo "=== 完成 ==="
echo "DMG 位置: ${DMG_PATH}"
echo ""
echo "安装: open ${DMG_PATH}"
