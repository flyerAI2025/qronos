#!/bin/bash

# 增强版智能PR脚本 - 包含撤回和描述审核功能
# 使用方法：./create_pr_enhanced.sh [command]
# 命令：create（默认）| withdraw | review

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  ${NC}$1"; }
log_success() { echo -e "${GREEN}✅ ${NC}$1"; }
log_warning() { echo -e "${YELLOW}⚠️  ${NC}$1"; }
log_error() { echo -e "${RED}❌ ${NC}$1"; }
log_review() { echo -e "${CYAN}📝 ${NC}$1"; }

# 获取命令参数
COMMAND=${1:-create}

case "$COMMAND" in
    "withdraw"|"撤回")
        echo "🔙 撤回最近的PR"
        echo "==============="
        echo ""
        
        # 检查GitHub CLI
        if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
            log_error "需要GitHub CLI认证"
            exit 1
        fi
        
        # 获取最新的PR
        LATEST_PR=$(gh pr list --repo Templeton1129/qronos --author @me --json number --jq '.[0].number' 2>/dev/null || echo "")
        
        if [[ -z "$LATEST_PR" ]]; then
            log_warning "未找到你创建的PR"
            exit 0
        fi
        
        log_info "找到PR #$LATEST_PR"
        
        # 显示PR信息
        gh pr view $LATEST_PR --repo Templeton1129/qronos
        echo ""
        
        read -p "确认撤回PR #$LATEST_PR？(y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            read -p "撤回原因（可选）: " WITHDRAW_REASON
            if [[ -n "$WITHDRAW_REASON" ]]; then
                gh pr close $LATEST_PR --repo Templeton1129/qronos --comment "撤回原因：$WITHDRAW_REASON"
            else
                gh pr close $LATEST_PR --repo Templeton1129/qronos --comment "撤回PR以完善内容"
            fi
            log_success "✅ PR #$LATEST_PR 已撤回"
        else
            log_info "取消撤回操作"
        fi
        exit 0
        ;;
        

        
    "create"|"创建"|"")
        echo "🚀 增强版智能PR脚本 - 审核模式"
        echo "=========================="
        echo ""
        REVIEW_MODE=true
        ;;
        
    *)
        echo "使用方法："
        echo "  $0 [create|withdraw]"
        echo ""
        echo "命令说明："
        echo "  create   - 创建PR（默认，包含审核）"
        echo "  withdraw - 撤回最近的PR"
        exit 1
        ;;
esac

# 检查GitHub CLI
if ! command -v gh >/dev/null 2>&1; then
    log_error "需要安装GitHub CLI才能实现完全自动化"
    echo ""
    echo "安装方法："
    echo "  brew install gh"
    echo "  gh auth login"
    exit 1
fi

# 检查GitHub CLI认证
if ! gh auth status >/dev/null 2>&1; then
    log_error "GitHub CLI未认证，请先登录"
    echo "  gh auth login"
    exit 1
fi

# 检查当前分支是否为main
CURRENT_BRANCH=$(git branch --show-current)
if [[ "$CURRENT_BRANCH" != "main" ]]; then
    log_warning "建议在main分支运行此脚本"
    echo "当前分支：$CURRENT_BRANCH"
    read -p "是否继续？(y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# 列出所有本地分支（除了main）
log_info "检测可用的PR分支："
AVAILABLE_BRANCHES=($(git branch --format='%(refname:short)' | grep -v '^main$' | grep -v '^\*' || true))

