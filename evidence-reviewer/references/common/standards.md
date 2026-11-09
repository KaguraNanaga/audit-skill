# 标准表与适用性

计划确认后，先从实际原文提取标准，再与具体事实结合。外部依据沿用 [rules 来源登记](../evidence-review/modes.md)及 import-web，不凭记忆补条款，不把获取成功当作现行有效。

1. 在 assessment 的 `standards` 中保存每条依据，使用唯一 key。来源为材料单元或已有 RuleApplication；需要补充依据时先登记待核实状态。
2. 对每条线索引用的每条依据，填写六项适用性及理由；行为时间使用事实发生时点。
3. 执行 check-assessment；按错误修正记录矛盾，缺失信息继续保持待核。真实改判通过 update 留下历史。

| 字段 | 内容与枚举 |
|---|---|
| summary、name、document_number、article | 摘要、文件名、文号、条款；未知文号或条款用 null |
| level | 法律、行政法规、部门规章、地方性法规和规章、规范性文件和政策、上级单位制度、本单位制度、合同 |
| effective_at、repealed_at | YYYY-MM-DD 或 null；分别为施行、废止日期 |
| subjects、territory、matter_conditions、exceptions | 适用主体、地域、事项条件和规定本身的例外；未知明确说明待核 |
| nature | 强制性要求、导向性政策 |
| relationships | `{standard_id,relation,reason}` 列表；relation 为更严格、冲突；判断由执行会话依据双方条款形成 |
| source_ref、rule_id、critical_text | 二选一引用：source_ref 为 `{source_version_id,unit_id,quote}`；或 rule_id 指向真实 rules 记录。critical_text 与引用原文一致；无来源时留 null |
| verification_state | 已核对原文、仅有二手来源、待核实 |

未知依据可以登记待核实标准及需要取得的内容，critical_text留空；模型记忆不是条款来源。OFD、扫描等待视觉核对单元采用为已核原文时，先按原页要求实际查看并登记 observations。OCR、筛选结果不作为标准原文。

每个线索的 `standard_applications` 为 `{standard_id,judgments}` 列表。judgments 恰含以下六项，每项都是 `{state,reason}`；state 为成立、不成立、无法确定。

| 字段 | 核对内容 |
|---|---|
| subject | 事实涉及主体是否属于依据的适用主体 |
| time | 行为发生时是否在效力区间内 |
| territory | 地域是否适用 |
| matter_conditions | 事项、前提与例外是否满足 |
| hierarchy | 与其他适用依据的层级、冲突及更严格要求的关系 |
| nature | 该依据的强制或导向性质是否支持本次使用方式 |

日期齐全时，程序采用“施行日包含、废止日不包含”的区间校验。日期缺失，包括空废止日期，时间效力为无法确定，不推定无限期有效。跨越规则变动的多笔事实拆开记录，不用一个有利日期代替整个期间。法律上特殊的生效、过渡或追溯安排由审计人员依据原文判断并明确记录，本脚本没有自动解释规则的能力。

任一适用性未知，或依据尚未核对原文，线索填写 `basis_pending:true`、`verification_status:"待核实"`，输出为需人工判断事项。明确不适用的依据不能支撑已核实结论。导向性政策可作评价依据，不能单独支持 `conclusion_type:"违规"`。

识别本单位制度与上位规定（法律至上级单位制度）冲突时，线索另填 `institutional_inconsistency:{description,standard_ids:[]}`，说明“制度与上位规定不一致”并引用双方依据；不能只留下执行人员违规。与合同的冲突仍登记在relationships中，不把合同自动视为上位规定。是否更严格或冲突属于判断，程序只核验已登记的关系与输出一致性。
