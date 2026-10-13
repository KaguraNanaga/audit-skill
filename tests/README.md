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

重新生成会覆盖本目录内合成输入及 `expected.json`，随后应重新核对图像、PDF 原页与输入指纹。该命令不读取实际业务资料。XLSX 有意不提供计算缓存；独立 Decimal 复算不能宣称是 Excel 的实时重算结果。

首版合成合同 PDF 在本次准备中曾出现文字层可提取但第 1 页渲染空白的问题。生成器已通过显式使用嵌入字体修复，并用 Poppler 渲染后实际查看第 1 页确认文字可见，再提交独立会话评测。这个修复涉及样例的可见性，不改变预期审计结论。

## 字体许可

`cases/contract/sources/合同及补充页.pdf` 嵌入 ReportLab 随附的 Bitstream Vera 字体子集。该字体依据原字体许可使用，不因项目其他许可而改为 Apache 2.0；完整版权与许可见 [FONT_LICENSE.txt](FONT_LICENSE.txt)。公开包不单独分发 TTF 字体文件。
