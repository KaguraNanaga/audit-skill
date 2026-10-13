# 手动增量复核接口

由会话实际读新材料、比较、找新问题和判断；脚本做版本识别、候选影响、保留历史与恢复。沿用workflow.md的环境要求与assessment.md字段。不要用旧AI结论、生成物或测试答案作为业务事实。

## 新建更新轮次

```json
{
  "event_id": "本次补证的稳定标识",
  "reason": "本轮真实触发原因",
  "source_roots": ["/明确新批次目录"],
  "source_bindings": [{"path":"/新批次/校对稿.vtt","source_id":"真实原Source ID","relation":"correction","reason":"实际确认是该转写的校对稿"}]
}
```

```sh
python3 /skill/scripts/review.py update --project /现有项目 --request /更新请求.json
python3 /skill/scripts/review.py inspect --project /现有项目 --records
```

inspect默认读待审更新；--committed查看最后完成轮次，--run 真实run_id查看历史。--version可以逐份读原件；--records附当前任务、主张、问题、规则、计算与缺证，原ID从实际输出取得。

event_id在同一事件重试时保持不变；输入变了使用新事件。相同事件不同指纹拒绝。source_roots为本轮新增/替换批次，不因旧文件不在这个目录就推定撤回。来源原路径相同，或同字节唯一匹配可识别旧Source；同名本身不够。同字节迁移保留版本，变更内容建立新版本。明确同源的跨文件名校对、返回稿或换目录改稿，用source_bindings登记；relation可replacement/correction/supplement/migration/reparse，后3种中correction/supplement/reparse保留派生父版本。无法确认同源则先保留独立Source和疑问，不猜配对。

请求可加：scope、goal、modes、main_document（null清除主稿；精确路径/唯一名称选定）；changed_entity_ids（计算输入/假设、规则适用或既有判断变化）；withdraw_sources:[{source_id,reason}]（明确撤回采用）；unavailable_sources:[{source_id,reason}]（用户报告不可用，非工具实测）；check_local_availability:true（检查已知原路径）；exclusions（相对排除路径）。来源快照始终保留，原路径不可达不证明历史事实不存在。

原选主稿所在Source替换时跟随其新版本；也可用select-main显式换稿并记录原因。source_version_snapshot含全部已知历史快照，active_source_version_ids才是本轮活动版本；两者不可混用。旧版引用保留原文件名和位置。

默认search覆盖活动版本、本轮变化版本和显式选定的主稿（含旧稿），返回searched_version_ids。指定--version时仅检索列出的版本，不额外加入主稿；SearchRecord保存实际范围。

## 来源注释更正（0.3.0）

既有Source的role/role_basis、signature_status、confirmation_scope、origin_group_id、发言人确认等字段变化，都进入source_annotation_changed及影响复核。可在update请求中带source_annotations，也可在读取后、形成assessment前执行：

~~~sh
python3 /skill/scripts/review.py annotate-sources --project /项目 --annotations /来源更正.json
~~~

文件结构：

~~~json
{"reason":"实际更正依据","source_annotations":[{"source_id":"真实ID","signature_status":"unsigned","confirmation_scope":"实际确认范围"}]}
~~~

命令返回新的changes和impact，据此形成screening和impact_review。重复相同注释不制造变化。可以有理由地判定unaffected，也可defer；不能在提交assessment时突然修改旧来源绕过此步骤。初轮及本轮新Source仍可在assessment中分类。

误把AI、模板、底稿当业务来源时，更正role并复核其Claim/Finding，撤回或改写当前不当判断。旧EvidenceLink不可删除。对已无活动Finding采用、关联Claim已降为insufficient/refuted/unassessed的旧fact_basis关系，程序登记run.evidence_link_retirements，记录理由及停止采用轮次。其他明确停止采用情形可在assessment提供link_retirements列表，每项为link_id和reason，只接受旧关系。活动Finding不得引用已停止采用关系；仍为supported/partial的Claim需要其他当前支持关系。新建的AI/template/workpaper事实关系仍拒绝。旧轮回查仍显示当时分类与采用理由。

