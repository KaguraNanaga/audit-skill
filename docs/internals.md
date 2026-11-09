# Evidence Reviewer 维护者说明

本文件随仓库分发，不位于 evidence-reviewer 子目录内。模型执行任务的共同原则和路由在该子目录的 SKILL.md；业务项目仍以自身 ledger/ledger.json 为权威记录。

## 当前目录约定

- `evidence-reviewer/SKILL.md`：单一 skill 入口、共同原则、任务到模块的路由。
- `evidence-reviewer/references/common/`：证据、准确性、读取、台账和增量接口等共享规则。
- `evidence-reviewer/references/evidence-review/`：证据复核模块入口和专用方法。
- `evidence-reviewer/scripts/core/`：本地读取、转换、台账、历史和导出等共享实现。包内使用相对 import；循环依赖保留原有函数内延迟 import。
- `evidence-reviewer/scripts/review.py`：统一 CLI 入口及命令注册。`prepare.py` 是已有盘点命令的兼容入口。
- 当前运行代码没有独立的证据复核专用算法，因此不创建空的 evidence_review 代码包。

内部目录迁移不改变 schema 1/2、引擎0.3.1、readers-1.1、renderer 1–7、命令参数、记录字段、导出文字或原件指纹含义。旧渲染器内的文字与格式保持原样。

## 如何新增模块

1. **明确模块范围。** 给出具体任务、输入、输出及不适用情形，先确定哪些能力可复用 core。脚本只做确定性处理；审计判断由实际核查形成。
2. **建立模块资料。** 使用 `references/<module-id>/index.md` 作为模块入口，将专用参考文档放在同一目录。只有存在实际专用代码时才建立 `scripts/<module_package>/`，加 `__init__.py`。路由标识及文档目录用连字符（如 journal-testing），Python 包目录用下划线（如 journal_testing）。共享规则引用 common，不复制出另一套口径。
3. **登记路由。** 在 SKILL.md 的“任务到模块的路由”表增加一行，列为“当前任务｜模块｜按需读取的入口｜运行入口”。目前唯一模块是 evidence-review，query/verify/coverage/draft/review/rules 仍是其既有模式，不是新增 skill。
4. **注册有实际用途的命令。** 当前入口在 review.py 的 `main()`。需要新 CLI 时，同时在子命令参数声明和 commands 映射中注册，处理函数放在实际模块包内并按需 import；复用 core 的能力。模块目录不会自动扫描、执行或自动增加命令。保留现有命令的名称、参数、默认值、退出码与 JSON 契约；本阶段未添加运行命令。
5. **核对来源及兼容性。** 新派生内容记录源版本、指纹、工具版本和参数；新依赖可选且失败明确。需要 schema 变化时先提升引擎版本并补旧台账兼容测试，不静默改写旧账。
6. **补测试并登记发布。** 在 tests 中增加确定性测试；新材料从零合成、单独冻结，预期与 sources 分开。更新 check_release.py 中已登记目录的白名单，禁止把任意开发文件或业务资料纳入分发。根目录维护文档按check_release.py逐项登记：internals.md、rewrite-rule-mapping.md、SKILL.stage5.diff和stage5-behavior-check.md；不随skill子目录安装。
7. **执行验收后记结果。** 运行 test_public.py、test_platform.py、test_structure.py、check_links.py、check_release.py，执行三系统CI；分开报告通过和跳过。同步 RELEASE_MANIFEST、RELEASE_NOTES；VALIDATION 仅填写实际执行结果。变更运行行为前遵守用户分阶段计划与确认要求。

## 阶段 1.5 的对照方法

对照基线为已验收阶段1提交 `a0cb3714fa7a9d543eb1af0b9b436c38204a73b9`，不是本机可能仍指向旧发布的 HEAD。修改前另保存经发布清单校验的包外副本。CI从本地Git对象导出该提交到临时目录，不由运行脚本联网下载。

`tools/compare_structure.py --baseline BASELINE_DIRECTORY` 在同一解释器及依赖下，对同一批冻结的财务、合同、内控和任期合成输入分别调用调整前后的 begin 与 inspect。

- 不排除任何字段。
- 测试进程固定 L.uid 的UUID序列、L.now的时钟；所有ID、时间字段及相互引用仍比较。
- 只把两个项目各自的绝对根路径前缀规范化为 `$PROJECT`，以比较相同的相对结构。
- 原件SHA256、正文、locator、公式、缓存、状态、限制和版本不屏蔽；副本内的原件字节不改写。

