# 会话评估字段

assessment.json是完成实际阅读后的结构化结果，不是要求脚本推理的提示词。顶层允许source_annotations、observations、tasks、claims、evidence、links、gaps、calculations、rules、findings、human_decisions、answers、draft、review_checks、limitations；不用的列表可省略。各对象用唯一key作为本文件别名，所有*_id、*_ids自动解析为UUID；来源ID及unit ID必须用inspect返回值。以下是当前实现契约。

## 结果与任务

用户报告的“基本相符/确认有误/需要解释/证据不足”属于呈现层，不是下列枚举的新值。须按每条Claim/Finding的命题方向、实际证据及未获证范围映射，见[报告核验结论等级](report-verification.md)。业务口径和最小修改可写入现有basis、summary、limitations、recommended_action等字段；不自行增加强制字段或改写已提交台账。

重要判断提交前按[准确性核查与交付检查](accuracy-and-context.md)完成上下文、视觉证据、数值/推断及反证检查。将实际检查范围与具体结果写入现有任务、证据和review_checks；受相关未读上下文或不可辨图像影响的命题不得标supported。保留可单独证明的子命题，未完成与证据不足分别说明；不要为满足检查伪造阅读、计算或引用。

- answers：至少一项 `{text,evidence_ids:[],calculation_ids:[],rule_ids:[],task_ids:[]}`。依据至少一类非空；材料不可读可以引用说明局限的任务。无异常不强制Finding，简单查询不强制Claim。
- tasks：`{key,objective,procedure,population,sampling_basis,actual_scope,uncovered_scope,execution_state,result,basis,next_step,source_version_ids:[],record_ids:[]}`。可补subjects/period。execution_state为not_started/partial/done/not_applicable；result为no_exception/exception/undetermined/not_applicable。basis说明判断与边界，未覆盖与实际范围分开。
- review_checks：`{target_id,reason,result,evidence_ids:[],calculation_ids:[]}`。完整核查和记录任务需实际最终复核，reason说明选择问题或无异常任务的理由，result保存可核验复核结果，不记录内部思维过程。
- limitations：字符串列表，保存未读、未查、抽样和不确定事项。

## 来源与读取

- source_annotations：`{source_id,role,role_basis,issuer,signature_status,confirmation_scope,origin_group_id}`；可补formed_at/facts_period/received_at/transcript_kind/confirmed_speakers/audio_version_id。未知用null。role为business/signed/draft/department_statement/transcript/template/ai_analysis/workpaper/external_rule/policy_explanation/unknown；signature_status为unknown/unsigned/signed_unverified/verified，verified需实际依据。origin_group_id指向源Source ID，同源转抄用同组，不按相同金额合并。当前形成/事实时间等注释存在Source，SourceVersion保留初次获取时间与未知初值；多轮Source变更另有Revision，旧轮次保留原注释。
- observations：`{read_id,artifact_id,observation,limitations:[]}`。仅实际打开图片后登记具体可见内容。创建追加viewed记录，不把原extracted记录改掉。Word需实际匹配锚点所在页。

viewed只记录实际查看，不自动代表所有内容可辨。看过但只能读清一部分时，observation及limitations写清区域和不可辨内容，相应任务保留未覆盖范围；用于肯定结论的Evidence不能超出实际看清部分。

## 主张、证据、缺证

- claims：`{key,proposition,type,origin,assessment,basis,task_ids:[],source_locator:null,child_ids:[],parent_id:null}`。type=fact/assumption/normative；origin=source_statement/reviewer_hypothesis/reviewer_opinion。材料陈述须source_locator:{source_version_id,unit_id}；原件比对线索用reviewer_hypothesis。assessment=unassessed/insufficient/partial/supported/refuted。
- evidence：`{key,source_version_id,unit_id,verbatim_quote,reviewer_summary,reading_method,verification_state,limitations:[]}`。quote是该单元逐字子串，不是概括；可以增加image_region_description，但需真实view记录。verification_state=extracted_only/original_viewed/transcript_unverified/tool_body_read/snippet_only。修订/隐藏层限制保留。
- links：`{key,evidence_id,claim_id,direction,supported_scope,conditions,sufficiency,limitations,source_usage}`。direction=supports/opposes/context；source_usage=fact_basis/statement_only/context。AI/template/workpaper不能fact_basis证明业务事实；同源材料不计独立票数。充分程度及必要条件用范围明确文字描述，不能用支持方向代替。
- gaps：`{key,task_ids:[],claim_ids:[],expected_fact,search_record_ids:[],reason_insufficient,minimal_request,state}`。SearchRecord引用真实search/import-web记录；state=open/satisfied/withdrawn。缺证可以没有Evidence，不能虚构证据填表。

