# 执行结果、线索与覆盖矩阵

1. 确认计划已冻结后，执行 `scaffold --project P --plan-version ID`，预填真实检查实例、计划版本和任务骨架。判断字段留空，需实际执行后填写；未执行项删除空结果，保留待办及部分交付。
2. 按冻结程序核原件、合理解释与反证；用现有 search、原页查看、table-query、Decimal 等工具并保存真实记录。没有跨表自动匹配工具时人工关联，说明方法与未覆盖范围。
3. 在 standards 登记[标准表及六项适用性](../common/standards.md)，在 clues 登记线索，在 executions 登记程序结果。原件证据、任务、计算和缺口沿用[assessment](../common/assessment.md)；新列表同样支持 key 别名。
4. 实际复核重要结论和重要无异常项后，执行 `check-assessment → finalize → validate → export`。有待执行、依据待确认或未覆盖条目时，填写 delivery 的partial、真实原因及下一步。
5. 阅读两种覆盖矩阵，分别交付已执行范围、未执行原因、线索及待核事项。计划外发现单列；需要扩展程序时先修订计划并获得确认。

## executions

每项包含 `key,plan_version_id,check_code,status,scope_complete,actual_scope,uncovered_scope,reason,evidence_ids:[],calculation_ids:[],clue_ids:[],gap_ids:[],task_ids:[]`。

check_code指计划检查实例的code，不是通用库编号。scope_complete为实际完成计划声明范围的布尔值；完成一个明确样本不表示总体已核。task_ids引用至少一个真实ReviewTask。已执行结果须引用原件Evidence，计算和补证按需关联。

新轮次的每项executions还须填scheme_results，与该实例的scheme_links逐项对应：`{scheme_code,state,actual_scope,uncovered_scope,reason}`。state为已覆盖、部分覆盖、未覆盖，表示该程序映射范围内对这个目标的实际执行情况。已覆盖写实际范围并留空剩余范围；部分覆盖两者均写；未覆盖留空实际范围并说明剩余范围和原因。一个程序查过某个目标，不代表同程序下其他目标也查过。scaffold预填真实scheme_code，判断留空。整体scope_complete=true时，各目标均须已覆盖；计划中原本只是部分匹配的条目，即使完成映射范围，方案视图仍显示部分覆盖。

status为“已执行未发现异常、发现线索并已核实、发现线索待核实、无法执行、未选用”。前者须完成所声明范围；无法执行写原因和未覆盖范围；未选用须与冻结计划一致。选用程序改为不做属于范围调整，先修订确认计划。尚未执行的选用项不填虚假结果，矩阵显示待执行。

一份计划中的同一检查实例只有一个当前执行记录；增量修改引用原id及revision_reason。新计划建立新结果，不迁移旧结果冒充新范围已经执行。

## clues

| 字段 | 内容 |
|---|---|
| key、plan_version_id | 本文件别名、冻结计划版本 |
| origin、check_codes | 计划内或计划外发现；计划内引用检查实例列表，计划外必须空列表 |
| fact、fact_evidence_ids | 已读事实及真实Evidence；不以AI、模板或底稿独立证明业务事实 |
| behavior_date | 行为发生日期YYYY-MM-DD；缺失null |
| standard_applications | 逐条依据的六项判断，见标准表说明 |
| actual_decision、required_decision | 各为 `{state,description,reason,evidence_ids:[]}`；state为有证据或待确认。记录实际决策者、按制度应决策者及权限，不推断动机 |
| category | 被审计单位权限内、涉及上级或外部决策、情况记录 |
| conclusion_type | 违规、评价、事实记录、制度与上位规定不一致 |
| verification_status、basis_pending | 已核实或待核实；依据待确认布尔值须与标准核实及适用性一致 |
| institutional_inconsistency | 涉及制度冲突时填写description和双方standard_ids |

计划内线索在对应执行结果的clue_ids中完整列出。计划外发现与计划内计数分开，即使结论相似也不挂到计划内检查项上。需要保留原Finding接口时，新增/修订Finding必须以discovery_clue_id关联受新门槛校验的线索；一般直接用clues。

已核实的异常线索须有决策主体和权限证据；无法取得时保持待核实。情况记录可明确“决策信息不涉及本事实/尚未核查”，不编造决策证据。所有线索仍是供审计人员复核的工作草稿。

## 导出和续办

renderer12导出 inspection-plan.md、standards.md、discovery-clues.md、out-of-plan.md，以及 coverage-checks.md/csv、coverage-scheme.md/csv，review.md和handoff.md提供入口。来源、冻结计划及导出文件均登记指纹。CSV按UTF-8保存，公式形状的文本加前导单引号，以文本形式打开。

检查项视图显示方案匹配、执行状态、三类线索计数、依据待确认数、无法执行/未选用原因、补证需求和剩余范围。方案视图显示已覆盖、部分覆盖、未覆盖、评价类待模板。未执行、无法执行、未选用不计作已执行；部分匹配不自动覆盖完整方案。覆盖说明实际检查范围，不证明无异常或依据已经确认。

矩阵的检查项范围以本次冻结计划为准，包括其中明确列出的建议补充和未选用项；不是通用库全部检查项的完成率。未进入计划的库项目不自动纳入执行或统计。

新材料走 update；旧标准、线索和结果按影响复核说明review/unaffected/defer，延期保持needs_review，旧判断仅供追溯。旧项目普通inspect、validate、export保持历史；显式export --compact --renderer 12只另建视图，没有历史计划的轮次显示未建立，不倒填确认或覆盖。

早期候选没有逐目标记录的轮次保留原输出；显式update启用逐目标范围后，未补登记的目标显示未覆盖/待补记录，不从旧程序级状态推定已经执行。根据原始执行记录补充范围，通过原id及revision_reason登记修订；计划目标和范围未变时沿用原确认，范围变化仍须重新确认。
