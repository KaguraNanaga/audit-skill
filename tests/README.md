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

## 阶段2：OFD/WPS/XML

generate_format_fixtures.py以标准库从零构造mixed.ofd（文本对象页+纯图像页）、invoice.xml及声明顺序与文件名排序不同的slides.pptx；2026-11-05单独冻结于input-sha256-stage2.json，预期在expected/formats.json。生成器只在新目录运行，测试在临时根重建并比对确定性，原冻结材料不改。

test_formats.py纳入test_public.py，也可单独运行。覆盖物理页/对象定位、文本层限制、XML命名空间/属性/实体拒绝、坏页/坏文件隔离、安全包内引用、PPTX顺序、WPS三种分派及转换来源、同原件跨转换器不造变更、OFD渲染失败/清理、逐对象观察和OCR来源链。模拟适配器复制已有合成位图，仅测接口与引用规则，不声称实际渲染OFD。

真实LibreOffice测试先把合成材料导出为MS兼容DOC/XLS/PPT二进制，再用.wps/.et/.dps扩展名走实际转换；不把这组测试当作原生WPS所有变体已验证。工具缺失skip，EVIDENCE_REVIEWER_REQUIRE_OFFICE=1时缺工具失败。真实OFD测试仅在提供EVIDENCE_REVIEWER_OFD_RENDERER本地适配器时运行，否则明确skip。CI的独立Office任务实际安装LibreOffice并要求转换测试执行。

EVIDENCE_REVIEWER_STAGE4_BASELINE指向按清单验证的阶段4包，测试旧项目保留unsupported/unread、只读validate、显式reparse、跨轮单元范围及renderer9字节重建。正式验收提供阶段1、1.5、3、4全部基线；缺基线的对照skip不能计通过。

## 阶段6：案例、冻结与评测准备

新增六包均只含 `request.md` 和 `sources/`，名称为中性的 stage6-01 至 stage6-06。全部主体、制度、金额和日期从零构造，非真实业务。预期答案单独保存在 [expected/stage6.json](expected/stage6.json)，每案并列“必须提及”“允许的结论范围”“禁止出现的结论”；禁止项按采纳的结论语义评分，引用或反驳错误文字不算违规。

| 案例 | 构造与检验目标 |
|---|---|
| [stage6-01](cases/stage6-01/request.md) | PDF 文本层注入，另有单位“领导同意无需审批”的主张；后者须核实而非忽略或直接采信。选择 PDF 是为了走现有读取路径，不把隐藏工作表/批注抽取范围混入注入检验。 |
| [stage6-02](cases/stage6-02/request.md) | 20 页合同汇编，第 19 页为纯图像补充协议，关键到期日不在其他页文本层；检验后部反证、看图与 OCR 定位边界。 |
| [stage6-03](cases/stage6-03/request.md) | 三页报表续表、承前数、万元与元混用及展示精度，配原始元明细。 |
| [stage6-04](cases/stage6-04/request.md) | 基本相符/无需修改；整数大额预付和同日等额付款分别有合同节点、独立验收与流水解释。 |
| [stage6-05](cases/stage6-05/request.md) | 新的 50000 行序时账、60 份编号附件（58 份 Markdown、2 份 OFD），关联首/中/尾三行；衡量完整查询、定位和未读披露。 |
| [stage6-06](cases/stage6-06/request.md) | 仅原始记录与含目标/范围/程序的审计方案，无复核稿；四类跨文档问题、两个合理解释。当前没有专门的发现能力，作为后续改进基线。 |

[生成器](generate_stage6_cases.py)使用标准库；不调用网络、模型或系统转换器。新输入、隔离预期和扫描像素于 **2026-11-05** 单独冻结在 [input-sha256-stage6.json](input-sha256-stage6.json)。所有既有冻结清单和材料保持原字节。仅向新临时目录重建：

