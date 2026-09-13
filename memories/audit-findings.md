# 项目"不符合预期"清单与状态

> 2026-09-14 审计

## 已修复

- [x] 测试门禁红灯 4 failed / 839 passed → 843 passed
  - 新增 tests/conftest.py：autouse fixture 清空 config.llm，测试不再受本机 .env 干扰
  - 附带收益：套件 128s → 13.7s（不再偷偷发网络请求）
  - 修正 test_does_not_import_third_party_openai_sdk：改用 ast 只查真实 import
- [x] 文档数字漂移：README/CLAUDE 更新为真实值 71 规则 / 24 工具 / 843 测试（原写 69/22/367/719）
- [x] 仓库一个月未提交：已提交 64fd8ce（601 文件 / 23.3 MB），工作区干净

## 待处理

- [ ] 实验指标可信度：幻觉消除率 100%、多智能体均分 94（min 88.7）无区分度；需重新定义 + 评分校准
- [ ] 规则覆盖率低：79 个真实设计只触发 30/71 条规则
  - 实测依赖：21 条需 PCBData（走线/过孔）、3 条消费 netlist、48 条 BOM+坐标
  - 当前 pcb_path=None、check_all 未传 netlist → 这 24 条从未运行
  - 解决路径：解析 .epro2（见 epro2-format.md）
- [ ] frontend/ 去留：原封不动的 Vite React+TS 模板（node_modules 未提交），实际 UI 是 web/
- [ ] 其他：simulator.py 是占位；convergence.py 基类 evaluate 抛 NotImplementedError；.zcode/config.json 含明文 key（已 gitignore）

## 文档仍偏旧

- PROJECT_BLUEPRINT.md 仍描述 PyQt5 + src/gui/，实际是 Eel web/
- README.md 架构章节仍写"三栏布局"，与 CLAUDE.md 的两级导航不一致