另比较排除import节点后的Python AST、搬迁参考文档的原文，以及旧/新台账的 inspect、validate、update、export。对调整前已提交的renderer 7项目删除临时副本中的导出后重建，要求恢复为原字节；旧renderer 1–6历史仍按冻结指纹校验。链接检查为离线文件/锚点检查，不验证外部网站的当前可用性。

## 阶段3实现与历史范围

OCR共用能力放在core，不新增业务模块或skill。schema3新增OCRAttempt和ocr_derived单元，每轮snapshot保存unit_ids；as_of只返回该轮ID范围。历史单位内容不可变，recovery比较原单元的逐ID内容和每轮视图；旧schema前缀重建必须精确匹配事务原哈希。旧账仅在明确update/finalize时升级并备份。新导出器8追加OCR来源警示，旧1–7实现保持；旧轮portable显式视图仍用renderer7，新轮选择renderer8并保留OCR警示。

阶段1.5的AST/文档原文/输出前后对照固定到阶段1提交a0cb3714和阶段1.5提交4701ac6f，两份均按发布清单验证。当前代码继续单独执行旧台账操作和字节回归，不再把新增功能错误要求为结构迁移。CI设置EVIDENCE_REVIEWER_STRUCTURE_CANDIDATE指向固定阶段1.5目录。

## 阶段4查询实现

TableQuery为不可变事件，table_queries_version=1显式扩展schema3，工具版本table-query-1.0。规范化规格、原件哈希和四个结果文件指纹保存在台账。materialize在副本中按query_id/result_locator生成确定ID的table_query_derived单元；只为实际引用值建立单元，不把整份查询结果复制进台账/上下文。原单元不可改写，按轮unit_ids继续隔离历史。

XLSX查询通过openpyxl read_only和OOXML数值字面量并行读取；通用读取器的公式/缓存改为并行逐行流，现有单元字段有对照测试。台账校验及历史视图使用局部ID集合/索引，避免大表逐单元线性查找造成平方级扫描。renderer9增加查询结果链接与派生警示，旧1–8保持重建指纹；scaffold只在项目根创建新文件。

## 阶段2格式与OFD渲染适配

读取器提升为readers-1.3，新增ofd_reader、xml_reader、pptx_reader及ofd_render，均位于core。没有增加实体种类、强制字段或schema版本；沿用schema1/2/3、引擎0.4.0及renderer9。新增locator和provenance使用既有开放字典，不改旧记录或历史导出。旧不支持格式只在显式reparse时抽取为新版本，匹配仍看原件SHA256。

OFD页单元始终单独登记为manual_check，TextObject单元保留XML声明位置，不能代表版面实际可见内容。物理页按DocBody及Pages声明顺序连续编号。解析器不抽取模板、附件或验证签名；XML部件32MiB/包成员10000上限、DTD/实体拒绝和安全包内引用检查在失败信息中说明。PPTX只提取声明幻灯片中的段落文字；图像/母版/备注等保留未核范围。

本地OFD适配器接口：

```text
python adapter.py --version
python adapter.py INPUT.ofd --output_dir OUTPUT --pages 1 2
```

--version须输出真实渲染器名称与版本；成功输出必须包含全部请求页的page-N.png。适配器负责确保物理页与OFD声明顺序一致、图像确实渲染自输入文件；调用者验证文件存在、PNG头/尺寸并登记来源，不鉴定图像语义。禁止适配器自动下载渲染器、上传原件或开启遥测；安装由环境维护者独立完成。外部工具的字体、模板和原生格式保真范围单独验证。

版本探测10秒、渲染120秒，复用converters.run_tool终止超时进程及子进程。TemporaryDirectory在成功/失败时清理。仅所有请求页成功后发布本次文件，唯一渲染目录避免覆盖旧图。每张真实页图按页单元及各文本对象的准确locator分别登记artifact，文件路径和哈希相同，ID独立；只观察一个对象不会放宽其他对象的viewed校验。OFD页图可作为OCR的原页来源，OCR派生单元不参与对象页图别名登记。

渲染provenance保存在新增artifact内，含原件SHA、源版本、适配器路径/哈希、真实版本、Python版本、参数和超时。失败诊断放run.errors；不修改已提交SourceVersion.processing。处理状态不构成新台账schema。WPS转换仍保留源原件与派生物各自哈希；实际转换测试使用从合成材料导出的MS兼容二进制，不宣称已覆盖WPS生产器所有原生变体。

