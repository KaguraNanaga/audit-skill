# OFD、WPS 与通用 XML

按实际格式选择以下步骤；定位和来源登记完成后，依任务继续原页核对与评估。

这些读取路径属于通用 core，不增加业务模块。先用 begin/inspect 登记原件版本及真实单元，再按本页处理格式限制；新材料和已提交项目分别按[运行接口](workflow.md)、[增量接口](incremental.md)操作。

## 1. 定位OFD文本并核对原页

1. begin 按 OFD.xml 中的 DocBody/DocRoot、Document.xml 中的 Pages 声明顺序登记页面。多个文档连续编号，physical_page 从1开始；document 和 ofd_page_id 同时保留。
2. 每页建立 manual_check 页单元；TextObject 中的 TextCode 建立 extracted 对象单元。对象 locator 保存物理页、XML 部件、对象路径/ID及原始 Boundary，text_codes 保留各段文字及 X/Y/DeltaX 等参数。坐标是文件原值，不推断版面阅读顺序、图层可见性或经过变换的视觉位置。
3. search 用对象文字定位，引用时标注“仅文本层”。有文字页与纯图像页都需要相应原页的视觉核查；字体映射、签章、遮挡、图像、附件和数字签名未由本读取器核验。提取器不生成页图，不把嵌入图像当作完整原页。
4. 有可用本地 OFD 渲染适配器时，显式生成对应物理页的图像：

```sh
python3 scripts/review.py render --project /项目 --version OFD版本ID --pages 1 2 --ofd-renderer /本地/ofd_adapter.py
```

适配器须支持 `--version`，以及 `输入OFD --output_dir 目录 --pages 页码...`，返回实际对应的 page-1.png 等文件；接口供维护者接入，不随 skill 提供渲染器。版本探测限10秒，渲染限120秒，超时终止进程并清理临时目录。工具缺失或失败保存到本轮 errors，返回 tool_unavailable/failed，其他命令仍可执行。缺页或无效PNG不发布本次页图。

5. 实际打开成功登记的页图后，使用对应单元 read_id 和 artifact_id 写 observations。同页不同对象仍逐单元确认；生成图不会改变已读状态。需要 OCR 定位时，先登记页图，再执行[OCR命令](ocr.md)，原页观察和 OCR 派生内容继续分开。

OFD XML 部件上限32 MiB，包成员上限10,000；重复或不安全成员、越出包根的引用、外部引用和DTD/实体声明明确失败。单页损坏保留失败页并继续其他声明页。未声明页、模板/附件文本和任意厂商扩展不在当前文本提取范围内。

## 2. 读取XML元素并核对业务依据

begin 对 .xml 提取元素自身文本、子元素尾文本和属性。locator.element_path 使用完整命名空间和同名兄弟序号，例如 `{urn:synthetic:invoice}Line[2]`，避免不同命名空间或重复项目混淆。原值与属性分别保留，search 可查对应文字和属性值。

核对电子发票时，按元素路径引用已提供字段，再核对原件、业务资料及可用的真实查验结果。此读取器不鉴定发票真伪、不校验数字签名，也不访问税务查验或其他外部地址。DTD/实体声明及损坏XML记 failed，其他材料继续处理。

## 3. 读取WPS转换件及幻灯片

| 原件 | 可选本地转换 | 转换后定位及限制 |
|---|---|---|
| .wps | LibreOffice → DOCX | OOXML段落/表格锚点；分页、签章和对象需要回看。可用现有 --docx-renderer 渲染转换件，保留转换限制 |
| .et | LibreOffice → XLSX | 工作表/单元格；公式与缓存分别保留，复杂对象和缓存仍需核查 |
| .dps | LibreOffice → PPTX | 幻灯片声明顺序与XML对象路径；版式、图像、图表、备注、母版和动画另行核查 |
| .pptx | 标准库直接读取 | 与上述PPTX文本边界相同，不生成幻灯片页图 |

LibreOffice通过 shutil.which 或 EVIDENCE_REVIEWER_SOFFICE 定位；每次版本探测及转换使用独立临时用户配置，保留失败、工具版本、参数、原件哈希和转换产物哈希。原件是 SourceVersion 的身份依据，转换产物不能替代原件；同一原件跨平台产生不同转换结果，不自动判为材料变更。

LibreOffice按内容及可用过滤器识别格式；扩展名不是成功承诺。真实WPS原生变体仍需实际样本验证；合成MS兼容二进制路由测试只证明该转换路径。工具缺失或转换失败记 failed/tool_unavailable，继续其余文件。[LibreOffice官方过滤器表](https://help.libreoffice.org/latest/en-US/text/shared/guide/convertfilters.html)

.et提供转换读取、search及单元引用；table-query当前接受CSV/TSV/XLSX原件版本。对需要查询的转换表，另登记转换来源并在明确范围内处理，不能将转换文件冒充独立原件。

## 4. 显式更新旧项目

旧项目中的 unsupported/unread 单元继续按原记录 inspect/validate/export。需要使用新读取器时，通过 update.source_bindings 的 relation=reparse 和实际理由显式重新解析，新增版本并保留原件相同指纹、旧单元、历史输出。OFD新解析或字节变更需要登记视觉核查结果或具体不可用原因；未完成事项按[原页核查跟进](visual-followup.md)持续交接。
