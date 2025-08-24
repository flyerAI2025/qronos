#!/bin/bash

# 应用补丁到QRONOS项目的脚本
# 使用方法：./apply_patch.sh <patch_name>

set -e

PATCH_NAME="$1"

if [[ -z "$PATCH_NAME" ]]; then
    echo "使用方法：$0 <patch_name>"
    echo ""
    echo "可用的补丁："
    find patches/ -name "*.patch" -o -name "apply_*.sh" | sort
    exit 1
fi

echo "🔧 应用补丁：$PATCH_NAME"

# 检查补丁文件是否存在
if [[ -f "patches/$PATCH_NAME/apply.sh" ]]; then
    echo "📝 执行补丁应用脚本..."
    bash "patches/$PATCH_NAME/apply.sh"
elif [[ -f "patches/$PATCH_NAME.patch" ]]; then
    echo "📝 应用patch文件..."
    git apply "patches/$PATCH_NAME.patch"
else
    echo "❌ 未找到补丁文件：$PATCH_NAME"
    exit 1
fi

echo "✅ 补丁应用完成"
