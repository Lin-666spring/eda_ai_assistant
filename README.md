# EDA AI 智能助手 v0.7.0

> 基于多智能体协同的 PCB 设计辅助工具 — 69条设计规则 · 22项工具 · 10家AI厂商 · 5个专业审查Agent

面向立创EDA用户的 AI 辅助设计软件。支持自然语言交互、多智能体协同审查、BOM智能管理、设计规则检查、供应链健康评估、VLM 视觉分析。

## 核心亮点

- **多智能体协同审查**: 5 个专业 AI Agent（电源/信号/热/EMC/可制造性）并行审查，辩论合成
- **设计质量雷达图**: 6 维度量化评分，可视化展示设计质量
- **设计意图识别**: AI 主动识别电路类型（STM32最小系统/Buck/电机驱动...），提前建议缺失元件
- **12 种电路模板**: 覆盖 STM32/ESP32/Buck/锂电池/RS485/USB-UART/H桥/运放/LED/CAN/SD卡/无线模块
- **10 家 AI 厂商**: DeepSeek / OpenAI / Gemini / Claude / 通义千问 / 智谱 / Kimi / 豆包 / MiniMax / 硅基流动
- **Claude 原生协议**: 直接支持 Anthropic Messages API（非 OpenAI 兼容）

## 快速开始

```bash
pip install -r requirements.txt
python main.py
# → 打开设置(Ctrl+,) 配置 AI 厂商和 API Key → 导入 BOM → 开始使用
```

快捷键: `Ctrl+B` 导入BOM | `Ctrl+R` 多智能体审查 | `Ctrl+Enter` 快速发送 | `Esc` 关闭弹窗

## 功能总览

| 类别 | 功能 | 状态 |
|------|------|------|
| AI 引擎 | 10 厂商 LLM 路由 + Agent Loop (Function Calling) + 流式输出 | 完成 |
| AI 引擎 | Claude 原生 Messages API（非 OpenAI 兼容） | 完成 |
| AI 引擎 | VLM 多模态图片分析（粘贴/上传 PCB 截图） | 完成 |
| BOM 管理 | 智能合并 / AI合并 / 封装校验 / 位号查重 / 筛选 | 完成 |
| BOM 管理 | CSV 导出 (UTF-8-BOM, Excel 兼容中文) | 完成 |
| BOM 管理 | HTML 交互式 BOM 生成 | 完成 |
| 设计规则 | 69 条 PCB 设计规则 (BOM 27 + PCB布线 22 + 布局 20) | 完成 |
| 多智能体 | 5 Agent 并行审查 + 6维度雷达图 + 共识合成 | 完成 |
| 设计意图 | 12 电路模板自动识别 + 缺失元件主动建议 | 完成 |
| 供应链 | 立创商城库存/生命周期/替代料/成本估算 | 完成 |
| 知识库 | ChromaDB 本地 RAG 知识库 | 完成 |
| UI/UX | 多助手实例 / 双窗口模式(完整+伴生) / Agent模式 | 完成 |
| UI/UX | 键盘快捷键 / Toast 通知 / 高级设置面板 | 完成 |
| 系统 | 全局热键(Ctrl+Shift+E) / 系统托盘 / 文件监听 | 完成 |
| 持久化 | SQLite 会话/对话/消息/app_state 全量持久化 | 完成 |

## 架构

```
web/                          # Eel 前端（Cherry Studio 设计系统）
├── index.html                # 三栏布局 + 设置面板 + 审查面板 + 图片粘贴
└── js/app.js                 # 雷达图 Canvas + 多Agent卡片 + 键盘快捷键

src/
├── agent/                    # AI 引擎
│   ├── nlu_engine.py         # 10 意图语义分类 (embedding + 关键词)
│   ├── router.py             # 多 LLM 路由 (10 类意图)
│   ├── llm_client.py         # OpenAI 兼容 LLM 客户端
│   ├── anthropic_client.py   # Claude 原生 Messages API 客户端
│   ├── prompt_templates.py   # 提示模板库
│   ├── tools.py              # 22 工具统一注册表 (SSOT)
│   ├── review_agents.py      # 5 Agent 多智能体协同审查
│   └── design_templates.py   # 12 电路模板 + 设计意图识别
├── core/
│   ├── controller.py         # AppController 编排层
│   ├── design_scorer.py      # 6 维度设计质量评分引擎
│   ├── persistence.py        # SQLite 会话持久化
│   ├── system_bridge.py      # 全局热键 + 系统托盘
│   └── file_watcher.py       # 立创EDA 文件监听
├── bom/                      # BOM 解析/合并/校验/查重
├── pcb/                      # PCB JSON 解析
├── rules/                    # 69 条设计规则
├── supply/                   # 立创商城 API + BOM 健康
├── rag/                      # ChromaDB 知识库
├── html_bom/                 # HTML BOM 生成
└── interfaces/               # EDA 适配器

tests/                        # 367 条测试
```

## 配置

支持 10 家 AI 厂商，在设置面板中可视化切换:

| 厂商 | 默认模型 | API 协议 |
|------|---------|---------|
| DeepSeek | deepseek-v4-pro | OpenAI 兼容 |
| OpenAI | gpt-5.5 | OpenAI 兼容 |
| Gemini | gemini-3.5-flash | OpenAI 兼容 |
| Claude | claude-opus-4-8 | **原生 Messages API** |
| 通义千问 | qwen3.7-max | OpenAI 兼容 |
| 智谱 | glm-5.1 | OpenAI 兼容 |
| Kimi | kimi-k2.6 | OpenAI 兼容 |
| 豆包 | doubao-1.5-pro-256k | OpenAI 兼容 |
| MiniMax | MiniMax-M3 | OpenAI 兼容 |
| 硅基流动 | deepseek-ai/DeepSeek-V4-Flash | OpenAI 兼容 (聚合) |

## 测试

```bash
python -m pytest tests/ -q     # 367 条测试
python -m pytest tests/ -v     # 详细输出
```

## 许可证

MIT License © 2026 吉林大学 · 测控技术与仪器专业 · 创新训练项目