CI增加固定阶段4提交56095f85541e269d97259d76dddbe3b195a555fa，验证旧schema3/renderer9的未读OFD在未重新导出时仍可validate、显式reparse及历史字节重建。独立Ubuntu Office任务安装可选LibreOffice并要求真实转换测试不跳过；实际OFD渲染器缺失明确skip，不把模拟适配器测试计作真实渲染。

## 文档改写移入的实现与历史契约

下列段落保留基线规则；版本号按原段所属阶段理解。当前引擎0.4.0、读取器readers-1.3、新轮renderer10，schema1/2/3可读取。执行者遇到异常按skill中的恢复操作处理，维护者在此核对实现保证。

### R0303 · 校验与提交

同一已提交评估重放返回原run，不新增对象；不同评估拒绝覆盖，需先update建立新轮次。采用单写入者锁、完整候选暂存、fsync及原子replace；导出全部核验后才更新outputs/current.json。提交后导出中断可export重建；台账损坏保留现场，不初始化为空。staging/validated-candidate.json供检查/人工恢复，不是第二份可编辑权威台账。

### R0304 · 校验与提交

跨批匹配、状态传播和恢复流程见[incremental.md](../evidence-reviewer/references/common/incremental.md)。原件路径迁移可识别并保留旧快照；新轮使用renderer 7相对链接。旧renderer 1–6的导出不改字节；显式 `export --portable` 才在新目录产生带来源清单的可移动视图，普通validate/export不自动生成。旧项目无须重新导出即可validate；若旧导出丢失且新位置无法按原指纹重建，报错并保留现场。

### R0309 · 阶段 1：平台与写入

POSIX 使用 fcntl，Windows 使用 msvcrt 系统锁。独立 `.writer.lock` 不写诊断内容，元数据在 `.writer.lock.json`；判断占用只看系统锁。两端默认等待最多5秒，异常关闭句柄释放系统锁。持锁进程异常退出后的sidecar仅提供残留提示，不据此拒绝新写入者。锁文件保持原位，不删除重建来绕过占用。

### R0310 · 阶段 1：平台与写入

文件写入flush/fsync后原子replace，Windows占用/访问错误有限重试6次（等待总计1.55秒）；失败保留旧权威台账及既有恢复材料。POSIX另外fsync目录，Windows跳过该步；两者不承诺相同的断电后目录持久性。第三方文档渲染器和转换器有各自保证，不能把生成成功当作已看原页。

### R0190 · 提交、重试、恢复

check-assessment不提交；finalize保存旧台账备份、完整候选和事务记录，再原子替换台账，验证全部导出后更新current指针。多轮schema为evidence-ledger-2.0；原schema 1首次更新时兼容升级，旧轮次快照和旧导出不重写业务内容。

### R0191 · 提交、重试、恢复

recover先验证权威台账、结构与引用文件。台账完整时保留它，仅继续与其基础指纹和历史严格衔接的待提交事务；旁路候选损坏不能使其降级。台账不可用时按事务候选/备份指纹和完整祖先历史选择唯一恢复点，不按修改时间或初始候选猜测最新。备份副本损坏时可从完整候选重建历史前缀，但须精确匹配事务中的原基础指纹；多分支或无法验证则停止。回退报告rolled_back及unrecovered_run_ids，保留损坏原文件；recovery_warnings是旁路异常，errors为空不表示没有未恢复轮次。

### R0193 · 提交、重试、恢复

新轮次结果为review.md、changes.md、history.md及handoff.md。history按该轮时点导出，未来信息不进入旧轮次；相同输入重试不重复制造对象或Revision。代码提供EVIDENCE_REVIEWER_FAILPOINT仅供隔离测试实际退出进程，正常运行不要设置。

### R0194 · 数据与导出兼容

0.3.0沿用单轮schema 1、多轮schema 2；旧ledger可validate/inspect，首次update通过原升级机制追加历史，不批量修改已提交账本。新建/修订Gap按validation_version=2校验；旧Gap未修订时保留旧状态和缺项，后续报告提示“旧版关闭状态缺少解决依据”，不自动补证或认定满足。修订时须提供真实解决依据。

### R0195 · 数据与导出兼容

新轮OutputRecord.renderer_version=5；旧轮按已登记1—4渲染，保留原字节和指纹，新读取警示不追写旧报告。新报告及handoff自动汇总盘点/读取失败文件、原因、未覆盖范围；validate分别给出structure_valid、material_reading、reading_issues。盘点失败跨轮保留，成功取得同一路径后解除当前盘点警示，旧轮仍保留；损坏/未读单元按活动版本及所选主稿继续列示。结构校验与阅读充分性分别解释。

### R0196 · 数据与导出兼容

