# 单次审查运行接口

按本页编号步骤核对当前问题，记录实际依据与剩余限制后进入交付；共同检查统一执行[准确性核查](../common/accuracy-and-context.md)。

review.py是确定性助手；执行会话实际读材料、查反证、判断并写assessment.json。不能用测试答案、历史AI结论或整个开发目录作为业务输入。

## 环境与开始

先检查当前环境；有工作区依赖定位工具时用其取得运行库，否则使用已配置的Python环境，验证解释器及所需模块。文本/CSV/SRT/VTT/DOCX用标准库，PDF需pypdf，XLSX只读需openpyxl；DOC可选macOS textutil，缺失/失败后用LibreOffice；XLS需LibreOffice，PDF页图需Poppler的pdftoppm。缺依赖记failed，可用其他读取路径补足但须保留派生来源和限制，不静默猜测。文档编辑、原页查看和联网搜索需要宿主提供相应工具。

请求JSON：

```json
{"goal":"核对选定合同与付款","modes":["verify"],"source_roots":["/明确材料目录"],"scope":{"subjects":[],"audit_period":null},"output":{"format":"md"}}
```

兼容阶段0请求user_request/mode/source_root。模式query、verify、coverage、draft、review、rules可组合；增量补证使用独立的update命令，见incremental.md。scope未知用null。项目必须是来源根之外的新目录。纯rules允许空source_roots。不默认选主稿；确有依据用select-main登记。主稿和取证单可为空；查询不强制Claim/Finding。

```sh
python3 /skill路径/scripts/review.py begin --project /新项目 --request /请求.json
python3 /skill路径/scripts/review.py inspect --project /新项目 --summary --limit 20
python3 /skill路径/scripts/review.py select-main --project /新项目 --version 真实版本ID --reason '用户选定版本的实际依据'
```

优先用下节有界接口。原inspect仍可用--version返回一份或多份完整Source/SourceVersion、units及图片，未带--summary的旧调用保持完整输出，可能很大。必须实际读相关单元及关键原页，不能只看命令摘要。失败材料保留failed单元；扫描页manual_check。unknown角色由执行会话按内容/已知用途分类。

## 搜索与回看

```sh
python3 /skill路径/scripts/review.py search --project /新项目 --target both --pattern '所需关键词' --purpose '提出补证前查找已有附件' --limit 10
python3 /skill路径/scripts/review.py render --project /新项目 --version PDF版本ID --pages 1 2
```

