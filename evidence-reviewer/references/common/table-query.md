# 大表筛选与查询来源

对已经抽取的CSV/TSV/XLSX版本执行确定性筛选与统计。查询不形成异常、错报或其他审计结论，不证明材料总体完整。先确认表名、表头、主体、期间、单位及借贷方向；业务核查继续按[准确性要求](accuracy-and-context.md)。

## 执行查询

在未提交工作包中执行；已提交项目先update。用真实source_version_id指定原件版本，默认终端只返回10行预览，limit可选0至100。

```sh
python3 scripts/review.py table-query --project /项目 --version 实际版本ID --spec /查询规格.json --limit 10
```

规格示例（列名以实际表头为准；XLSX须另加sheet）：

```json
{"header_row":1,"filters":[{"column":"amount","op":"number_range","min":"0.00","max":"500.00"},{"column":"date","op":"date_range","min":"2031-01-01","max":"2031-01-31"}],"group_by":["category"],"aggregates":[{"op":"sum","column":"amount","as":"total"},{"op":"count","as":"rows"}]}
```

filters采用AND，eq为字符串精确相等，contains为区分大小写的子串；number_range与date_range的min/max均含边界，可只提供一端。日期边界用YYYY-MM-DD，日期时间按其本地日历日期筛选，不转换时区；结果保留完整时间字符串。header_row指CSV/TSV记录序号（不是文本物理行）或Excel工作表行号。表头须非空且不重复；不推测合并表头、同名列或续表归属。group_by须配aggregates；不分组时可统计全部命中行。count统计命中行数，不是非空单元格数。

金额从十进制字符串构造Decimal；XLSX使用openpyxl只读流式取数，并保留OOXML原始数值字面量，不经过float作金额汇总。公式只采用已保存缓存，缺缓存不当作零，也不执行Excel重算。空值、千分位、货币符号或无效日期不会静默归一化：需要数值的筛选/求和遇到它们时登记失败。每行全部筛选条件均校验，即使另一条件已不匹配。求和保留输入小数精度，不中途舍入；数字字符串最多100字符，十进制指数和数量级范围为±100。单位/币种不自动合并或转换，筛选规格及后续计算明确口径。

## 保存内容与引用

每次追加不可变TableQuery，登记源版本/原件哈希、规格与指纹、工具/Python版本（XLSX另记录openpyxl版本）、创建轮次、扫描数、命中数和结果指纹。项目queries/<query_id>/保存spec.json、summary.json、rows.jsonl、groups.jsonl及各自SHA256。每个命中行保留原始locator和已抽取unit_ids，分组关系保留group_key。结果文件可以很大，终端只显示摘要及前N行；这不表示只扫描N行。

处理失败仍登记state=failed、原因和空files，不允许作为依据；继续其他查询或材料。缺openpyxl时XLSX查询明确失败，不改用其他解释器或静默丢弃工作表。

assessment的Evidence或Calculation输入可引用查询：

```json
{"query_id":"实际查询ID","result_locator":{"kind":"group","index":1,"field":"total"}}
```

kind可为row/group/summary；row和group的index从1开始，field指保存结果的列或聚合别名；summary没有index，可选matched_rows等单个标量。程序在候选中生成有来源链的table_query_derived单元，补source_version_id/unit_id。Evidence仍需真实逐字引用、概括及限制；Calculation输入仍需value/raw_value、单位、期间、币种、税口径及normalization。raw_value必须精确等于所选结果，value数值须相同；换单位或舍入用另一个有记录的Calculation，不把查询结果伪装成原件单元。示例还需按[评估字段](assessment.md)补齐完整对象。

check-assessment/finalize/validate核对文件指纹、保存规格/摘要、所引值及来源链；不能证明使用者选择了正确列、总体和业务口径。查询派生值不可标original_viewed，也不可用observations伪装看过原件。用于视觉事实的核查仍回原页。结果哈希是完整性检查，不是外部真实性认证。

## 版本兼容

新轮使用table_queries_version=1扩展schema3；引擎仍属于开发中的0.4.0。旧schema1/2及阶段3的schema3继续读取、validate、update、export，旧账不因读取升级。新输出用renderer9，旧1–8按原指纹重建。新结果及引用只进入本轮和之后，旧轮单元范围不追写。