上段为0.3.0规则；0.3.1新轮使用renderer 6，旧renderer 5也冻结保留。旧轮报告不追加未来提示；当前validate可按历史派生尚未完成的视觉事项，首次新update将其保存到新轮，详见原页核查跟进。

### R0198 · 阶段 1 兼容补充

新轮输出使用renderer 7；1–6继续按原指纹保留。读取、validate和普通export均不自动生成可移动视图。需要时显式执行 `export --portable`，新建独立目录及派生manifest，不改历史台账、旧导出或current指针。旧版台账不要求重新导出才能validate。

### R0199 · 阶段 3：派生单元与历史

引擎0.4.0继续读取schema 1/2。新轮提交schema 3，按轮unit_ids固定单元范围，OCRAttempt不可改写。OCR不参与原件文本变更比对，不触发原件指纹变更，也不自动完成视觉待办。旧台账和renderer 1–7不因读取/校验改写；新增能力见[OCR定位层](../evidence-reviewer/references/common/ocr.md)。

### R0288 · 兼容及历史

沿用ledger schema 1/2，新轮增加visual_checks_version=1。旧0.3.0的unavailable即使在后续空轮已消失，也可按各历史轮的变更、来源单元及已有观察重新承接；不凭当前一轮screening猜测。旧版未明确登记范围时，按相关版本全部单元保守承接。若后续旧轮已有完整匹配观察，承接为已查看；仍未查或仅撤去来源但无处理理由时继续未决。

### R0289 · 兼容及历史

当前只读validate可披露派生出的旧未核事项；新update将它们保存进新轮。旧ledger和旧输出不重写，新轮使用renderer 6，旧1—5仍按当时格式与原指纹重建。历史状态按各轮时点显示，新轮查看不会把旧轮unavailable改成viewed。

### R0253 · 提交与兼容

引擎0.4.0支持schema 1/2/3。新工作包使用derived_units_version=1，schema 3按轮保存unit_ids，后轮OCR不进入旧轮单元范围；原单元内容保持。读取、validate和普通export不升级旧台账；显式update/finalize提交新schema时保留旧台账备份、历史轮及原字节导出。新输出使用renderer 8，旧1–7继续按登记版本恢复。包版本描述分发的skill，引擎版本描述台账与校验行为，可运行review.py --version查看。

### R0272 · 版本兼容

新轮使用table_queries_version=1扩展schema3；引擎仍属于开发中的0.4.0。旧schema1/2及阶段3的schema3继续读取、validate、update、export，旧账不因读取升级。新输出用renderer9，旧1–8按原指纹重建。新结果及引用只进入本轮和之后，旧轮单元范围不追写。

### R0192 · 中止事务

放弃未提交评估用recover --abort --reason '实际原因'，工作包归档；只移动属于该待办轮的事务，保留已提交索引。恢复也检查旧版误移至取消目录的已提交事务。回退或存在pending_review_run_id时，不能称最新工作全部恢复。

## 有界读取和renderer 10（2026-11-05）

本轮不改变schema 1/2/3、引擎0.4.0、读取器或既有实体字段。新增inspection.py封装只读视图；review.py显式注册read/search-results，inspect --summary与search --limit为可选参数，旧完整调用保留。目录按来源分页，read按单元及正文字符预算分页，元数据预览显式截断。范围token绑定轮次、SourceVersion记录和单元ID序列；命令不会新增ReadRecord或把返回成功登记为已核。搜索仍在原SearchRecord保存完整结果，因此台账内存和搜索存储并未变成常量空间。

L.output_renderer从本轮已有OutputRecord读取版本；没有本轮输出时选择10，测试覆盖旧显式_renderer_version。L.render在旧JSON规范化之前分发10，旧1–9路径保持原排序和格式。新renderer独立构造正文、来源目录和JSONL附录，不调用旧renderer，也不深复制整个工作包。完整记录附录排除OutputRecord以避免循环指纹，输出记录本身保留于权威台账；历史附录按轮次/实体/修订ID排序，保证提交、读回、恢复和重建的字节一致。

所有新附录沿用OutputRecord登记和原子写入、事务、校验机制。新compact视图只在明确export --compact时创建新目录，附派生台账指纹、renderer、参数及各文件哈希；不会改写旧输出或current指针。export --portable仍沿用已有路径。

read和目录的输出有界不等于进程内存有界：get_work/thaw仍整体加载台账，materialize和历史构建仍有副本，所有导出内容仍先在内存形成字符串。资源测量工具仅使用合成输入，报告实际环境、峰值RSS和文件大小；不得据一次样本外推任意材料上限。无resource模块的平台明确记录峰值未验证。