返回上轮生成稿时，source_bindings可以用`{path,reviewed_output_id:"原OutputRecord ID",relation:"returned_record",reason}`替代source_id绑定。返回稿作为新来源，based_on_output_id指回原导出，不假称其就是原业务凭证；inspect --records不显示OutputRecord，需从已校验台账取得真实输出ID。

## 实际筛查与评估

update产生run.changes、changed_version_ids与impact_candidates。脚本能沿引用找直接影响，但不知道新文件的全部业务含义，因此先把现有业务对象列为保守候选并标needs_review；候选含缺证及原无异常任务。根据真实主题筛查说明缩小或扩大范围。

先实际inspect、search及必要原页回看，再形成新的assessment。顶层沿用单次字段，另加：

- screening：每个change恰一项 `{change_id,topics:[],new_matters,scope_decision:"targeted|topic|project",basis,affected_ids:[]}`。new_matters写实际新增事项或无新增的理由；不能凭有无旧ID作判断。需要关键图像比较的变化，加visual_check:{state:"viewed|unavailable",basis,artifact_ids:[]}；viewed需旧/新版本实际页图和observations，不能只凭文本无变化。
- impact_review：每个候选恰一项 `{target_id,decision:"review|unaffected|defer",basis,evidence_ids:[],source_version_ids:[],calculation_ids:[],search_record_ids:[]}`。review须实际依据；unaffected保留原对象且解释为何不受影响；defer保留旧判断但维持needs_review。缺证复查应实际search覆盖本批新版本，引用新SearchRecord。

新任务/主张/问题仍用各列表中新key新增，不要求已有匹配对象。修改已有ReviewTask、Claim、EvidenceGap、Calculation、RuleApplication或Finding，在相应列表用 `{key:"本评估别名",id:"原稳定ID",revision_reason:"实际变化及依据",...要修改的字段}`；未列字段从旧对象保留。引用新对象时仍可用key别名。新旧Evidence、EvidenceLink、SourceVersion、读取、搜索和人工审定事件不覆写，建立新记录再关联。更新任务时同时核对procedure、actual_scope、population和uncovered_scope；部分字段继承不会自动把T0范围改成实际完成的T1检查范围。

计算更新后由引擎复算；不提供旧result。改变计算/规则/主张会传播至依赖对象，依赖对象需review或defer，不能以unaffected绕过。实质内容未变不制造业务Revision，本轮实际复核记在run及outcome；最后实质修订的last_reviewed_run可能仍指旧轮次。

缺证改为satisfied时写resolution_reason和resolution_evidence_ids；改withdrawn也写resolution_reason。当前仍需的其他事实单列保留，不因一份回复解决整个复合问题。关闭/撤回Finding同时复核相关缺证是否仍有独立必要，避免旧断言的索资继续出现在当前待办。

新证据证明当时已批准，可以推翻并撤回原断言；后来补批不能抹去当时未批，记录实际整改时间和依据后关闭流程。新稿修正数字时保留旧稿错误的历史，区分是否尚有业务影响。返回确认稿逐项比较改动与签署范围：未确认事项保持未知，生成draft仍为unconfirmed。可改modes为review以复核返回稿，不强制再次起草。

本轮answers必须重新写，旧答案不自动继承；完整核查还需review_checks。延期对象会进入输出限制，不能在摘要中称其已验证。程序只核字段与引用，语义仍须会话最后回看。

每份新增、替换或重解析PDF均要求visual_check，包括文字和矢量勾选同时变化。viewed须实际打开并登记旧/新版本关键原页；未能查看使用unavailable并说明未覆盖范围。脚本能核观察记录与版本引用，不能替代会话实际看图，也不会把文字抽取成功认定为勾选、签章已核。

0.3.1起，未核视觉事项进入run.visual_checks并跨轮保留。如何按范围补看、退出采用以及承接0.3.0旧事项，见[原页核查跟进](visual-followup.md)。后续轮不需要为旧变化伪造一条新的screening。

