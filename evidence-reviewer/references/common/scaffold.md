# 生成评估骨架

1. 从inspect选择实际版本和单元。2. 执行下面命令生成新骨架。3. 按说明填写真实判断。4. check-assessment通过后进入提交。

用真实inspect数据减少手抄版本/单元ID，骨架本身不完成阅读或判断。

```sh
python3 scripts/review.py scaffold --project /项目 --limit 20
python3 scripts/review.py scaffold --project /项目 --version 实际版本ID --unit 实际单元ID --out /项目/选定评估.json
```

在未提交工作包执行。默认选本轮活动版本，可重复version/unit限定；默认最多20个单元，limit为1至100。输出必须是项目根目录下的新JSON文件，默认assessment.json，旁边生成assessment.README.md说明。已存在的评估或说明文件不覆盖。

JSON预填实际版本、unit ID；已登记查询单元另带真实query_id及result_locator。逐字摘录、概括、读取方法、核验状态和答案由执行会话实际阅读后填写。说明文件另存填写步骤、候选/已选/未纳入数量及实际ID；JSON保持合法语法。未纳入内容继续按任务判断相关性和阅读状态，预览不作为抽样结论。

更新轮次另预填真实change_id、影响候选target_id，筛查结论和决策留空。阅读后按[评估字段](assessment.md)填写实际结果，删除未采用的空对象并补必要任务、计算和观察。未填好的骨架应被check-assessment拒绝；程序不会自动把它提交。查询来源见[表查询](table-query.md)，图像和OCR见[OCR定位](ocr.md)。

发现型任务先按[发现型流程](../evidence-review/discovery.md)制定程序，再根据实际阅读的unit ID定向生成骨架。scaffold默认前20单元不是样本设计，也不会自动创建完整审计方案；tasks、反证关系、合理解释及未完成项由执行会话据实填写。读取采用[有界接口](workflow.md#有界读取与续读)，保留长单元和分页的续读位置。

骨架说明会提醒目录搜索、候选核查和阶段性交付字段；它不会自动认定某份材料无关、创建假observations或填写完成状态。缺口与delivery按[评估字段](assessment.md#6-发现型程序与未完成项)据实补齐。

## 发现型骨架

已启用discovery时先确认冻结计划，可加--plan-version指定当前版本；骨架预填真实计划和检查实例，tasks与executions的判断留空。新增standards、clues按[结果字段](../evidence-review/check-results.md)填写；未执行项不伪填无异常。