if [[ ${#AVAILABLE_BRANCHES[@]} -eq 0 ]]; then
    log_error "未找到可用的PR分支（除main外）"
    exit 1
fi

echo "可用分支："
for i in "${!AVAILABLE_BRANCHES[@]}"; do
    echo "$((i+1)). ${AVAILABLE_BRANCHES[i]}"
done
echo ""

# 自动选择第一个分支作为默认
DEFAULT_BRANCH="${AVAILABLE_BRANCHES[0]}"
read -p "选择分支 [1]: " BRANCH_CHOICE
BRANCH_CHOICE=${BRANCH_CHOICE:-1}

# 验证选择
if [[ "$BRANCH_CHOICE" =~ ^[0-9]+$ ]] && [[ "$BRANCH_CHOICE" -ge 1 ]] && [[ "$BRANCH_CHOICE" -le ${#AVAILABLE_BRANCHES[@]} ]]; then
    BRANCH_NAME="${AVAILABLE_BRANCHES[$((BRANCH_CHOICE-1))]}"
else
    log_error "无效选择，使用默认分支：$DEFAULT_BRANCH"
    BRANCH_NAME="$DEFAULT_BRANCH"
fi

log_success "选择的分支：$BRANCH_NAME"

# 自动检测GitHub用户名（从GitHub CLI）
GITHUB_USERNAME=$(gh api user --jq '.login' 2>/dev/null || echo "")
if [[ -z "$GITHUB_USERNAME" ]]; then
    log_error "无法获取GitHub用户名"
    exit 1
fi

log_info "检测到GitHub用户名：$GITHUB_USERNAME"

# 检测Git配置的邮箱
CURRENT_EMAIL=$(git config user.email 2>/dev/null || echo "")
if [[ -z "$CURRENT_EMAIL" ]]; then
    log_error "未检测到Git邮箱配置，请先配置：git config user.email your@email.com"
    exit 1
fi

log_info "使用配置的邮箱：$CURRENT_EMAIL"

# 更新Git配置
git config user.name "$GITHUB_USERNAME"
git config user.email "$CURRENT_EMAIL"

# 切换到目标分支
log_info "切换到目标分支：$BRANCH_NAME"
git checkout "$BRANCH_NAME"

# 检查并修正提交作者
CURRENT_COMMIT_AUTHOR=$(git log --format="%an <%ae>" -1)
EXPECTED_AUTHOR="$GITHUB_USERNAME <$CURRENT_EMAIL>"

if [[ "$CURRENT_COMMIT_AUTHOR" != "$EXPECTED_AUTHOR" ]]; then
    log_info "修正提交作者信息..."
    git commit --amend --author="$EXPECTED_AUTHOR" --no-edit
fi

# 检查是否有远程fork
FORK_URL="https://github.com/$GITHUB_USERNAME/qronos.git"
if ! git remote get-url fork >/dev/null 2>&1; then
    log_info "添加fork远程仓库..."
    git remote add fork $FORK_URL
fi

# 清理远程分支的旧历史（强制推送干净版本）
log_info "清理远程分支旧历史..."
git push fork $BRANCH_NAME --force-with-lease

# 生成PR描述的函数
generate_pr_description() {
    case "$BRANCH_NAME" in
        *docker*volume*mapping*|*pm2*mapping*)
            PR_TITLE="优化Docker部署脚本的PM2目录映射"
            PR_BODY="优化Docker部署脚本的PM2目录映射

🎯 问题：原有的 .pm2 映射是无效的，因为容器中该目录根本不存在，导致无法在宿主机访问PM2的配置和日志。

🔧 解决方案：
- 删除：\`-v \$(pwd)/data/.pm2:/app/.pm2\` 无效的目录映射
- 添加：\`-v \$(pwd)/data/.pm2-runtime:/app/.pm2-runtime\` 映射实际存在的PM2目录
- 简化：只创建实际需要的目录

✅ 效果：
- 🎯 可在宿主机访问完整的PM2配置、日志和进程信息
- 🚀 移除无效映射，简化Docker配置
- 💾 不影响容器内PM2正常运行

## 📋 技术细节
- PM2应用日志通过现有的 \`firm\` 目录映射访问
- PM2系统配置和日志通过新增的 \`.pm2-runtime\` 映射访问
- 删除的 \`.pm2\` 映射指向不存在的目录，完全无效"
            ;;
        *)
            PR_TITLE="改进：$BRANCH_NAME"
            PR_BODY="## 📋 改进内容

$(git log --oneline main..$BRANCH_NAME | sed 's/^[a-f0-9]* /- /')

## 🔧 主要变更

$(git diff --name-only main..$BRANCH_NAME | sed 's/^/- /')

## ✅ 测试状态

- [ ] 本地测试通过
- [ ] 功能验证完成

请review并提供反馈，谢谢！"
            ;;
    esac
}

# 描述审核和编辑功能
review_and_edit_description() {
    while true; do
        generate_pr_description
        
        echo ""
        log_review "📝 PR描述预览："
        echo "================================"
        echo "标题：$PR_TITLE"
        echo ""
        echo "描述："
        echo "$PR_BODY"
        echo "================================"
        echo ""
        
        echo "审核选项："
        echo "1. 接受当前描述"
        echo "2. 修改标题"
        echo "3. 修改描述内容"
        echo "4. 添加内容到描述"
        echo "5. 重新生成描述"
        echo ""
        
        read -p "请选择 [1]: " REVIEW_CHOICE
        REVIEW_CHOICE=${REVIEW_CHOICE:-1}
        
        case "$REVIEW_CHOICE" in
            1)
                log_success "✅ 描述已确认"
                break
                ;;
            2)
                echo ""
                echo "当前标题：$PR_TITLE"
                read -p "新标题: " NEW_TITLE
                if [[ -n "$NEW_TITLE" ]]; then
                    PR_TITLE="$NEW_TITLE"
                    log_success "标题已更新"
                fi
                ;;
            3)
                echo ""
                echo "请输入新的描述内容（输入END结束）："
                NEW_BODY=""
                while IFS= read -r line; do
                    if [[ "$line" == "END" ]]; then
                        break
                    fi
                    NEW_BODY="$NEW_BODY$line"$'\n'
                done
                if [[ -n "$NEW_BODY" ]]; then
                    PR_BODY="$NEW_BODY"
                    log_success "描述已更新"
                fi
                ;;
            4)
                echo ""
                echo "请输入要添加的内容（输入END结束）："
                ADDITIONAL_CONTENT=""
                while IFS= read -r line; do
                    if [[ "$line" == "END" ]]; then
                        break
                    fi
                    ADDITIONAL_CONTENT="$ADDITIONAL_CONTENT$line"$'\n'
                done
                if [[ -n "$ADDITIONAL_CONTENT" ]]; then
                    PR_BODY="$PR_BODY"$'\n\n'"$ADDITIONAL_CONTENT"
                    log_success "内容已添加"
                fi
                ;;
            5)
                log_info "重新生成描述..."
                ;;
            *)
                log_warning "无效选择，请重新选择"
                ;;
        esac
    done
}

# 默认使用审核模式
review_and_edit_description

# 检查是否已存在PR
EXISTING_PR=$(gh pr list --head "$GITHUB_USERNAME:$BRANCH_NAME" --repo Templeton1129/qronos --json number --jq '.[0].number' 2>/dev/null || echo "")

if [[ -n "$EXISTING_PR" ]]; then
    log_warning "PR #$EXISTING_PR 已存在"
    read -p "是否更新现有PR？(Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z "$REPLY" ]]; then
        gh pr edit $EXISTING_PR --title "$PR_TITLE" --body "$PR_BODY" --repo Templeton1129/qronos
        log_success "✅ PR #$EXISTING_PR 已更新！"
        PR_URL=$(gh pr view $EXISTING_PR --json url --jq '.url' --repo Templeton1129/qronos)
    else
        log_info "保持现有PR不变"
        PR_URL=$(gh pr view $EXISTING_PR --json url --jq '.url' --repo Templeton1129/qronos)
    fi
else
    # 创建新PR
    log_info "🚀 创建Pull Request..."
    if gh pr create --title "$PR_TITLE" --body "$PR_BODY" --base main --head "$GITHUB_USERNAME:$BRANCH_NAME" --repo Templeton1129/qronos; then
        log_success "✅ PR创建成功！"
        PR_URL=$(gh pr list --head "$GITHUB_USERNAME:$BRANCH_NAME" --repo Templeton1129/qronos --json url --jq '.[0].url')
    else
        log_error "PR创建失败"
        git checkout main
        exit 1
    fi
fi

# 同步到本地main分支
log_info "同步修改到本地main分支..."
git checkout main

# 检查main分支是否需要更新
if git merge-base --is-ancestor $BRANCH_NAME main; then
    log_info "main分支已包含所有修改"
else
    read -p "是否将修改合并到本地main分支？(Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z "$REPLY" ]]; then
        git merge $BRANCH_NAME --no-ff -m "合并 $BRANCH_NAME 的修改"
        log_success "已合并到本地main分支"
        
        # 自动同步到你的fork远程main分支
        echo ""
        log_info "自动同步本地main到fork远程仓库..."
        git push fork main
        log_success "✅ 已自动同步到你的fork远程main分支"
    fi
fi

# 显示完整的同步状态
echo ""
log_success "🎉 增强版PR流程完成！"
echo ""
echo "📋 结果摘要："
echo "• PR标题：$PR_TITLE"
echo "• PR链接：$PR_URL"
echo "• 分支：$BRANCH_NAME"
echo "• 作者：$GITHUB_USERNAME <$CURRENT_EMAIL>"
echo "• 状态：已自动创建，无需手动操作"
echo ""
echo "🔄 同步状态："
echo "• ✅ 本地分支 → 你的fork远程分支"
echo "• ✅ 本地分支 → 本地main分支 (如果选择)"
echo "• ✅ 本地main → 你的fork远程main (自动)"
echo "• ℹ️  你的fork → 原始仓库 (通过PR完成)"
echo ""
echo "🔗 管理命令："
echo "  $0 withdraw          # 撤回最近的PR"
echo "  $0 review            # 审核模式创建PR"
echo "  gh pr view --repo Templeton1129/qronos"
echo "  gh pr list --repo Templeton1129/qronos"
