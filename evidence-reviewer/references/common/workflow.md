# 单次审查运行接口

review.py是确定性助手；Codex会话实际读材料、查反证、判断并写assessment.json。不能用测试答案、历史AI结论或整个开发目录作为业务输入。

## 环境与开始

先检查当前环境；有工作区依赖定位工具时用其取得运行库，否则使用已配置的Python环境，验证解释器及所需模块。文本/CSV/SRT/VTT/DOCX用标准库，PDF需pypdf，XLSX只读需openpyxl；DOC可选macOS textutil，缺失/失败后用LibreOffice；XLS需LibreOffice，PDF页图需Poppler的pdftoppm。缺依赖记failed，可用其他读取路径补足但须保留派生来源和限制，不静默猜测。文档编辑、原页查看和联网搜索需要宿主提供相应工具。

请求JSON：

```json
{"goal":"核对选定合同与付款","modes":["verify"],"source_roots":["/明确材料目录"],"scope":{"subjects":[],"audit_period":null},"output":{"format":"md"}}
```

兼容阶段0请求user_request/mode/source_root。模式query、verify、coverage、draft、review、rules可组合；增量补证使用独立的update命令，见incremental.md。scope未知用null。项目必须是来源根之外的新目录。纯rules允许空source_roots。不默认选主稿；确有依据用select-main登记。

```sh
python3 /skill路径/scripts/review.py begin --project /新项目 --request /请求.json
python3 /skill路径/scripts/review.py inspect --project /新项目
python3 /skill路径/scripts/review.py select-main --project /新项目 --version 真实版本ID --reason '用户选定版本的实际依据'
```

inspect可用--version逐份读取，返回真实文件名、Source/SourceVersion、units及图片。必须实际读相关单元及关键原页，不能只看命令摘要。失败材料保留failed单元；扫描页manual_check。unknown角色由会话按内容/已知用途分类。

## 搜索与回看

```sh
python3 /skill路径/scripts/review.py search --project /新项目 --pattern '所需关键词' --purpose '提出补证前查找已有附件'
python3 /skill路径/scripts/review.py render --project /新项目 --version PDF版本ID --pages 1 2
```

search在选定版本的全部已抽取单元搜索，保存真实命中及未读部分；可重复--version限定。它不搜索图像；未命中不证明未发生。补证还需会话按主题查看命中及相关材料。

PDF用Poppler；DOCX/DOC须传真实--docx-renderer /当前文档技能/render_docx.py，可选--fontconfig /实际配置。返回artifacts只表示已生成图，必须图像工具打开后才能写observations。Word XML锚点不是页码，回看确认其与页图的对应。表格缓存、公式与Decimal复算分开，不声称实时Excel重算。

按[评估字段](assessment.md)写会话审查结果，别名key自选，来源ID和unit ID从实际inspect读取。形成重要结论及提交前执行[准确性核查与交付检查](accuracy-and-context.md)，把上下文、原页、复算和反证的实际结果写入现有字段；完整核查也选择重要无异常任务检查遗漏。脚本不自动执行这项语义复核，结构通过不能把受关键未读材料影响的结论升级为已核实。

## 校验与提交

```sh
python3 /skill路径/scripts/review.py check-assessment --project /新项目 --assessment /新项目/assessment.json
python3 /skill路径/scripts/review.py finalize --project /新项目 --assessment /新项目/assessment.json
python3 /skill路径/scripts/review.py validate --project /新项目
python3 /skill路径/scripts/review.py export --project /新项目
```

check-assessment只校验候选并返回计算结果，不提交台账。finalize再次校验、提交唯一ledger/ledger.json；当前导出器生成outputs/<run_id>/review.md、handoff.md、changes.md和history.md，draft模式另有draft.md。台账保存稳定ID、原件版本、读取、任务、判断、初始Revision、输出指纹。

同一已提交评估重放返回原run，不新增对象；不同评估拒绝覆盖，需先update建立新轮次。采用单写入者锁、完整候选暂存、fsync及原子replace；导出全部核验后才更新outputs/current.json。提交后导出中断可export重建；台账损坏保留现场，不初始化为空。staging/validated-candidate.json供检查/人工恢复，不是第二份可编辑权威台账。

跨批匹配、状态传播和恢复流程见[incremental.md](incremental.md)。原件路径迁移可识别并保留旧快照；新轮使用renderer 7相对链接。旧renderer 1–6的导出不改字节；显式 `export --portable` 才在新目录产生带来源清单的可移动视图，普通validate/export不自动生成。旧项目无须重新导出即可validate；若旧导出丢失且新位置无法按原指纹重建，报错并保留现场。

## 外部搜索接入

会话检查工具并实际调用搜索/打开；缺搜索但能打开时可用已知官方入口，缺工具则记tool_unavailable。只搜索必要公开关键词。原始工具响应原样存UTF-8，再创建web记录JSON：

```json
{"purpose":"核对发布通知","query":"公开关键词","tool":"实际工具名","queried_at":"实际ISO时间","acquisition_state":"partial_body","url":"实际URL","title":"实际标题","text":"原始响应中逐字连续摘录","raw_tool_path":"/原始工具响应.txt","locator":"实际标题/行号/条款","errors":[],"unread_parts":["未取得附件"]}
```

调用 `import-web --project /新项目 --record /记录.json`。状态full_body/partial_body/snippet_only/unavailable/tool_unavailable。成功需原始响应且text是精确子串；失败text为空并保留错误。保存类型是工具响应摘录，不是网站HTML原始字节。脚本不能鉴定响应是否人为伪造，真实性由实际工具调用记录支持。不同尝试分别登记，不覆盖失败。

inspect得到新source_version_id、unit ID、SearchRecord ID，再创建RuleApplication。摘要不能标body_verified；页面正文已打开不等于附件、现行效力或历史适用已核验。

## 阶段 1：平台与写入

POSIX 使用 fcntl，Windows 使用 msvcrt 系统锁。独立 `.writer.lock` 不写诊断内容，元数据在 `.writer.lock.json`；判断占用只看系统锁。两端默认等待最多5秒，异常关闭句柄释放系统锁。持锁进程异常退出后的sidecar仅提供残留提示，不据此拒绝新写入者。锁文件保持原位，不删除重建来绕过占用。

文件写入flush/fsync后原子replace，Windows占用/访问错误有限重试6次（等待总计1.55秒）；失败保留旧权威台账及既有恢复材料。POSIX另外fsync目录，Windows跳过该步；两者不承诺相同的断电后目录持久性。第三方文档渲染器和转换器有各自保证，不能把生成成功当作已看原页。

## 阶段 3：OCR定位

可选 `ocr` 命令与search警示、失败处理及回原页观察步骤见[OCR定位层](ocr.md)。OCR只处理已登记页图，原件读取状态与核查边界继续保留。

## 阶段 4：表查询与骨架

大表确定性筛选、分组Decimal求和、计数及查询来源引用见[表查询](table-query.md)；真实ID预填、空判断与更新候选说明见[评估骨架](scaffold.md)。新轮用renderer9，旧1–8保持历史字节，查询不自动生成审计结论。

## 阶段 2：OFD、WPS及XML

begin自动按扩展名选择OFD文本层、通用XML或WPS转换读取。OFD/XML/PPTX读取使用标准库；.wps/.et/.dps需要可选LibreOffice。OFD的render显式传 --ofd-renderer，成功页图可供ocr定位，再实际打开并登记原页observations。定位字段、来源链、适配器接口和旧项目显式reparse见[格式说明](formats.md)。schema及renderer9保持，旧项目不自动重新解析。
