# 可选 OCR 定位层

需要让 search 定位扫描材料时使用。OCR 文本是派生的定位内容，实际事实依据仍指向原件及匹配原页的观察。OCR成功不改变原页的 manual_check、failed 或其他读取记录。

## 准备本地工具

默认后端为 Tesseract，需要本地可执行文件以及 chi_sim、eng 两个语言包。Python无需安装额外包装库。使用 RapidOCR 时，在独立环境安装仓库根目录的 requirements-ocr.txt；固定的 rapidocr-onnxruntime 1.4.4 仅支持 Python 3.12及以下，Python 3.13及以上使用 Tesseract。依赖保持可选，主流程不导入OCR后端。

运行前只检查已安装的工具和模型，不安装或下载。RapidOCR仅接收本地文件及包内模型，工作进程禁用网络和ONNX Runtime遥测；不自动切换引擎。缺少工具、模型或语言包记 failed，failure_kind=tool_unavailable。识别异常、超时、无已登记页图等记 failed，继续其余页。工具存在但运行失败不伪装成不可用。

Tesseract的TSV位置和置信度接口见[官方说明](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)；RapidOCR旧包的维护状态见[官方安装说明](https://rapidai.github.io/RapidOCRDocs/main/en/install_usage/rapidocr/install/)。不承诺其他包版本或所有图片格式已验证。

## 执行定位

在未提交的项目工作包中操作；已提交项目先用 update 建立新轮次。用 inspect取得真实版本、原页单元和页图；PDF先用已有 render 生成需要的页图，独立图片已在 begin 登记。

```sh
python3 scripts/review.py render --project /项目 --version 原件版本ID --pages 2
python3 scripts/review.py ocr --project /项目 --version 原件版本ID --pages 2 --engine tesseract --timeout 120
python3 scripts/review.py search --project /项目 --pattern '合同金额' --purpose '定位后打开原页核对'
```

省略pages时处理该版本所有已登记page/image单元；指定pages使用正整数物理页序号，单页独立图片为1。无明确物理页绑定的Word XML段落不作为OCR页；多帧图片需要先分别生成并登记单页图，当前命令不把多帧识别结果冒充单页。

OFD先用显式 --ofd-renderer 登记实际物理页图，再对原页单元执行ocr；文本对象单元不替代OCR来源页。没有页图时保存失败尝试，详见[格式说明](formats.md)。

每次调用追加不可变OCRAttempt，保存源版本/单元、页图ID和哈希、引擎版本、参数、超时、成功结果路径/哈希或失败原因。RapidOCR另保存包内模型哈希和运行库版本。重试保留先前尝试并追加新记录。OCR输出为ocr_derived单元，保留derived_from（版本、原单元、物理页、页图ID及哈希）、置信度、像素bbox（原点为页图左上角）及所属attempt_id。结果文件为规范化的OCR块列表，不是原件字节。

search默认包含OCR单元，每条命中带“OCR 派生，仅供定位，需打开原页确认”；仍列出原页未核范围。先打开该版本、该页图并确认所需区域，再在assessment.observations登记原页read_id、artifact_id及实际所见。生成图、识别成功和search命中都不创建viewed记录。

## 提交与兼容

check-assessment和finalize拒绝缺少对应原页观察的OCR Evidence或来源主张。对应观察须同时匹配版本、原单元、页图ID和哈希；同页另一张渲染图、其他页和旧版本观察均不能替代。观察只登记在原单元，OCR单元不能标记original_viewed；采用的视觉事实应引用原页Evidence。Calculation不接受OCR单元作为事实金额输入，原图取数的现有限制仍见[评估字段](assessment.md)。

校验器检查引用链和结构，不能证明会话实际看图、观察内容充分或业务判断正确；自由文本中的无依据判断仍需执行[准确性核查](accuracy-and-context.md)。

引擎0.4.0支持schema 1/2/3。新工作包使用derived_units_version=1，schema 3按轮保存unit_ids，后轮OCR不进入旧轮单元范围；原单元内容保持。读取、validate和普通export不升级旧台账；显式update/finalize提交新schema时保留旧台账备份、历史轮及原字节导出。新输出使用renderer 8，旧1–7继续按登记版本恢复。包版本描述分发的skill，引擎版本描述台账与校验行为，可运行review.py --version查看。