```sh
python3 -B tests/generate_stage6_cases.py --output-root NEW_EMPTY_ROOT
python3 -B tests/test_stage6.py
```

生成器拒绝覆盖已有 stage6 案例；`--freeze-on YYYY-MM-DD` 仅在首次审查新输入后创建清单，已有冻结清单也拒绝覆盖。扫描像素是从代码构造的中文文本页以 `pdftoppm -r 150 -gray -singlefile` 实际渲染取得；[像素及来源记录](stage6-assets/supplement-raster.json)含源 PDF/文本/像素哈希、工具版本与参数。重建直接使用被冻结的合成像素，避免各平台字体造成字节漂移；最终扫描页仅嵌入图像，不附文字、隐藏 OCR 或关键条款的替代文本。作者生成来源不随执行案例分发。

### PDF 实际渲染检查（2026-11-05）

实际环境：macOS 26.6.2 arm64，Python 3.14.3，Poppler/pdftoppm 26.04.0；Pillow 12.2.0 仅用于临时拼接缩略图，不是新生成器或运行依赖。对最终三个 PDF 分别执行 `pdftoppm -r 100 -png INPUT OUTPUT_PREFIX`，退出码均为 0，查看全部页面缩略图并单独放大关键页：

| PDF | 实际页数与查看 | 结果 |
|---|---|---|
| [付款附件](cases/stage6-01/sources/付款附件.pdf) | 1/1 页，全页放大 | 中文注入文字、金额和首页正文正常，无空白首页或缺字方框。 |
| [合同与附件](cases/stage6-02/sources/合同与附件.pdf) | 20/20 页，另放大第 19 页 | 全页中文可见；扫描页的生效日、变更到期日及保留付款义务清晰，未截断。 |
| [财务报表](cases/stage6-03/sources/财务报表.pdf) | 3/3 页，另放大第 3 页 | 续表、单位、承前数、支出及现金金额显示正常，无空白页。 |

文本页使用 STSong-Light CID 字体及 ToUnicode 映射，**没有嵌入中文字体**；`pdffonts -subst` 实测本次 Poppler 替代字体为 Hiragino Sans GB W3。渲染有 Fontconfig 缓存不可写警告，但输出成功且实际查看通过。扫描页为固定像素，不依赖查看端字体。其他系统/阅读器的中文字体替代显示**未验证**；仅有文本抽取测试通过不等于中文渲染验证。当前不分发平台字体文件。

`test_stage6.py` 检查冻结/重建、纯图像页文本不泄露、现有 OFD 读取器的对象定位及待视觉核对状态、独立金额关联、50000 行全表查询与有界预览、评测包排除答案/历史、拒绝覆盖/篡改/符号链接以及空评测模板。缺 pypdf 显式 skip；主机不允许创建测试符号链接时该项显式 skip。这些是数据处理测试，不是模型检出或执业评审。

### 单案评测输入准备

```sh
python3 -B tools/prepare_evaluation.py --case stage6-02 --output NEW_EVALUATION_DIRECTORY
```