资源抽查发现新增完整附录时提交峰值仍受整台账JSON副本放大，随后将checksum和atomic_json改为分块编码、哈希和写入。encoded_chunks的UTF-8字节与既有encoded逐字节相同（sort_keys、indent、Unicode、末尾换行均保留）；编码失败删除临时文件，旧权威文件不变，fsync/替换/故障注入语义沿用。此修复没有改变台账格式、指纹算法或字段，也没有使整体JSON读取变为流式。旧1–9指纹回归和实际资源复测分别验证兼容与效果。

## 候选核查与阶段性交付（2026-11-06）

包0.5.0-beta.2、引擎0.4.1。台账仍使用schema3容器，新增run.gap_checks_version=1、新SearchRecord.search_version=2/search_target、新建或修订EvidenceGap.validation_version=3及gap_type/candidate_reviews、outcome.delivery。旧schema1/2/3及Gap1/2原样读取/validate，不静默增加记录或修改历史。history.thaw检查已启用的轮次不能在后轮关闭检查。新轮旗标在begin/update创建，不由assessment降级。

core/gap_checks.py只检查搜索覆盖、完整命中对应候选、引用范围、原页观察、类型一致性及显式部分交付。目录命中按不可变来源版本名称和检索式重新计算；limit只限终端，不缩小候选。引用的本地文字命中也纳入候选。新增活动版本使旧目录搜索不足时拒绝当前v3缺口；执行者可重查并把尚未核的候选明确记为待办。旧Gap仍可保留，renderer11将尚未按新规则复核的旧缺口列待核，避免将旧断言转成新的对外请求。

新单元索引只保存candidate_reviews所需单元。校验不判断关键词选择、语义充分性、候选关联是否合理或用户是否真的调用过图像工具；这依赖宿主日志与人工复核，不作自动审计判断。observations须对应原件单元和已登记图像，OCR/查询派生单元不能替代。

事务state=completed保持原语义；新增commit_state及独立review_state，pending_items覆盖未完成任务、待复核对象和执行缺口。显式partial还需reason/next_step，不能用“提交成功”替代业务完成。初次和增量候选均走同一校验，历史输出重建仍用当时记录的renderer。

renderer11独立于冻结的1–10；新轮使用11，旧轮不自动变化。export --compact默认10以保留旧用法；--renderer 11显式创建新目录及派生manifest，不更改权威台账、历史目录和current指针。正文分执行待办与必要补证，完整候选保存于records.jsonl。新增测试和固定renderer10样本验证这条边界。

## 阶段7：程序包、计划与覆盖

包0.6.0-beta.1、引擎0.5.0；新发现型流程使用schema4和renderer12。core/program_packs处理JSON、快照、ID冲突和生成文档；core/standards校验依据与六项适用性；evidence_review/plans、execution、coverage承载发现型专用契约，review.py显式注册命令。没有自动业务判断、网络访问或新依赖。

PackSnapshot、PlanVersion、PlanConfirmation是不可变事件；Standard、CheckExecution、DiscoveryClue纳入业务Revision和增量影响复核。计划前版以UUID连接，确认引用规范化计划SHA256；项目保存原包字节哈希和规范化包指纹，两者用途不同。计划冻结在项目写锁内原子写一个完整frozen.json，再更新工作包；中断前已写但未引用的快照不授权执行，明确重试相同计划与确认时可复用。after_plan_snapshot故障点用于真实进程中断测试。

check-assessment、finalize、validate共享计划及结果校验；新增来源/标准变化沿既有保守影响复核处理。方案原件被替换/撤回、目标范围或包改变时清除本轮活动计划指针、保留前版，要求重新确认。纯补证沿用冻结范围但重新复核受影响结果。确认字段记录来源，不提供对宿主身份或会话内容的密码学认证。

旧schema1–3只读验证、普通导出不升级。显式update/finalize建立新轮才提交schema4；历史快照保留原数据及当时renderer。schema4恢复增加精确schema3前缀候选，只有原事务哈希一致才采用。新报告在renderer11结果基础上增加计划/标准/覆盖文件，冻结的renderer1–11源文件不改；字段排序确保提交、读回、恢复、重建字节一致。CSV采用UTF-8 BOM，公式形状文本加前导单引号。

通用库JSON与生成Markdown发布时逐字比较。名称扫描只是启发式，人工检查表见[库转换记录](stage7-library-review.md)。开发测试合成确认明确不计作用户授权。独立行为抽查见[实际记录](stage7-behavior-check.md)，未执行部分保持待执行。