## Decimal复算

calculations：`{key,purpose,inputs:[],formula,rounding:{places:2,mode:"ROUND_HALF_UP"},unit,currency,result_kind,assumptions:[],limitations:[]}`。result由引擎生成，若填写则必须一致。result_kind=recalculation/conditional_estimate/scale_check。公式允许输入名、+ - * /、sum(a,b)、min/max/abs。常数也需登记为输入；不允许直接数字常数、代码或属性访问。舍入可ROUND_HALF_UP/ROUND_HALF_EVEN/ROUND_DOWN。

每个输入 `{name,value:"十进制字符串",raw_value:"来源逐字金额",source_version_id,unit_id,unit,currency,period,tax_basis,normalization}`。原值必须在该单元出现；转换需说明单位和规则。无来源的条件参数用input_kind:"parameter",basis:"实际假设依据"，不编来源ID；不能自动套税率。Excel公式/缓存留unit，Decimal结果另存Calculation，不改称Excel实时重算。复算差额与业务异常、错报/损失分开判断。

纯图像金额可依据真实observations及image_region_description形成证据，但当前Calculation原值校验仍依赖可引用单元的文本。若尚无可追溯、已核对的转录单元，不伪造raw_value出处或把事实金额改成parameter绕过；可在引用图像证据的核查说明中保留实际执行的会话复算、输入和舍入，明确其未进入台账的Calculation自动校验，不冒称脚本已验证该图像取数。

## 规则、问题、记录

- rules：`{key,name,issuer,reposting_body,document_number,nature,published_at,effective_at,repealed_at,jurisdiction,official_url,attachment_url,source_version_id,unit_id,critical_text,subjects,conditions,exceptions,behavior_time,applicability_reason,unknowns:[],verification_state,search_record_ids:[],task_ids:[],claim_ids:[]}`。未知null，critical_text须该单元原文；verification_state=body_verified/unverified/snippet_only。摘要不能充正文，本地合成规则不能当真实法规。
- findings：`{key,proposition,task_ids:[],claim_ids:[],supporting_link_ids:[],opposing_link_ids:[],calculation_ids:[],rule_ids:[],summary,impact,impact_basis,severity,recommended_action,contact_role,assessment,workflow,disposition,review_freshness,closure_reason}`。assessment同Claim；workflow=open/awaiting_evidence/awaiting_action/awaiting_review/closed；disposition=active/withdrawn/superseded；review_freshness=current/needs_review。closed需原因，superseded需successor_id。新问题登记本轮；既有问题按自身命题复核，更新字段、理由与历史见incremental.md。
- draft：`{title,confirmation_status:"unconfirmed",sections:[{heading,text,evidence_ids:[],calculation_ids:[]}]}`。draft模式必需，分事实、分析、待核、确认；不能填不存在签字/日期。
- human_decisions：仅实际人工审定时建 `{key,target_id,decision,reason,at,actual_actor,source_evidence_id}`，必须可核实外部记录；Codex复核不属于人工审定。

校验器检查出处、引用、枚举及计算，不能判断所有语义是否充分或是否漏掉反证。最终回看与理由由会话真实执行，不能按字段齐全打分通过。

新建和明确修订的EvidenceGap使用validation_version=2（程序登记，不接受降级）：satisfied需非空resolution_reason及指向实际Evidence的resolution_evidence_ids；withdrawn需非空resolution_reason，不要求伪造证明。open保留真实搜索与不足说明。

增量更新另支持screening、impact_review、link_retirements及既有对象id/revision_reason字段，按[incremental.md](incremental.md)使用；初次评估不接受更新操作。既有来源的实质source_annotations应先暂存，直接写入assessment会提示先执行annotate-sources；新来源仍可在评估时分类。

0.3.1增量评估另可提供visual_resolutions，每项含check_id、decision（withdrawn/not_relevant）和reason，明确退出未核视觉事项；仍被主稿、当前判断或本轮答案采用时拒绝。实际补看只需登记匹配版本及范围的observations，程序据此解决。见[原页核查跟进](visual-followup.md)。
