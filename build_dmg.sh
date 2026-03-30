#!/bin/bash
# 构建 .app 并打包为 DMG（拖拽安装：内含 Applications 快捷方式）
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="随口说"
DMG_NAME="${APP_NAME}.dmg"
STAGING="dist/dmg_staging"

# 代码签名：未设置时使用 ad-hoc（本机可用；分发需自己的证书：export SIGN_IDENTITY="Apple Development: …"）
SIGN_IDENTITY="${SIGN_IDENTITY:--}"

if [ -f "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
else
  PYTHON="${PYTHON:-python3}"
fi

echo "=== 清理旧产物 ==="
rm -rf build "dist/${APP_NAME}.app" "dist/${DMG_NAME}" "${STAGING}"

echo "=== py2app 构建（${PYTHON}）==="
"${PYTHON}" setup.py py2app

if [ ! -d "dist/${APP_NAME}.app" ]; then
  echo "❌ 未生成 dist/${APP_NAME}.app"
  exit 1
fi

echo "=== 代码签名（identity: ${SIGN_IDENTITY}）==="
codesign --force --deep --sign "${SIGN_IDENTITY}" "dist/${APP_NAME}.app"

echo "=== 制作 DMG ==="
mkdir -p "${STAGING}"
ditto "dist/${APP_NAME}.app" "${STAGING}/${APP_NAME}.app"
ln -sf /Applications "${STAGING}/Applications"
# 避免 xattr/隔离标记等导致映像异常；压缩一步直接失败时常见于“半写入”映像（表现为错误 3840）
xattr -cr "${STAGING}" 2>/dev/null || true

# 两步法：先只读可改写的 UDRW，再转成 UDZO，比一步 UDZO 更稳（尤其大体积 .app）
TMP_RW="dist/.${APP_NAME}.rw.dmg"
rm -f "${TMP_RW}"

hdiutil create \
  -volname "${APP_NAME}" \
  -srcfolder "${STAGING}" \
  -ov \
  -format UDRW \
  -fs HFS+ \
  "${TMP_RW}"

hdiutil convert "${TMP_RW}" -format UDZO -ov -o "dist/${DMG_NAME}"
rm -f "${TMP_RW}"
rm -rf "${STAGING}"

echo "=== 校验 DMG ==="
hdiutil verify "dist/${DMG_NAME}"

echo ""
echo "✅ 完成: dist/${DMG_NAME}"
echo "   安装: 打开 DMG，将应用拖入「应用程序」文件夹"
