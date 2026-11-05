# 原页视觉核查的跨轮跟进（0.3.1）

本接口解决“前轮未看原页，后轮提示消失”。查询可在披露限制后继续完成，不将全部PDF永久判为未核。原有PDF变更门槛保持：文字改变也不能代替矢量、勾选和图像核查。

## 登记及读取未决事项

本轮screening中的visual_check仍用state=viewed/unavailable及basis。可选scopes列表，每项为source_version_id和unit_ids，必须分别覆盖该change的旧、新版本，并引用inspect返回的真实单元ID。例如只需核两个版本的关键第2页时，将两页各自的unit ID分别登记，并在basis解释检查范围。未提供scopes时采用旧、新版本的全部已抽取单元；PDF默认为全部已登记物理页。

这些范围在提交后固定保存到run.visual_checks，每项包含id、change_id、opened_run_id、description、scopes、state、history。状态：

- pending：有待完成的原页核查，持续进入review、handoff及material_reading=partial。
- viewed：匹配全部登记范围的有效观察已完成，当前未核提示解除。
- released：有理由地退出相关核查范围，不表示已经查看。

用inspect查看run.visual_checks；query或无关补证后仍需交代pending项。validate.reading_issues列出visual_check_id、scopes及missing_scope，后者是尚缺匹配观察的单元。不要通过只改本轮摘要或不再重复screening来隐藏旧事项。

## 实际补看

按来源版本渲染原页，实际打开相应页图，再将read_id、artifact_id、所见内容和限制写入本轮assessment.observations。生成图本身不算查看。匹配必须同时满足源版本、unit/物理页、页图定位和页图指纹；看新版本不能替代旧版本，看第1页不能解决登记的第2页。

不需要再创建change或重复旧screening。原page记录与新增观察共同保留，已有的有效匹配观察可复用；部分完成只缩小missing_scope，全部登记范围完成才将该项转为viewed。程序验证观察引用，不判断会话是否真的看图；必须如实登记。

## 退出采用或不再相关

在本轮assessment中提供：

~~~json
{"visual_resolutions":[{"check_id":"inspect返回的真实视觉事项ID","decision":"withdrawn","reason":"该来源已明确退出采用，当前任务仅涉及其他材料"}]}
~~~

withdrawn还要求相关版本已经通过update.withdraw_sources等操作退出活动采用；not_relevant表示当前范围不再涉及该视觉事项，可以保留材料本身。两者均需非空真实理由；只删除活动路径、换轮次或有一段解释文字不自动解除。

仍选为主稿，或仍被当前Finding、Claim、Calculation、RuleApplication、相关任务/开放缺证以及本轮答案采用时，不能直接解除。原始Evidence、旧SearchRecord、已退出效力的历史意见和版本派生关系本身不等于当前采用。必要时先根据真实业务变化复核或撤回相应当前判断，再明确退出该视觉事项；不能伪造撤回绕过未核。

released事项保留全部沿革。若以后重新选为主稿或重新被当前判断/答案采用，原未核范围会重新进入pending；withdrawn事项的版本重新成为活动采用时也会重新开放。

## 兼容及历史

沿用ledger schema 1/2，新轮增加visual_checks_version=1。旧0.3.0的unavailable即使在后续空轮已消失，也可按各历史轮的变更、来源单元及已有观察重新承接；不凭当前一轮screening猜测。旧版未明确登记范围时，按相关版本全部单元保守承接。若后续旧轮已有完整匹配观察，承接为已查看；仍未查或仅撤去来源但无处理理由时继续未决。

当前只读validate可披露派生出的旧未核事项；新update将它们保存进新轮。旧ledger和旧输出不重写，新轮使用renderer 6，旧1—5仍按当时格式与原指纹重建。历史状态按各轮时点显示，新轮查看不会把旧轮unavailable改成viewed。
