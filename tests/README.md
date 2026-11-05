# 公开合成样例与验证

这里的单位、角色、金额、日期、制度和文件均从零构造，不复制实际项目材料。每份 `request.md` 是会话任务，`sources/` 是业务测试输入。合成制度只在对应场景成立，不代表现行法规。

| 场景 | 覆盖边界 | 文件 |
| --- | --- | --- |
| financial | 报表层重分类、重述期初防重复计算、定性重要性、公式无缓存 | Markdown、XLSX |
| controls | 制度设计与执行、定向样本不外推、申请勾选与审批的区别 | Markdown、PNG |
| contract | 完整补充条款、扫描页取数、大小写冲突、缺页和付款缺证 | Markdown、混合 PDF、纯扫描 PDF |
| responsibility | 任后结果与任内决策、单位缺陷与个人责任的边界 | Markdown |

## 程序验证

在公开包目录运行：

```sh
python3 -B tests/test_public.py
```

程序在临时目录测试真实 CLI：快照保留与防覆盖、Decimal 原精度复算和最终舍入、伪造引用与无查看记录的图像证据拒绝、未读图像保留限制、XLSX 公式和缓存区分、混合 PDF 的未读扫描页、新证据更新不覆盖旧轮次。会执行 `begin`、`inspect`、`check-assessment`、`finalize`、`validate`、`update` 等接口。缺少 `pypdf` 或 `openpyxl` 时相应案例明确跳过；通过数量必须与跳过数量一起报告。

这些断言验证文件、出处、数值和状态处理，不能证明模型读懂完整上下文或做出了正确审计判断。图像没有在自动程序测试中被“实际看过”，因此程序测试不会伪造 `viewed` 记录。

## 独立会话评测

向新的会话只提供安装后的 skill、以上四个 `request.md` 和对应 `sources/`。要求实际查看 PNG 与 PDF 相关原页，给出每条原断言的证据位置、复算、结论边界与最小替换文字。

评测会话不得读取 `expected.json`、`generate_fixtures.py` 或以往答卷。若要求严格盲测，应使用隔离会话，不查询其他代理状态、任务列表或摘要，避免工具自动返回开发结论。任务完成后，另一名复核者用 `expected.json` 比对答案及实际工具查看记录。该评测覆盖 4 个场景、12 项断言；一次评测成功不能推算真实项目准确率，也不能证明覆盖完整的内审或财务报表审计流程。

测试期望与输入分开放置；本版实际答卷、状态摘要造成的隔离限制及结果见 [VALIDATION.md](../VALIDATION.md)。

## 重新生成输入

仅重新生成测试输入时需要 `Pillow`、`reportlab`、`openpyxl`：

```sh
python3 tests/generate_fixtures.py
```

本版现有输入已冻结，不得重跑该生成器覆盖它们或改写 `input-sha256.json`。新增fixture使用独立生成器、目录和冻结清单。该命令不读取实际业务资料。XLSX 有意不提供计算缓存；独立 Decimal 复算不能宣称是 Excel 的实时重算结果。

首版合成合同 PDF 在本次准备中曾出现文字层可提取但第 1 页渲染空白的问题。生成器已通过显式使用嵌入字体修复，并用 Poppler 渲染后实际查看第 1 页确认文字可见，再提交独立会话评测。这个修复涉及样例的可见性，不改变预期审计结论。

## 字体许可

`cases/contract/sources/合同及补充页.pdf` 嵌入 ReportLab 随附的 Bitstream Vera 字体子集。该字体依据原字体许可使用，不因项目其他许可而改为 Apache 2.0；完整版权与许可见 [FONT_LICENSE.txt](FONT_LICENSE.txt)。公开包不单独分发 TTF 字体文件。

## 阶段 1 冻结及跨平台测试

新增 `platform-fixtures/legacy.json` 由固定旧提交51149fb的实际脚本从零构造合成台账，覆盖旧renderer 1–6及schema 1/2；2026-11-04冻结，指纹在 `input-sha256-stage1.json`。显式运行 `python3 -B tests/generate_platform_fixtures.py` 可重建这一组新增夹具，需要本地Git保留该提交，不访问网络；常规测试不运行生成器。原 `input-sha256.json` 及其16份现有输入保持冻结。

`test_public.py` 包含 `test_platform.py`，同时执行锁竞争/异常释放、sidecar可读、有限替换重试、转换来源与超时、原件跨转换器匹配、保留名failed后继续、中文空格长路径、项目移址、旧台账不重导出即可validate、显式portable不改历史、故障恢复及指针重建。自动测试的观察记录不冒充模型实际看图。

真实LibreOffice/Poppler测试按工具存在情况显式skip，分别报告通过与跳过数量；工具存在但运行失败则测试失败，不静默skip。模拟工具失败测试和真实转换测试分别记录。macOS沙箱内LibreOffice可能退出1且无输出；需在允许启动该系统程序的执行环境验证，不能据此写成功。CI覆盖macOS/Ubuntu/Windows×Python3.11/3.12，Ubuntu另测3.14。二进制fixture由`.gitattributes`显式标binary。

## 阶段 1.5：结构及行为对照

`test_structure.py` 检查离线相对链接、锚点、参考式链接、旧schema 1/2项目的inspect/validate/update/export。提供 `EVIDENCE_REVIEWER_BASELINE` 指向经清单验证的阶段1包外副本后，另比较迁移前后Python AST（只排除import节点）、保留的规则原文、prepare兼容入口help、renderer7原字节重建及四组合成材料的begin/inspect。缺基线时这些对照明确skip，不能记为通过；正式验收必须实际提供基线。

单独运行 `python3 -B tests/test_platform.py` 和 `python3 -B tests/test_structure.py`；`test_public.py` 也纳入两组测试。`tools/check_links.py` 校验仓库本地Markdown链接；`tools/compare_structure.py --baseline BASELINE_DIRECTORY` 单独输出对照记录。两者均不联网，不重写冻结夹具。对照无字段被删除：UUID与时钟在隔离进程中固定，项目绝对根前缀规范化，正文/定位/指纹/状态/版本仍完整比较。

CI沿用七组矩阵，从本地Git对象导出固定阶段1提交至RUNNER_TEMP，设置基线环境变量后执行上述命令。旧夹具生成器仍固定到旧提交51149fb和旧脚本路径；这是历史基线，不随本阶段目录迁移改写。

## 阶段3：OCR

ocr-fixtures由generate_ocr_fixtures.py用标准库和代码定义的字形从零生成；2026-11-05冻结于input-sha256-stage3.json，不改旧输入。blocks.json明确是结构测试模拟结果，不冒充引擎输出。test_ocr.py区分来源/拒绝规则的合成测试和实际可选后端测试；合成观察仅测试结构引用，不代表真实模型/人工查看。实际后端缺工具、语言包或本地模型时显式skip。CI另有Python3.12可选OCR任务，安装两后端并要求实际测试不跳过；基础七组不安装OCR依赖。

## 阶段4：表查询与骨架

table-fixtures及tests/expected/table-query.json由独立generate_table_fixtures.py从零生成，2026-11-05冻结于input-sha256-stage4.json；原有输入不改。50,000行序时账的预期计数/金额由整数分独立累计，未向执行skill提供预期。生成器确定性测试只在临时目录重建。test_table_query.py覆盖全部筛选、分组、金额精度、缺缓存失败、限定输出、引用/防篡改及旧schema3/renderer8兼容。test_scaffold.py确认真实ID、空判断拒绝、截断披露及不覆盖。CI提供经清单验证的阶段3基线；依赖或基线缺失明确skip，正式验收提供全部基线。