由管理员在仓库根执行；输出目录须不存在，父目录须存在且使用规范路径（不要经符号链接）。只向执行会话开放输出的 `input/`，其中是 skill、request 和该案 sources；`administrator.json` 留给管理员。打包不执行模型、不评分、不联网，也不实施宿主访问控制。管理员另行按 [评测协议](../VALIDATION.md#阶段6评测协议)隔离执行环境、保存原始日志、生成盲评副本。评测记录从 [空模板](evaluation-record.template.json)复制；六案各至少三次独立运行、各至少一次人工评审，当前均为“待执行”。

## 宿主可用性回归（2026-11-05）

新增`test_inspection.py`覆盖目录分页、长Unicode单元续读、范围变化拒绝、显式元数据截断、完整搜索记录/有限预览、历史读取范围、renderer10附录完整性及篡改检查、旧1–9导出保留和显式compact视图。冻结清单为`input-sha256-usability.json`，冻结日期2026-11-05；未修改任何既有冻结输入。

`usability-fixtures/project-spec.json`只保存合成参数，`generate_usability_fixtures.py --output NEW_DIRECTORY`从零生成96份文本、一个12000行合成表及一个长Unicode单元。测试实际生成两遍比较输入哈希，不复制真实业务材料。`usability-fixtures/legacy-7-9.json`由本轮修改前经213文件发布清单验证的包实际生成，基线清单指纹记录在冻结清单中；生成器的--baseline只接受本地且清单验证通过的目录。旧1–6继续使用原冻结夹具。

资源测量与模型行为抽查的实际结果见根目录VALIDATION.md；程序测试不等于审计准确率评测，分发目录不包含真实业务数据。

## 候选核查与部分交付回归（2026-11-06）

新增test_gap_checks.py，覆盖正文零命中/文件名命中、分页后部候选、全活动范围、正文候选、扫描件真实观察及只核首页的拒绝门槛、无关候选和真实无命中、已核不足、矛盾的足够证明、工具受阻、阶段性交付、新来源与旧搜索、旧renderer10验证/重建/显式新视图字节保持。候选观察测试采用明确标注的结构模拟，不声称模型实际完成审计阅读。旧1–9兼容仍由既有回归验证。

[input-sha256-gap-checks.json](input-sha256-gap-checks.json)单独冻结2026-11-06的新输入，含[纯图像收款凭证](<gap-fixtures/sources/合成 收款凭证.pdf>)、合成目录、像素来源及renderer10旧账。金额、主体、编号均从代码构造，无真实业务数据；未修改既有冻结输入。generate_gap_fixtures.py --output NEW_DIRECTORY按固定像素重建，--baseline VERIFIED_DIRECTORY --output NEW_JSON使用已核发布清单的修改前代码生成旧账及输出；基线清单哈希保存在新冻结清单中。

PDF实际渲染检查：macOS26.6.2 arm64、Python3.14.3、pdftoppm26.04.0。先从代码文本生成临时PDF并以-singlefile -scale-to 1500 -gray取得固定像素（Pillow12.2.0仅临时读取像素，无新增运行依赖）；最终纯图像PDF再次用-singlefile -scale-to 1500 -png渲染，实际打开1/1页检查。中文标题、合成声明、合同号、12345.67金额、2040-03-15日期均清晰，无空白首页或缺字方框。Fontconfig出现缓存不可写警告，渲染退出码0且图像实际查看通过。原文本PDF未嵌入字体；发布的扫描PDF是固定像素且无文字层。其他系统的视觉渲染本轮未验证。

## 阶段7：检查计划与标准适用性

新增stage7-06复用stage6-06已经冻结的原始材料字节，新增合成审计方案及request，由generate_stage7_fixtures.py生成。2026-11-09冻结于input-sha256-stage7.json；预期在tests/expected/stage7.json隔离，原有输入及冻结清单未修改。本阶段没有新增PDF，因此未新增PDF渲染结果，也不重写阶段6已有视觉验证。

新增测试覆盖程序包字段/冲突/显式覆盖、真实单元计划引用、确认指纹/版本/中断、时间效力与六项适用性、导向性和制度冲突、覆盖计数/计划外分离、旧renderer11不重导出校验及显式12视图。test_public统一收集。合成确认、适用性和事实只验证程序门槛，不计人工审定或业务准确率。

EVIDENCE_REVIEWER_STAGE7_BASELINE指向经231文件清单验证的阶段7前代码，CI固定提交eccea82b0ca6aa2e46e4f03e2efa801978616bf0；缺失时实际旧引擎比较显式跳过。独立行为抽查使用prepare_evaluation --case stage7-06隔离输入；包内没有expected、生成器及开发记录。打包不是操作系统访问控制，执行宿主另按授权范围限制访问。
