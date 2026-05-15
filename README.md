# EDA AI 智能助手

> 面向立创EDA的AI智能辅助设计软件 —— 内置 Agent 的 BOM 管理与 PCB 设计助手

## 项目简介

本项目面向立创EDA用户，开发一款内置AI Agent的第三方辅助软件。用户只需用中文描述需求，软件内置的Agent即可自动完成BOM整理、元件校验、交互式HTML BOM生成等任务，大幅降低PCB设计中的重复劳动。

### 适用场景

- 🎓 测控专业课程设计、电子竞赛
- 🔧 硬件开发中的 BOM 物料管理
- 🔍 封装/型号一致性校验
- 🌐 焊接辅助（交互式HTML BOM）

## 功能特性

| 功能 | 描述 | 状态 |
|------|------|------|
| 🤖 AI Agent 对话 | 基于 DeepSeek 的自然语言交互 | 🚧 开发中 |
| 📦 BOM 智能合并 | 同类元件自动合并，输出对比报告 | ✅ 已实现 |
| ✅ 封装校验 | 检测封装与型号不匹配项 | ✅ 已实现 |
| 🔍 位号查重 | 跨文件/单文件重复位号检测 | ✅ 已实现 |
| 🌐 HTML BOM | 交互式网页，点击高亮PCB位置 | 🚧 开发中 |
| 📏 规则检查 | 去耦电容、信号线等规则 | 🚧 开发中 |

## 技术栈

- **语言**: Python 3.10+
- **GUI**: PyQt5
- **AI**: DeepSeek API (大语言模型)
- **数据处理**: pandas, openpyxl
- **HTML模板**: Jinja2
- **打包**: PyInstaller

## 项目结构

```
eda_ai_assistant/
├── main.py                 # 应用入口
├── requirements.txt        # 依赖清单
├── README.md
├── .gitignore
├── src/
│   ├── agent/              # AI Agent 核心模块
│   │   ├── deepseek_client.py   # DeepSeek API 封装
│   │   └── prompt_templates.py  # Prompt 模板库
│   ├── bom/                # BOM 处理引擎
│   │   ├── parser.py            # CSV/Excel 解析
│   │   ├── merger.py            # 同类元件合并
│   │   ├── validator.py         # 封装校验
│   │   └── checker.py           # 位号查重
│   ├── gui/                # PyQt5 图形界面
│   │   ├── main_window.py       # 主窗口
│   │   ├── chat_panel.py        # 聊天面板
│   │   └── bom_table.py         # BOM 表格视图
│   ├── html_bom/           # 交互式 HTML BOM
│   │   ├── generator.py         # 生成器
│   │   └── templates/          # HTML 模板
│   ├── rules/              # 设计规则检查
│   │   └── checker.py
│   └── interfaces/         # 扩展接口
│       ├── simulator.py         # 仿真器抽象
│       └── eda_adapter.py       # EDA 工具适配器
├── tests/                  # 单元测试
├── docs/                   # 文档
└── assets/                 # 资源文件
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API 密钥

创建 `.env` 文件（项目根目录）：

```env
DEEPSEEK_API_KEY=your_api_key_here
```

### 3. 运行应用

```bash
python main.py
```

### 4. 打包为可执行文件

```bash
pyinstaller --onefile --windowed --name "EDA_AI_Assistant" main.py
```

## 开发计划

- [x] 第一阶段 (2026.5-6): 需求分析与原型搭建
- [ ] 第二阶段 (2026.7-10): 核心功能开发
- [ ] 第三阶段 (2026.11-2027.2): 用户界面与交互功能
- [ ] 第四阶段 (2027.3-5): 测试优化与成果输出

## 团队

吉林大学 · 测控技术与仪器专业 · 创新训练项目 © 2026

## 许可证

本项目代码将在 GitHub/Gitee 开源，具体许可证待定。

## 开发日志

- 2026-05-15: BOM引擎完成，AppController架构重构
