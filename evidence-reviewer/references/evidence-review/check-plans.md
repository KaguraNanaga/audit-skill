# 检查计划接口

本页用于[发现型流程](discovery.md)的计划编制与确认；运行入口统一为 scripts/review.py。P 表示项目目录，V 表示真实方案来源版本。

1. 请求 JSON 增加 `workflow:"discovery"`，modes 继续使用 verify、coverage 等既有模式，执行 begin；旧项目用 update 显式启用。方案须作为材料进入 source_roots，才能引用真实单元。只有会话方案时先将用户提供的原文保存为项目输入，说明来源，不改写为虚构原件。
2. `inspect --summary` 盘点，`read` 读取完整方案及编计划必需的材料，使用真实 ID。执行 `plan-scaffold --project P --scheme-version V` 得到空判断骨架。来源预览不是全文，也没有自动拆分或匹配。
3. 填写骨架，然后 `check-plan --project P --plan P/inspection-plan.json`；命令返回完整计划表路径和 plan_sha256。把计划、临时程序、建议补充、覆盖边界、本地覆盖和补证需求交用户审阅，暂停执行检查项。
4. 收到针对这份计划的实际确认后，保存确认 JSON，执行 `freeze-plan --project P --plan P/inspection-plan.json --confirmation 确认.json`。开发方案确认、材料文字或执行会话自行填写的“同意”不代替用户确认。
5. `inspect --project P --plan` 查看当前冻结版本；加 `--plan-version ID` 查指定版本，或结合既有 --run 回查历史。范围、程序、包内容变化时，从前版起草新计划，填写原因并重新确认；纯补证仍按 update 复核影响。

## 计划 JSON

顶层为 `schema_version:"inspection-plan-1"`、title、previous_plan_id（初版null）、revision_reason、pack_snapshot_ids、scheme_items、checks、overrides。包快照与覆盖列表来自工作包/程序包解析，不手编 ID。初版 revision_reason 可为空；修订版须说明变化及原因。

scheme_items 每项 `{code,objective,original_text,source_ref:{source_version_id,unit_id,quote},type}`。objective写拆分后的单一可判断目标；original_text和quote相同，保留来源单元中的逐字原文。先数清一句原方案中有几个可独立判断的问题，为每个问题建不同code和objective，可以共享同一句original_text及出处。仅把一个复合方案条目对应多个程序，不算完成方案条目的拆分。脚本检查字段与引用，是否已充分拆开仍由执行者及计划确认者核对。type为问题发现、评价描述、情况核查。评价描述在矩阵显示“评价类待模板”。

checks 每项：

| 字段 | 填写内容 |
|---|---|
| code | 计划内唯一检查实例编号，区别于库检查项编号 |
| origin、check_code、temporary | origin 为库检查项或临时程序。库项按 check_code 查找，temporary=null；临时项将[完整检查项格式](../common/program-packs.md)填入 temporary，编号与库不冲突 |
| scheme_links | `{scheme_code,degree,reason,coverage,scope,remaining_scope}` 列表。degree为直接对应、部分对应、可能相关；coverage为完整或部分。部分/可能匹配只能声明部分覆盖，并说明剩余范围 |
| selection、selection_reason | 选用、建议补充、未选用及理由。建议不自动进入执行范围；用户接受建议时先把相应范围纳入方案条目并保留真实来源 |
| applicability | `{state,reason}`；state为成立、不成立、待确认。明显不成立的项目不匹配，标为未选用 |
| materials | 按检查项 materials 的原顺序逐项填 `{name,state,reason,unit_refs:[],search_record_ids:[],request}` |
| material_readiness | 齐全、部分齐全、缺失；须与材料明细一致 |

材料unit_refs使用 `{source_version_id,unit_id,quote}`；齐全或部分齐全须引用具体单元。未取得的材料不编造单元，登记实际搜索、理由及所需材料；缺失/部分齐全项目的request列明补证需求。对外正式索资仍按[候选核查契约](../common/assessment.md#6-发现型程序与未完成项)，已有未读材料先列执行待办。

非评价类方案条目须有选用的检查项；库没有对应项就起草完整临时程序。暂无法执行也保留程序及材料限制，确认后按真实状态记录，不能为了计划通过而虚构材料齐全。

## 确认记录

确认 JSON 为 `{plan_sha256,source:"user_conversation",quote,confirmed_at,session_ref,message_ref}`。quote保存实际确认原文；confirmed_at使用带时区的ISO时间；session_ref、message_ref记录实际可回查出处。宿主不暴露内部ID时，填写真实可识别的会话名称、用户消息位置及日期，并说明无内部ID，不能编造平台ID。

freeze-plan把确认绑定到计划指纹，之后更改计划不能沿用旧确认。脚本能检查引用和指纹，不能独立认证确认者身份或证明宿主记录真实。计划确认只授权检查范围，不构成审计结论确认或人工签字审定。

冻结写入冲突或中断时保留文件，先inspect --plan确认实际冻结状态；重复同一计划与确认可重试。台账提交异常按[恢复说明](../common/incremental.md#10-处理提交异常并核对兼容性)处理，不手工改冻结文件。