## 外部规则变化

先实际搜索/打开并保存工具原响应，再用import-web。可在记录中加source_id绑定既有网页来源；失败保留新获取失败事件及旧正文快照，不把网页下线当作规则废止。成功新正文作为新版本，规则适用在rules列表显式修订并复核影响。仅假设或适用变化可用changed_entity_ids启动，仍需说明实际原因和取得的依据；未联网就不称已验证现行规则。

full_body可更新活动正文；snippet_only/partial_body只增加本次获取版本，旧完整正文跨后续轮保持可检索。Source记录latest_acquisition_state、latest_acquisition_version_id及retained_full_body_version_ids；各SourceVersion保留取得时间。body_currentness=not_determined_by_acquisition表示获取状态不能证明现行有效，规则时效仍在RuleApplication中依据实际核查判断。新报告分别披露本次获取、旧正文可用性和时效未核范围。

## 提交、重试、恢复

```sh
python3 /skill/scripts/review.py check-assessment --project /项目 --assessment /本轮评估.json
python3 /skill/scripts/review.py finalize --project /项目 --assessment /本轮评估.json
python3 /skill/scripts/review.py validate --project /项目
python3 /skill/scripts/review.py export --project /项目
python3 /skill/scripts/review.py recover --project /项目
```

check-assessment不提交；finalize保存旧台账备份、完整候选和事务记录，再原子替换台账，验证全部导出后更新current指针。多轮schema为evidence-ledger-2.0；原schema 1首次更新时兼容升级，旧轮次快照和旧导出不重写业务内容。

recover先验证权威台账、结构与引用文件。台账完整时保留它，仅继续与其基础指纹和历史严格衔接的待提交事务；旁路候选损坏不能使其降级。台账不可用时按事务候选/备份指纹和完整祖先历史选择唯一恢复点，不按修改时间或初始候选猜测最新。备份副本损坏时可从完整候选重建历史前缀，但须精确匹配事务中的原基础指纹；多分支或无法验证则停止。回退报告rolled_back及unrecovered_run_ids，保留损坏原文件；recovery_warnings是旁路异常，errors为空不表示没有未恢复轮次。

放弃未提交评估用recover --abort --reason '实际原因'，工作包归档；只移动属于该待办轮的事务，保留已提交索引。恢复也检查旧版误移至取消目录的已提交事务。回退或存在pending_review_run_id时，不能称最新工作全部恢复。

新轮次结果为review.md、changes.md、history.md及handoff.md。history按该轮时点导出，未来信息不进入旧轮次；相同输入重试不重复制造对象或Revision。代码提供EVIDENCE_REVIEWER_FAILPOINT仅供隔离测试实际退出进程，正常运行不要设置。

## 数据与导出兼容

0.3.0沿用单轮schema 1、多轮schema 2；旧ledger可validate/inspect，首次update通过原升级机制追加历史，不批量修改已提交账本。新建/修订Gap按validation_version=2校验；旧Gap未修订时保留旧状态和缺项，后续报告提示“旧版关闭状态缺少解决依据”，不自动补证或认定满足。修订时须提供真实解决依据。

新轮OutputRecord.renderer_version=5；旧轮按已登记1—4渲染，保留原字节和指纹，新读取警示不追写旧报告。新报告及handoff自动汇总盘点/读取失败文件、原因、未覆盖范围；validate分别给出structure_valid、material_reading、reading_issues。盘点失败跨轮保留，成功取得同一路径后解除当前盘点警示，旧轮仍保留；损坏/未读单元按活动版本及所选主稿继续列示。结构校验与阅读充分性分别解释。

上段为0.3.0规则；0.3.1新轮使用renderer 6，旧renderer 5也冻结保留。旧轮报告不追加未来提示；当前validate可按历史派生尚未完成的视觉事项，首次新update将其保存到新轮，详见原页核查跟进。
