# 生成评估骨架

用真实inspect数据减少手抄版本/单元ID，骨架本身不完成阅读或判断。

```sh
python3 scripts/review.py scaffold --project /项目 --limit 20
python3 scripts/review.py scaffold --project /项目 --version 实际版本ID --unit 实际单元ID --out /项目/选定评估.json
```

在未提交工作包执行。默认选本轮活动版本，可重复version/unit限定；默认最多20个单元，limit为1至100。输出必须是项目根目录下的新JSON文件，默认assessment.json，旁边生成assessment.README.md说明。已存在的评估或说明文件不覆盖。

JSON只预填实际版本和unit ID；已登记查询单元另带真实query_id及result_locator。逐字摘录、概括、读取方法、核验状态及答案留空；没有JSON注释或虚构判断。说明文件记录填写步骤、候选/已选/未纳入数量和实际ID。未纳入不代表不相关或已读，预览也不是抽样结论。

更新轮次另预填真实change_id、影响候选target_id，筛查结论和决策留空。阅读后按[评估字段](assessment.md)填写实际结果，删除未采用的空对象并补必要任务、计算和观察。未填好的骨架应被check-assessment拒绝；程序不会自动把它提交。查询来源见[表查询](table-query.md)，图像和OCR见[OCR定位](ocr.md)。
