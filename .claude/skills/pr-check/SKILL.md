---
name: pr-check
description: PR 提交前质量检查——测试、敏感文件、代码规范、未提交变更
disable-model-invocation: true
---

# PR 提交前检查

在提交 PR 前执行以下检查，逐项报告结果。

## 检查清单

### 1. 测试全部通过
```
cd PROJECT_ROOT && python -m pytest tests/ -x --tb=short -q
```
如有失败，列出失败的测试名和原因摘要。

### 2. 敏感文件检查
确认以下文件不在暂存区或未跟踪变更中：
- `.env`
- `*.pyc`
- `__pycache__/`
- `logs/`
- `output/`
- `.pytest_cache/`

运行 `git status` 检查。

### 3. 无调试残留
在变更的 Python 文件中搜索：
- `print(` — 调试打印
- `breakpoint()` — 断点
- `import pdb` — pdb 调试器
- `# TODO` 或 `# FIXME` — 待办标记（列出即可，不阻拦）

### 4. Git 状态摘要
- 当前分支名
- 未提交的变更文件列表
- 与 origin/main 的 commit 差异数

## 输出格式
每项用 ✅ / ❌ / ⚠️ 标记结果。最后给出 "可以提交" 或 "需要修复" 的结论。