search默认--target text保持原正文/OCR定位搜索；names只查文件名，both同时查文件名与已抽取单元。文件名命中返回match_type=filename、真实版本及定位警示，不伪造unit ID或已读记录。默认覆盖活动/变更/主稿，可重复--version限定。补证前至少有覆盖全部当前范围的names/both搜索，并逐项记录候选处理，见[缺口与交付字段](assessment.md#6-发现型程序与未完成项)。搜索不读取图像正文；未命中继续核相关附件。

PDF用Poppler；DOCX/DOC须传真实--docx-renderer /当前文档技能/render_docx.py，可选--fontconfig /实际配置。返回artifacts只表示已生成图，必须图像工具打开后才能写observations。Word XML锚点不是页码，回看确认其与页图的对应。表格缓存、公式与Decimal复算分开，不声称实时Excel重算。

按[评估字段](assessment.md)写执行会话审查结果，别名key自选，来源ID和unit ID从实际inspect读取。形成重要结论及提交前执行[准确性核查与交付检查](accuracy-and-context.md)，把上下文、原页、复算和反证的实际结果写入现有字段；完整核查也选择重要无异常任务检查遗漏。脚本不自动执行这项语义复核，结构通过不能把受关键未读材料影响的结论升级为已核实。

## 校验与提交

```sh
python3 /skill路径/scripts/review.py check-assessment --project /新项目 --assessment /新项目/assessment.json
python3 /skill路径/scripts/review.py finalize --project /新项目 --assessment /新项目/assessment.json
python3 /skill路径/scripts/review.py validate --project /新项目
python3 /skill路径/scripts/review.py export --project /新项目
```

check-assessment只校验候选并返回计算结果，不提交台账。finalize再次校验、提交唯一ledger/ledger.json；当前导出器生成outputs/<run_id>/review.md、handoff.md、changes.md和history.md及完整JSONL附录，draft模式另有draft.md。台账保存稳定ID、原件版本、读取、任务、判断、初始Revision、输出指纹。提交返回commit_state与review_state，含义及partial交付必填项见[评估字段](assessment.md#6-发现型程序与未完成项)。

## 外部搜索接入

执行会话检查工具并实际调用搜索/打开；缺搜索但能打开时可用已知官方入口，缺工具则记tool_unavailable。只搜索必要公开关键词。原始工具响应原样存UTF-8，再创建web记录JSON：

```json
{"purpose":"核对发布通知","query":"公开关键词","tool":"实际工具名","queried_at":"实际ISO时间","acquisition_state":"partial_body","url":"实际URL","title":"实际标题","text":"原始响应中逐字连续摘录","raw_tool_path":"/原始工具响应.txt","locator":"实际标题/行号/条款","errors":[],"unread_parts":["未取得附件"]}
```

调用 `import-web --project /新项目 --record /记录.json`。状态full_body/partial_body/snippet_only/unavailable/tool_unavailable。成功需原始响应且text是精确子串；失败text为空并保留错误。保存类型是工具响应摘录，不是网站HTML原始字节。脚本不能鉴定响应是否人为伪造，真实性由实际工具调用记录支持。不同尝试分别登记，不覆盖失败。

inspect得到新source_version_id、unit ID、SearchRecord ID，再创建RuleApplication。摘要不能标body_verified；页面正文已打开不等于附件、现行效力或历史适用已核验。

## 阶段 3：OCR定位

可选 `ocr` 命令与search警示、失败处理及回原页观察步骤见[OCR定位层](ocr.md)。OCR只处理已登记页图，原件读取状态与核查边界继续保留。

## 阶段 4：表查询与骨架

大表确定性筛选、分组Decimal求和、计数及查询来源引用见[表查询](table-query.md)；真实ID预填、空判断与更新候选说明见[评估骨架](scaffold.md)。新轮用renderer11，旧1–10保持历史字节，查询不自动生成审计结论。

## 阶段 2：OFD、WPS及XML

begin自动按扩展名选择OFD文本层、通用XML或WPS转换读取。OFD/XML/PPTX读取使用标准库；.wps/.et/.dps需要可选LibreOffice。OFD的render显式传 --ofd-renderer，成功页图可供ocr定位，再实际打开并登记原页observations。定位字段、来源链、适配器接口和旧项目显式reparse见[格式说明](formats.md)。schema保持；新轮使用renderer11，旧项目不自动重新解析。

## 8. 处理冲突与台账异常

按[增量接口的异常处理](incremental.md#10-处理提交异常并核对兼容性)保存现场、恢复并核对结果。提交状态与未完成项核清后再交付；可移动视图使用显式export --portable。

## 有界读取与续读

现有完整inspect/search用法保留。材料多时采用以下接口；这是输出限量，不承诺整个台账的内存上限。

```sh
python3 scripts/review.py inspect --project /项目 --summary --limit 20 --offset 0
python3 scripts/review.py read --project /项目 --version 实际版本ID --limit 20 --chars 12000
python3 scripts/review.py read --project /项目 --version 实际版本ID --offset 20 --text-offset 0 --snapshot 上次read返回的snapshot
python3 scripts/review.py search --project /项目 --pattern '关键词' --purpose '实际查找目的' --limit 10
python3 scripts/review.py search-results --project /项目 --search-id 实际搜索ID --offset 10 --limit 10
python3 scripts/review.py search-results --project /项目 --search-id 实际搜索ID --section unread_parts --limit 10
```

上面的offset值仅示意；实际使用返回的next_offset或next。目录、read和search-results的limit默认20、范围1—100；search只有显式--limit时才限量。read的chars是一次返回的正文字符总预算，默认12000，允许256—32000，不是每个单元的预算。元数据和搜索摘要另有限制，均明确标注truncated及完整长度。

- **目录**：total_sources、returned、remaining、next_offset；sources给真实source_version_id/source_id、原件指纹、抽取状态计数。名称和路径是 `{text,total_chars,truncated}` 预览。按任务决定需要继续哪些目录页，不把首屏当成全部材料。
- **单元**：用真实version，可加--unit只读一个单元。units给unit_id、read_id、locator预览、正文片段及text_start/text_end/text_total；read_id用于真实观察，不能因为命令返回就写observations。read返回next=null才表示本次所选范围已全部返回；不表示执行会话完成核查。next不空时保留相同version/unit，照抄offset、text_offset、snapshot继续；单元片段拼接后才是完整原文。不会自动合并邻接条款或续页。
- **游标范围**：inspect/read的snapshot分别绑定所选轮次、来源版本和单元ID范围，两类游标不能混用。继续期间范围变化会报错，重新取目录/游标。可用--committed或--run固定已提交轮次。它不是外部真实性认证，也不保存执行会话的阅读进度。
- **元数据**：locator、limitations、errors及来源链是显式长度预览，truncated=true时不能作为完整内容引用；确需完整元数据可用原inspect --version。每单元最多预览3个图像登记，artifact_count显示总量；图像是否看过以真实observations为准。
- **搜索**：扫描范围不因limit缩小，完整结果仍存SearchRecord；正文results显示首个命中附近最多600字符及原文偏移；文件名命中显示最多512字符及实际总长度/截断标记。search-results继续同一不可变记录，不重复搜索；section可选results、scope、unread_parts。图像/OCR边界继续保留。回原文用read --version V --unit U --text-offset 实际位置，随后读必要前后文。

renderer11的evidence.md、calculations.md、rules.md分别保留完整摘录/证明边界、复算输入/舍入及规则适用细节；正文保留结果、出处和限制。完整记录、单元、图像登记、读取限制及修订分别存入records.jsonl、units.jsonl、artifacts.jsonl、coverage.jsonl和history.jsonl；sources.md为目录。全部纳入输出指纹校验，详细数据不删减。正文列答案、程序、发现与限制，交接指向具体待办。附录可能很大，按以上接口定位，不一次性加载。

普通export按每轮原renderer恢复已登记文件，不自动更新旧项目。显式`export --compact`在outputs/compact-<ID>/各轮目录创建renderer10视图及派生manifest；要采用新的候选核查与阶段性交付显示，显式加`--renderer 11`；不更改台账、旧输出或current指针。既有`export --portable`保持原兼容行为，两参数互斥。

## 发现型计划入口

请求增加workflow=discovery及可选packs路径，按[检查计划接口](../evidence-review/check-plans.md)使用plan-scaffold、check-plan、freeze-plan。计划确认前只做方案阅读与材料盘点，确认冻结后再执行程序。新导出包含[覆盖矩阵](../evidence-review/check-results.md)。
