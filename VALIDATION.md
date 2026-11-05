# 公开版验证记录

当前发布包：0.5.0-beta.1；引擎：0.4.0。下文保留各阶段实际环境和结果，旧版本数字是当时的历史记录。阶段6正式模型评测与人工评审尚未执行。

包版本：0.4.0-beta.1；运行引擎：0.3.1；执行日期：2026-10-13。

本记录只报告此公开包的实际检查。原开发版本的历史测试未作为本包完整验收结果；本次合成测试不代表真实项目准确率或覆盖全部审计准则。

## 1. 发布范围与来源

从原运行技能按文件选取入口、11份Python脚本、参考方法与UI元数据，再在公开目录完成通用化修改。原技能文件保持不变，公开包中的11份运行脚本与本次复制前基线相同。没有复制真实业务原件、旧项目台账、历史归档、外部仓库副本或旧测试答卷。

公开方法中的历史业务数值已移除或替换为合成例子；测试的单位、角色、金额、日期及制度均从零构造。没有将原项目材料仅换文件名后作为公开样例。全部16份任务与业务测试输入在独立会话评测前冻结，见 [input-sha256.json](tests/input-sha256.json)。

文件审查包括说明和源代码、本机路径与密钥模式扫描、OOXML内部XML/属性、PDF元数据与原页、PNG可见内容及元数据。扫描只能发现所设模式；本包的发布选择和实际内容检查共同支持脱敏结论，不声称通用扫描器能发现一切敏感信息。官方准则只提供链接和方法性概括，不随包分发全文；PDF样例字体许可单独保留。

## 2. 程序与环境

实际运行环境：macOS。程序测试分别在Python 3.12.14 / pypdf 6.10.0和Python 3.14.3 / pypdf 6.12.1执行，两组均使用openpyxl 3.1.5；PDF原页查看使用Poppler。技能结构校验通过。安装说明中的 `begin` / `inspect` 示例已在包外临时目录执行，读取3份财务合成材料；它只完成准备，不表示业务核查通过。

自动程序验证：上述两组环境均为 **8项通过，0项跳过**。实际执行了begin、inspect、check-assessment、finalize、validate和update，包括提交两轮后回查原轮次。命令如下：

```sh
python3 -B tests/test_public.py
python3 -B tools/check_release.py
```

这些测试检查来源与快照、原精度计算、引用和观察记录约束、未读状态及增量历史。自动测试不会声称自己实际查看图像，也不会将数据结构校验等同于审计判断正确。

发布检查另在隔离副本验证：正常包通过；改写文件、增加未登记文件、删除必要参考分别被拒绝。检查脚本排除版本库的 `.git` 元数据，不将虚拟环境或业务成果纳入发布清单。

## 3. 独立上下文的会话演练

采用未继承开发会话的新会话，只提供技能及4份请求和对应 `sources/`；没有向执行者提供预期文件、生成器或其他答卷。执行者完成 [forward-response.md](tests/forward-response.md)，主会话再按 [expected.json](tests/expected.json) 和实际查看记录逐项比对，**12项均符合本次合成场景的预设判断边界**。这是模型会话及主会话复核，不是专业人员的人工审定。

隔离限制：执行者为查看并发状态，调用过一次代理状态工具，该工具自动显示其他代理的完成摘要；执行者报告未读取预期文件、生成器或其他会话正文，也未将状态摘要作为业务证据。因此本记录作为一次独立上下文的功能演练，**不宣称严格盲测通过**。后续严格盲测应在无其他任务状态可见的隔离环境执行；不能以本次12项吻合推算泛化准确率。

| 场景 | 断言数 | 实际结果 |
|---|---:|---|
| 财务报表 | 4 | 解释报表层重分类；期末80,900.00元，无重复扣减；保留定性重要性限制；区分独立复算与Excel空缓存 |
| 内控合规 | 3 | 制度不等于运行有效；实际看清申请勾选与批准空框；未将定向样本机械外推或把17笔未查交易写成违规 |
| 合同专项 | 3 | 实际看图采用补充到期日；识别127.35元明细；保留860.40/860.04冲突、缺页及收款限制 |
| 任期责任 | 2 | 任后损失不直接排除任内影响；保留单位缺陷和损失事实，未自动认定个人责任 |

执行者读取全部16份输入，实际打开1张PNG和2份PDF的全部3个已提供页，分开读取工作簿公式与缓存并执行Decimal复算。主会话另查看相同图像确认可辨。未提供的收款凭据第2页没有被写成已看；未建立业务台账、未执行现场或外部程序、未发表整体审计意见。

合成材料将关键背景明确写出，主要验证读取、计算和结论边界；它不是隐蔽舞弊、大型账簿、复杂行业或真实审计意见的能力测试。

## 4. 准备中发现并解决的问题

合成合同PDF初版存在文字可提取而首张渲染页空白的问题。首次会话评测因此中止，未作为有效验收计入。生成器改为嵌入字体，实际渲染确认可见后重新冻结输入，并启用新的独立会话；修正没有改变预期审计结论。字体说明见 [tests/README.md](tests/README.md)。

独立发布复核还发现安装示例将虚拟环境建在包内会触发额外文件校验，以及单独复制技能目录会漏带根许可证。现已将示例环境移到包外，并在技能目录内保留同一份 Apache 2.0 许可。原开发目录未因此改变。

## 5. 未验证范围

- 没有统计真实业务准确率，没有证明零幻觉或准则完整符合性。
- 没有完成跨行业、全部内审/外审程序、真实函证/监盘或审计意见签发的验证。
- Linux/WSL及其他Python/依赖组合未运行本轮测试；原生Windows台账写入不支持。
- 本轮没有验证加密损坏文件、复杂宏/外链、全部Word修订布局、彩色富文本、手写签名及所有图片格式。
- 自动字段校验无法证明会话真实看图或正确理解；实际原件阅读和专业复核仍须执行。
- 发布完整性清单不涵盖用户后来创建的业务项目；分享这些成果时须另行检查路径、原文与敏感信息。

## 6. 0.5.0-beta.1 开发中：阶段 1 实测记录（2026-11-04）

本节单独记录阶段1，不覆盖或改写前述2026-10-13历史结果。台账schema 1/2和引擎0.3.1保持；renderer 7为新的导出版本。新增合成旧台账夹具于2026-11-04单独冻结，未改变原input-sha256.json。

- 实际环境：macOS 26.6.2 arm64，Python 3.14.3，pypdf 6.12.1，openpyxl 3.1.5；LibreOffice 26.8.0.3。
- 已执行第一轮 `python3 -B tests/test_public.py`：22项通过、0项跳过；覆盖旧renderer 1–6/schema1/2的原字节校验、显式portable、真实DOC/XLS转换和Poppler页图生成、原件匹配、锁/持久化/恢复与文件名边界。随后增加Windows真实占用测试并再次执行完整测试：23项中22项通过、1项跳过（Windows真实文件占用测试在POSIX不适用），0失败、0错误。
- macOS沙箱内LibreOffice真实转换返回1且无输出，此次为失败尝试；相同转换在沙箱外已实际通过，不将沙箱内失败计为成功。textutil没有独立工具版本输出，记录macOS系统版本及可执行文件SHA256，不把帮助文字伪装成版本号。
- `python3 -B tools/check_release.py --write-manifest`已实际执行并通过（66份文件）；普通校验也已执行并通过，未写清单。
- Windows/Linux与七组GitHub Actions已实际执行，结果及日志链接见下表；缺系统工具的skip不算已验证其转换或渲染能力。
- 未验证：Windows/Linux上的真实LibreOffice转换及Poppler渲染；NFS/SMB共享盘锁与断电恢复；全部第三方转换器、宏、签章或格式保真。本阶段自动测试不证明语义复核正确或真实业务准确率。

阶段1首轮CI已实际执行：[运行41768979956](https://github.com/KaguraNanaga/audit-skill/actions/runs/41768979956)，代码1a82164f。macOS3.11/3.12及Ubuntu3.11/3.12共4组成功；Windows3.11/3.12和Ubuntu3.14共3组失败。失败分别来自测试持锁时读取Windows锁区，以及测试修改全局sys.platform导致Linux/Python3.14尝试导入macOS的_scproxy。修正为持锁时只读诊断sidecar、释放后才检查锁文件内容，并仅模拟转换器PLATFORM常量。修正后的第二轮CI已实际执行，结果如下，不把失败轮记为通过。首轮七组发布清单校验均通过。

第二轮：[运行41769277314](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314)，代码261a1c85，七组均成功。实际日志中，全部环境使用pypdf 6.21.4、openpyxl 3.1.5；全部七组的普通发布清单校验通过（66份文件）。

| 实际系统 | Python | 通过 | 跳过 | 失败/错误 | 日志 |
|---|---|---:|---:|---:|---|
| macOS 26.6.2 arm64 | 3.11.9 | 20 | 3 | 0/0 | [job126374903261](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903261) |
| macOS 26.6.2 arm64 | 3.12.10 | 20 | 3 | 0/0 | [job126374903128](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903128) |
| Ubuntu runner（Linux 7.0.0/glibc2.43） | 3.11.17 | 20 | 3 | 0/0 | [job126374903535](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903535) |
| Ubuntu runner（Linux 7.0.0/glibc2.43） | 3.12.15 | 20 | 3 | 0/0 | [job126374903251](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903251) |
| Ubuntu runner（Linux 7.0.0/glibc2.43） | 3.14.9 | 20 | 3 | 0/0 | [job126374903187](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903187) |
| Windows 10.0.26100 | 3.11.9 | 21 | 2 | 0/0 | [job126374903276](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903276) |
| Windows Server 2025 10.0.26100 | 3.12.10 | 21 | 2 | 0/0 | [job126374903253](https://github.com/KaguraNanaga/audit-skill/actions/runs/41769277314/job/126374903253) |

全部CI缺少LibreOffice与Poppler，两项真实工具测试因工具不可用而跳过；POSIX另跳过原生Windows共享占用测试。Windows的真实系统锁、sidecar读取、超时、进程异常释放、目标文件真实占用后重试、设备保留名及尾随点/空格逐文件failed、中文空格长路径、完整两轮提交/校验/导出均已执行通过。测试并未通过静默skip来隐藏工具已存在却运行失败的情况。

本地最终完整测试另已实际执行：macOS/Python3.14.3为22通过、1跳过（仅Windows专属测试），0失败/0错误；两项真实工具测试通过。技能quick_validate及git diff --check也已实际通过。阶段1未新增Python依赖，无新增网络、遥测或上传接口；CLI import-web仍只导入用户实际取得的本地工具响应。

收尾复核还将“请求主稿本身为Windows非法文件名”的分支纳入既有文件名测试：应逐文件failed、主稿未选定并说明原因，其余材料照常处理。此分支通过本地定向测试；新增分支所在最终提交另由CI复验。

## 7. 阶段 1.5：目录迁移实测（2026-11-04）

调整前基线：阶段1验收提交a0cb3714fa7a9d543eb1af0b9b436c38204a73b9对应的工作区，修改前按原66份发布清单逐文件验证并复制到包外临时目录。本地HEAD仍为旧发布，未将其误用为本阶段基线。

实际环境沿用本机macOS26.6.2 arm64/Python3.14.3，pypdf6.12.1、openpyxl3.1.5、LibreOffice26.8.0.3。已执行：

- 提供EVIDENCE_REVIEWER_BASELINE后运行 `python3 -B tests/test_public.py`：31项中30通过、1跳过（仅Windows专属共享占用测试），0失败/错误。包含真实LibreOffice转换和Poppler渲染，执行环境为沙箱外。
- 单独运行 `python3 -B tests/test_platform.py`：15项中14通过、1跳过（Windows专属测试），0失败/错误。
- `python3 -B tests/test_structure.py`：8项通过，0跳过、0失败/错误。实际核对了import以外的AST不变、迁移参考原文及SKILL旧章节保留、prepare入口help不变、旧schema1/2项目继续inspect/validate/update/export，以及已提交renderer7导出删除后的原字节重建。
- `python3 -B tools/compare_structure.py --baseline BASELINE_DIRECTORY`：实际运行调整前后的begin/inspect，财务3文件33单元、合同4文件11单元、内控3文件12单元、任期2文件9单元，共12份输入65单元，全部字段比较一致。
- 对照没有删除任何字段；在隔离测试进程固定L.uid序列和L.now时钟，仍比较所有ID引用及时间字段；仅规范化各自项目绝对根前缀。原件指纹、正文、locator、公式、缓存、状态、限制、工具/引擎版本均未屏蔽。
- `python3 -B tools/check_links.py`：77个本地链接通过，0错误；负向用例能拒绝缺失文件、越界路径、缺失锚点和未定义参考。外部URL不联网验证。
- `python3 -B tools/check_release.py --write-manifest`及不带写参数的普通校验均通过：73份文件。quick_validate、git diff --check通过。原冻结输入、既有stage1夹具及固定旧提交的生成器未改写。

阶段1.5 CI已实际执行，结果如下；上列本地结果不与CI计数混合。schema、引擎、读取器和renderer版本保持，不新增Python依赖或运行脚本联网路径；维护者指南不随skill子目录分发。

阶段1.5实际CI：[运行41787553785](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785)，提交17d5f247，七组全部成功。全部使用pypdf6.21.4/openpyxl3.1.5，31项完整测试中的实际通过/跳过如下：

| 系统 | Python | 通过 | 跳过 | 失败/错误 | 日志 |
|---|---|---:|---:|---:|---|
| macOS26.6.2 arm64 | 3.11.9 | 28 | 3 | 0/0 | [job126433069331](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069331) |
| macOS26.6.2 arm64 | 3.12.10 | 28 | 3 | 0/0 | [job126433069386](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069386) |
| Ubuntu/Linux7.0.0/glibc2.43 | 3.11.18 | 28 | 3 | 0/0 | [job126433069313](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069313) |
| Ubuntu/Linux7.0.0/glibc2.43 | 3.12.15 | 28 | 3 | 0/0 | [job126433069432](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069432) |
| Ubuntu/Linux7.0.0/glibc2.43 | 3.14.9 | 28 | 3 | 0/0 | [job126433069225](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069225) |
| Windows10.0.26100 | 3.11.9 | 29 | 2 | 0/0 | [job126433069299](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069299) |
| Windows Server2025 10.0.26100 | 3.12.10 | 29 | 2 | 0/0 | [job126433069809](https://github.com/KaguraNanaga/audit-skill/actions/runs/41787553785/job/126433069809) |

七组均实际单独执行test_platform.py（Windows13通过/2跳过，POSIX12通过/3跳过）、test_structure.py（每组8通过/0跳过）、四组合成输入前后begin/inspect对照、77个本地链接检查及73份发布清单校验。不存在因缺基线而跳过结构对照的情况。CI缺LibreOffice/Poppler，两项真实工具测试明确skip；POSIX另跳过Windows专属共享占用。此限制延续阶段1，不推断跨平台转换/渲染保真。

## 8. 阶段 3：可选OCR定位层（2026-11-05）

当前环境：macOS26.6.2 arm64、Python3.14.3、pypdf6.12.1、openpyxl3.1.5；本机没有Tesseract及rapidocr-onnxruntime包装库，已有onnxruntime1.26.0不等于OCR后端可用。旧包1.4.4的实际下载检查显示Requires-Python<3.13，已在requirements-ocr.txt加入解释器条件，并实际检查了其wheel中三个本地ONNX模型和配置文件；没有强行忽略Python版本要求安装。

阶段1.5基线在修改前按73份发布清单实际验证并复制至包外临时目录。历史结构对照使用固定阶段1与阶段1.5两份基线；当前实现另执行旧账兼容和历史字节测试，不声称新功能与旧CLI输出全字段相同。

- 完成代码及文档后，沙箱外实际执行`python3 -B tests/test_public.py`：41项，38通过、3跳过、0失败/错误。跳过为Windows专属共享占用及两个缺后端的真实OCR测试；LibreOffice真实转换和Poppler真实渲染通过。
- `tests/test_ocr.py`提供阶段1.5基线后单独执行：10项，8通过、2真实后端测试跳过，0失败/错误。结构测试使用明确标注的模拟OCR块及合成观察，不作为实际识别或实际看图结果。
- 已执行来源链、search警示、仅OCR的check-assessment/finalize拒绝、OCR观察伪装拒绝、不同页图哈希不能替代、失败继续、结果文件及来源篡改拒绝、后轮追加OCR不进入旧轮、真实进程中断及recover、旧schema1/2继续操作及显式提交升级测试。
- `python3 -B tools/check_release.py --write-manifest`通过84份文件；quick_validate及git diff --check实际通过。清单普通校验将在收尾再次执行。
- 开发中完整测试先有一次沙箱内LibreOffice退出1（原有环境限制）；随后沙箱外一轮因OCR文档链接尚未写入而失败。补齐文档后的上述完整测试通过，不将失败尝试记为成功。
- 本机真实OCR：未验证，两个后端测试明确skip。Windows/Linux真实OCR、识别准确率、复杂版式、中文识别准确率及多帧图片：本机未验证。CI实际结果待执行后追加；不存在预填通过。

阶段3首轮CI已实际执行：[41936507008](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936507008)，提交aefed414。可选OCR任务中RapidOCR实际识别通过；Tesseract实际识别得到“SYNTHETIC AMOUNT 125,45”，与合成原图123.45不一致，使原来要求数字123正确的测试失败。原图及冻结指纹保持，改为验证AMOUNT定位标识、bbox/来源链、search警示和仅OCR不可提交的实际流程；金额识别错误作为能力限制保留，不把测试调整宣称为数值准确率提高。实际环境为Ubuntu26.04.1/Python3.12.15，Tesseract5.5.0（chi_sim+eng）、RapidOCR1.4.4、onnxruntime1.31.1、opencv-python5.0.0.93、numpy2.5.4。两后端的bbox/置信度结构实际返回；本轮没有中文识别准确率评测。

收尾另实际测试新schema显式portable视图：选择renderer8保留OCR警示，旧轮仍用renderer7；原台账/历史导出字节不改写。再次完整测试结果及最终CI在实际执行后追加。

第二轮CI实际完成：[41936738706](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706)，提交0cca05d2，八组均成功。基础七组完整测试各41项；独立可选OCR任务真实执行两个后端的识别、登记、search标注和OCR-only拒绝流程，2通过、0跳过、0失败/错误。

| 实际环境 | Python | 完整测试通过/跳过 | 日志 |
|---|---|---|---|
| macOS arm64 | 3.11.9 | 36 / 5 | [126946981151](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981151) |
| macOS arm64 | 3.12.10 | 36 / 5 | [126946981062](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981062) |
| Ubuntu | 3.11.18 | 36 / 5 | [126946981227](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981227) |
| Ubuntu | 3.12.16 | 36 / 5 | [126946981184](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981184) |
| Ubuntu | 3.14.9 | 36 / 5 | [126946981262](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981262) |
| Windows | 3.11.9 | 37 / 4 | [126946981026](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981026) |
| Windows | 3.12.10 | 37 / 4 | [126946980851](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946980851) |
| Ubuntu可选OCR | 3.12.16 | 实际双后端 2 / 0 | [126946981161](https://github.com/KaguraNanaga/audit-skill/actions/runs/41936738706/job/126946981161) |

基础矩阵缺LibreOffice、Poppler及两个OCR后端；POSIX另跳过Windows专属测试，未计作通过。各基础任务单独平台测试Windows13/2、POSIX12/3，结构测试均8/0；固定阶段1→1.5的实际begin/inspect对照、本地链接及84份发布清单均通过。首轮失败及错误识别限制仍保留。真实OCR仅验证本合成英语字形的定位流程，不推断中文/金额准确率或其他系统后端支持。当前不保证多帧图片、未知页图绑定、全部图像格式或复杂版式。

最终收尾另加入原单元不可改写、schema降级拒绝、仅接收本地图像签名（拒绝文件列表/URL）和两份历史基线清单验证；本机重复完整回归记录在最终验收中，未改冻结输入。普通发布校验、离线链接检查（86个）、技能quick_validate及git diff --check已实际通过。

最终本机完整测试已实际再次执行（包含上述收尾校验）：41项，38通过、3跳过、0失败/错误；同样提供两份经过清单校验的固定历史基线。普通发布检查84份通过、86个链接通过、quick_validate及git diff --check通过。跳过范围未变，不把缺后端记作实际识别。

## 9. 阶段 4：表查询与评估骨架（2026-11-05）

阶段3基线在修改前按84份清单复制并校验，固定提交ba198b5b72db688529093a04e2f7f806b90544d8。历史结构对照仍固定阶段1→1.5，不将新行为误计为结构迁移。实际环境沿用本机macOS26.6.2 arm64/Python3.14.3、pypdf6.12.1、openpyxl3.1.5及LibreOffice26.8.0.3。

- 已提供三份固定基线，沙箱外执行`python3 -B tests/test_public.py`：51项，48通过、3跳过、0失败/错误，耗时22.322秒。跳过为Windows专属共享占用与缺少两OCR后端；真实LibreOffice及Poppler测试通过。
- 表查询先单独执行8项（当时尚未加原生Excel日期测试）：8通过、0跳过，包含旧/新XLSX读取器逐单元字段一致对照和schema3/renderer8旧账兼容。之后增加的日期测试已进入上述完整51项并通过。scaffold单独1项通过。
- 50,000行序时账实际完整扫描并用独立整数分期望核对命中数及总额；终端仅3行预览且JSON小于15,000字符，完整命中行保存结果文件。金额原精度、公式缺缓存失败、全部筛选、分组、计数、跨CSV/TSV及XLSX来源、时间保留、查询引用、防篡改、项目移动及历史字节重建均已执行。
- 新夹具于2026-11-05单独冻结；生成器在临时目录重建与冻结指纹逐项一致，原冻结输入不修改。开发首轮发现生成器没有自动创建临时目录父级，导致确定性重建测试失败；修正父级创建后通过，未改夹具字节。首轮未提供阶段3基线的两项对照skip，正式验收已提供基线并实际执行。
- `tools/check_release.py --write-manifest`通过98份文件，离线链接检查105项通过，quick_validate及git diff --check通过。普通发布校验与CI结果在实际执行后追加。
- 未验证：真实业务准确率、业务总体完整性、全部复杂/合并表头、任意Excel格式和超大规模内存上界。查询使用声明的表头与单位，不执行公式重算、不自动识别异常或形成审计结论。

首轮实际CI：[41947078668](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947078668)，提交a36f00f8。macOS/Ubuntu五组及可选双OCR任务成功，Windows3.11/3.12失败。Windows失败为临时重建的预期JSON使用CRLF，冻结文件为LF；改为生成器显式UTF-8/LF，并明确ZIP平台元数据，冻结输入和指纹不改。修正后本机生成器确定性定向测试通过，跨平台重验待实际执行，不把失败轮记为通过。

收尾记录工具实际版本：TableQuery保存当前Python版本，XLSX保存实际openpyxl版本；新update记录当前读取器及Python版本，原SourceVersion及历史run版本不改。结果指纹只包含保存文件的内容哈希，不含随机查询目录，同项目同规格重跑结果指纹一致。上述代码的本机完整回归已实际执行：51项，48通过/3跳过、0失败/错误（25.927秒）；之后仅生成器LF修正另有定向测试通过。普通发布校验98份、105个链接、quick_validate、git diff --check均通过。

第二轮CI已实际完成：[41947520805](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805)，提交233082d9，八组均成功；Windows的LF/ZIP确定性重建修正通过，未修改原冻结输入。基础矩阵每组51项，实际结果如下：

| 环境 | Python | 通过/跳过 | 日志 |
|---|---|---|---|
| macOS | 3.11.9 | 46 / 5 | [126983298553](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298553) |
| macOS | 3.12.10 | 46 / 5 | [126983298681](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298681) |
| Ubuntu | 3.11.18 | 46 / 5 | [126983298633](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298633) |
| Ubuntu | 3.12.15 | 46 / 5 | [126983298698](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298698) |
| Ubuntu | 3.14.10 | 46 / 5 | [126983298768](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298768) |
| Windows | 3.11.9 | 47 / 4 | [126983298625](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298625) |
| Windows | 3.12.10 | 47 / 4 | [126983298557](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298557) |
| Ubuntu可选OCR | 3.12.16 | 实际双后端 2 / 0 | [126983298300](https://github.com/KaguraNanaga/audit-skill/actions/runs/41947520805/job/126983298300) |

全部0失败/错误。基础任务仍缺LibreOffice/Poppler及两OCR后端，POSIX另跳过Windows专属测试；缺工具不计通过，实际双OCR在独立任务执行。七组单独平台测试Windows13/2、POSIX12/3，结构测试均8/0；固定结构前后对照、本地链接及98份发布清单校验均通过。

最终本机完整测试亦已执行：51项，48通过/3跳过、0失败/错误（23.773秒），包含最终来源版本校验与生成器修正。普通发布校验98份、105个链接及git diff --check通过。另实际逐文件比较原冻结输入、阶段1/3夹具与清单，共22份保持原字节；新阶段4夹具按独立冻结清单校验。新能力未新增依赖或运行联网路径。

## 10. 补齐阶段 2：OFD/WPS/XML（2026-11-05）

修改前核对阶段4验收提交56095f85541e269d97259d76dddbe3b195a555fa的98份包外基线文件，全部匹配清单。阶段5尚未改写；其规则基线将在阶段2验收后改用阶段2最终提交。schema1/2/3、引擎0.4.0及renderer9保持，读取器升至readers-1.3。

实际环境：macOS26.6.2 arm64/Python3.14.3、pypdf6.12.1、openpyxl3.1.5；本机LibreOffice沿用26.8.0.3。提供阶段1、1.5、3、4四份固定历史基线后，在允许启动本机系统工具的沙箱外运行：

- `python3 -B tests/test_public.py`：64项，60通过、4跳过、0失败/错误（33.175秒）。跳过为Windows专属共享占用、缺少RapidOCR、缺少Tesseract、缺少真实OFD渲染适配器。跳过不计通过。
- `python3 -B tests/test_platform.py`：15项，14通过、1跳过、0失败/错误（7.248秒）。真实LibreOffice DOC/XLS与Poppler执行通过，Windows专属测试跳过。
- `python3 -B tests/test_structure.py`：8项，8通过、0跳过、0失败/错误（2.632秒）。阶段1→1.5固定结构对照和旧schema1/2命令/历史字节检查实际执行。
- 新增13项格式测试已包含在完整64项中：12通过、真实OFD渲染1项跳过。实际LibreOffice先从合成源导出MS兼容DOC/XLS/PPT二进制，再分别用.wps/.et/.dps路径转换成功；模拟转换/适配器测试不计作真实工具结果。
- 旧阶段4未支持的OFD项目在不重新导出时validate通过，inspect保留旧未读单元；显式reparse后保留同原件哈希、新版本、旧轮单元与renderer9原字节重建。原件跨转换器测试确认不会重新调用读取器或制造材料变更。
- 离线链接检查117项通过；逐字节比较24份旧冻结输入及其4份清单，全部与阶段4验收包一致。新OFD/XML/PPTX输入2026-11-05独立冻结，临时根重建一致。

开发定向运行中，本机沙箱内LibreOffice退出1；沙箱外已实际通过，未将沙箱失败记作不可用或成功。真实OFD渲染、原生WPS生产器各变体、签名/发票真实性及真实业务判断准确性均未验证。OFD适配器模拟只验证文件/引用契约，不证明图像确实渲染自OFD；无适配器时不生成或声称有页图。

本机`tools/check_release.py --write-manifest`及普通`tools/check_release.py`均通过110份文件；117个本地链接、技能quick_validate及git diff --check实际通过。阶段2未新增运行联网、遥测或上传路径，未改变schema或历史renderer实现。

首轮实际CI：[41952200613](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613)，提交b377f0e01dbfe4b02bfe93131aa0a00ce7c8f263，九组任务全部成功。各基础矩阵均完整执行64项，结果如下：

| 环境 | Python | 通过/跳过 | 实际日志 |
|---|---|---|---|
| macOS arm64 | 3.11.9 | 57 / 7 | [126998537929](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537929) |
| macOS arm64 | 3.12.10 | 57 / 7 | [126998538044](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998538044) |
| Ubuntu | 3.11.18 | 57 / 7 | [126998537986](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537986) |
| Ubuntu | 3.12.15 | 57 / 7 | [126998537898](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537898) |
| Ubuntu | 3.14.9 | 57 / 7 | [126998537937](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537937) |
| Windows | 3.11.9 | 58 / 6 | [126998538033](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998538033) |
| Windows Server | 3.12.10 | 58 / 6 | [126998538034](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998538034) |
| Ubuntu双OCR | 3.12.15 | 2 / 0 | [126998537524](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537524) |
| Ubuntu LibreOffice | 3.12.15 | 1 / 0（含三条路径） | [126998537895](https://github.com/KaguraNanaga/audit-skill/actions/runs/41952200613/job/126998537895) |

全部0失败/错误。基础矩阵的缺工具跳过为旧DOC/XLS实际转换、Poppler、RapidOCR、Tesseract、WPS实际转换、实际OFD渲染；POSIX另跳过Windows专属共享测试。Windows的保留名failed后继续、独立锁sidecar和新增夹具确定性均实际通过。独立平台测试Windows13通过/2跳过、POSIX12通过/3跳过；结构测试各8通过/0跳过。固定历史对照、117个链接及110份发布清单七组均通过。

Office任务实际使用LibreOffice26.2.6.3（620 Build:3），1项测试包含.wps/.et/.dps三条MS兼容二进制转换路径，未跳过；不是原生WPS生产器兼容性评测。独立OCR任务实际Tesseract5.5.0（chi_sim+eng）、RapidOCR1.4.4/onnxruntime1.31.1，两项真实识别和来源/拒绝流程通过；未扩大为OCR准确率结论。OFD文本与适配器契约测试通过，真实OFD图像渲染仍未验证。


## 11. 阶段 5：文档改写及行为抽查（2026-11-05）

规则基线为阶段2最终验收提交8cd924eb478bc670f82ad0f93e8f59cfee1d3162。改写前先保存SKILL与全部references的470个原段/表行/接口块，再拆分为1425个句级或完整接口条目；[逐条对照](docs/rewrite-rule-mapping.md)标明唯一合并位置及3类存疑，没有删除规则或变更运行行为。[完整SKILL diff](docs/SKILL.stage5.diff)与基线逐行比较。SKILL总52行、description154字符；SKILL和16份references合计57399→55763字符，下降1636（2.85%）。

### 本机实际执行

macOS 26.6.2 arm64、Python 3.14.3、openpyxl 3.1.5、pypdf 6.12.1、Pillow 12.2.0；该解释器未安装reportlab，未重建旧夹具。测试通过包外执行包装器设置固定阶段1/1.5/3/4基线，运行命令本体如下；LibreOffice实际转换在允许启动本机应用的环境执行。

| 命令/检查 | 实际结果 |
|---|---|
| python3 -B tests/test_public.py | 64项：60通过、4跳过、0失败/错误；33.854秒 |
| python3 -B tests/test_platform.py | 15项：14通过、1跳过；7.489秒 |
| python3 -B tests/test_structure.py | 8项：8通过、0跳过；2.894秒 |
| python3 -B tools/check_links.py | 1549个本地链接通过；外部网站不由此脚本验证 |
| python3 -B tools/check_release.py --write-manifest及普通检查 | 113份发布文件通过 |
| skill-creator quick_validate.py | Skill is valid |
| git diff --check | 通过 |
| 与阶段2验收包逐字节比较 | 81份运行脚本/测试/全部夹具及冻结清单/依赖/CI配置/.gitattributes完全一致；唯一工具修改为check_release维护文档白名单 |

完整测试4个跳过分别为：非Windows主机不能执行原生Windows占用测试；未安装rapidocr-onnxruntime；没有tesseract；没有实际OFD渲染适配器。独立platform的1个跳过为同一Windows测试。跳过没有计入通过；OFD契约模拟测试不等于真实渲染验证。首轮环境清单读取未安装的reportlab元数据报PackageNotFoundError，改为如实登记未安装后重新取得环境记录；这不是回归测试失败。

### 文档改写后的行为抽查

两个新会话未继承开发过程及答案，分别只收到重写skill和原有financial/controls的sources/及request.md；业务输入逐字节不变。宿主提供的文件/图像工具可用，financial按宿主要求另读只读电子表格技能。两案都实际执行完整台账流程，并回读导出。[实际调用、输出、结论及失败日志](docs/stage5-behavior-check.md)以维护文档保存；发布时仅替换临时目录和用户目录前缀，保留替换前/后哈希。

financial：实际inspect33个单元、9项Decimal复算；先检查原件及公式/缓存，再begin、inspect、select-main、search、scaffold，填写判断并提交。首次check-assessment的Finding关系方向错误被拒，修正后校验通过；一次交付脚本编排语法错误发生于shell执行前，重试成功。controls：实际inspect12个单元，打开PNG全图、写原页观察，保留其余17笔未测试；完整台账链通过。首次长输出显示截断后补读、自动生成19份字节码后清理的过程均记录。

两案没有省略台账关键步骤；读取原件/看PNG提前于begin执行。此次未覆盖OCR、OFD/WPS/XML、table-query、大表、跨轮update、对抗性指令、万元精度情形或外部准则查询，未为触发步骤修改案例。抽查时SKILL与最终一致；其后4份参考补明原有条件的精确差异列于记录，补明处没有重新做独立会话验证。此为一次行为抽查，不是准确率、稳定性或全能力验证；执业人员人工评审未执行。

README节选由financial实际台账导出的review.md按F2整行读取，双语README保留同一原文，标注合成材料、非真实业务；原文件哈希、run_id及选取行号列于行为记录。Claude Code个人及项目安装路径于2026-11-05对照官方文档核实；实际安装及运行未验证。OpenAI安装路径同期对照官方文档复核。包版本未提前升级；阶段6未执行。

### 阶段5 CI

[实际运行41956626181](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181)，提交5530f9c86971270f0c6b11f9b9d25518f65e61ce，9个任务全部成功。逐项读取实际任务日志；通过与跳过分列：

| 实际任务 | public通过/跳过 | platform通过/跳过 | structure通过/跳过 |
|---|---|---|---|
| [macos-latest / Python 3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012972048) | 57/7 | 12/3 | 8/0 |
| [macos-latest / Python 3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012972007) | 57/7 | 12/3 | 8/0 |
| [ubuntu-latest / Python 3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012972008) | 57/7 | 12/3 | 8/0 |
| [ubuntu-latest / Python 3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012971954) | 57/7 | 12/3 | 8/0 |
| [ubuntu-latest / Python 3.14](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012971805) | 57/7 | 12/3 | 8/0 |
| [windows-latest / Python 3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012971969) | 58/6 | 13/2 | 8/0 |
| [windows-latest / Python 3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012972097) | 58/6 | 13/2 | 8/0 |

macOS实际为26.6.2 arm64/Python3.11.9、3.12.10；Ubuntu为Linux7.0 Azure/glibc2.43/Python3.11.17、3.12.16、3.14.10；Windows为build26100/Python3.11.9、3.12.10。基础矩阵缺LibreOffice、Poppler、双OCR和真实OFD适配器，显式skip；POSIX另skip原生Windows共享锁测试，Windows已实际执行该项。

[独立OCR任务](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012971541)：2通过/0跳过，实际Tesseract5.5.0、chi_sim+eng及RapidOCR1.4.4/ONNXRuntime1.31.1，缺后端会失败。[独立LibreOffice任务](https://github.com/KaguraNanaga/audit-skill/actions/runs/41956626181/job/127012971820)：1通过/0跳过，实际LibreOffice26.2.6.3，覆盖WPS/ET/DPS三条MS兼容二进制转换路径；不扩大为原生WPS全部变体已验证。

7组矩阵均通过独立平台/结构测试、4案例结构迁移对照、本地链接1549项及发布清单113份检查。真实OFD渲染仍未验证。本节回填真实结果后仅更新维护记录和发布清单，最终提交的后续CI状态另由交付链接核对，不预填尚未执行的结果。

## 阶段6评测协议

本阶段交付案例、隔离预期、记录模板及协议，**不填写未执行的模型表现或人工意见**。程序回归和 PDF 作者视觉检查不能替代这项评测；阶段5的两案一次行为抽查也不折算成这里的运行次数。详细材料与真实渲染记录见 [tests/README.md](tests/README.md)，预期见 [tests/expected/stage6.json](tests/expected/stage6.json)。

1. **冻结条件。** 管理员固定发布提交、包/引擎版本、skill 指纹、案例冻结清单、模型及配置、系统提示、工具/语言包/渲染器版本、系统环境、时间/上下文/调用预算。每案至少 3 次独立新会话，共至少 18 次；相同设置下重复，差异配置另分组。预期答案仅供评分方，执行者看不到此协议中的题型描述、生成器、开发历史或此前答卷。发现型 stage6-06 不提供复核稿，不把它当作已具备专用发现算法的证明。
2. **隔离输入。** 用 `prepare_evaluation.py` 逐案准备仅有 skill + request + sources 的输入；核对复制哈希。管理员在独立容器/工作区和新会话限制可见目录及工具权限，执行者不能读取仓库、expected、管理员映射、其他会话/代理状态、历史摘要或外网答案。打包工具不是沙箱。若宿主无法落实隔离，记录实际可见面、泄漏与限制，将该次标为“非严格隔离”，不冒称盲测、不混入严格隔离汇总。
3. **执行与留痕。** 按 request 完成复核工作草稿；观察实际流程，包括 begin → inspect → scaffold → check-assessment → finalize → validate → export。按材料需要使用 search、看原页/observations、OCR、table-query；不为触发命令修改案例。完整保存实际调用、参数、stdout/stderr、退出码、失败及修复、查看的原页及哈希、查询规格/结果/指纹、assessment、台账与导出。大表 inspect 全量输出可保存为文件后选读；不得将完整输出塞入上下文后声称进行了有界查询。区分脚本抽取/扫描、宿主实际读取、原页视觉核对三种覆盖。缺工具写 failed/tool_unavailable 或明确未覆盖，不静默跳过当作成功。
4. **保留所有运行。** 时间耗尽、工具失败、拒绝提交和未完成均保留；明确运行内修复与新一次重跑，不只选择最好答卷。以 [evaluation-record.template.json](tests/evaluation-record.template.json)记录步骤、跳步、未读范围和未覆盖能力。OCR 后端、OFD 渲染未实际调用或缺失时写未验证；不能拿接口模拟测试替代这次真实调用。指令性材料用任务、证据或限制字段留痕；单位解释属于主张，需要核实。
5. **盲评副本。** 由未参与执行的管理员随机分配 blind_id、打乱评分顺序；评分者只获得所需案例、隔离预期、匿名化答卷及核查日志。评分时隐去**运行序号和 skill 版本**，包括元数据、路径、版本命令输出和日志中可识别的版本片段；用固定占位符替换，不删掉失败、证据或判断内容。原始文件只读保存；另保存脱敏字段/位置、原文件与副本哈希及恢复映射。映射和 administrator 字段不向评分者开放。无法排除版本泄漏则记录，不能称为完成盲评。
6. **逐项评分。** 对每个 must_mention ID 记录“完整/部分/缺失”及实际引文和 locator：完整需要正确事实、所需关联、计算/视觉依据和适当边界；部分表示识别方向但缺关键支持；缺失含错误或未执行。逐项判定允许结论范围及 forbidden_conclusions 是否被肯定采纳；引用或反驳错误语句不算采纳，不使用关键词黑名单。另列事实检出数、无依据问题数（含真阴性误报）、来源可追溯性、OCR/原页边界、覆盖诚实性、流程遵守和限制披露。合理暂缓可以满足证据边界，但不冒充完整检出；stage6-06 四类检出与两个干扰项分别计分。出现禁止结论单独标记，不用其他得分抵消。六个定向合成案例不代表业务总体，不外推真实准确率。
7. **人机分开。** 模型评分记录模型/配置与原始评分输出；每个案例的至少一次运行须由具有相应审计经验的人员实际评审，至少 6 份人工评审记录，填写角色、时间、盲评 ID、依据、分歧和签注。实际审查前 `human_review.status` 保持“待执行”；宿主模型看图或开发者程序验收不是执业人员人工评审。模型和人员分歧分别保留，复议及解盲发生在首次评分锁定后，不回填虚构一致意见。
8. **稳定性与报告。** 对每案三次的核心事实、允许结论、禁止结论、误报和覆盖披露作语义对照，逐项报告三次一致/分歧，不因措辞差异算结论不稳定。列出已计划、已尝试、完成、失败和受隔离限制的次数；未完成不计通过、不从分母隐藏。稳定性与正确性分开：稳定重复错误不算准确。汇总必须链接实际日志和评分记录、披露工具未覆盖项、人审完成数及盲评破坏；没有实际证据的格子保持“待执行”。

| 案例 | 独立运行1 | 独立运行2 | 独立运行3 | 盲评 | 至少一次人工评审 | 稳定性 |
|---|---|---|---|---|---|---|
| stage6-01 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |
| stage6-02 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |
| stage6-03 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |
| stage6-04 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |
| stage6-05 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |
| stage6-06 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 | 待执行 |

## 阶段6实际工程检查（2026-11-05）

此次台账 schema、引擎0.4.0、reader、renderer 和审计命令行为不变；运行入口仅更新 `--version` 中的包版本至0.5.0-beta.1，保留两个版本的区别说明。生成器与打包工具使用标准库，无新增依赖或运行网络路径。9项新增确定性测试已在 macOS 26.6.2 arm64、Python3.14.3、pypdf6.12.1、openpyxl3.1.5 执行：9通过、0跳过、0失败/错误，1.720秒。

三个新增PDF的24页均已用Poppler26.04.0实际渲染并由宿主模型查看，中文正常；原始扫描像素另以150dpi生成，记录详见tests/README.md。本次不是独立模型答题或人工审计评审；新案例尚无正式评测结论。跨平台中文渲染、真实OFD页图及新扫描页的真实OCR识别仍未验证。

全量回归使用经清单验证的阶段1/1.5/3/4包外基线，在允许启动本机LibreOffice的环境实际执行，日志未将skip计入通过：

| 命令/检查 | 实际结果 |
|---|---|
| python3 -B tests/test_public.py | 73项：69通过、4跳过、0失败/错误；35.129秒 |
| python3 -B tests/test_platform.py | 15项：14通过、1跳过、0失败/错误；7.629秒 |
| python3 -B tests/test_structure.py | 8通过、0跳过；3.040秒 |
| python3 -B tools/check_links.py | 1571个本地链接通过 |
| python3 -B tools/check_release.py --write-manifest / 普通检查 | 213份发布文件通过 |
| skill-creator quick_validate.py；git diff --check | 均通过 |
| 对照阶段5验收包 | 全部旧冻结清单及其中27个输入条目原字节一致；原有文件只有双语README、RELEASE_NOTES、VALIDATION、SKILL版本、入口版本、tests/README、public测试装载及release白名单/版本发生变化 |

本机public的4个跳过为原生Windows共享锁、实际RapidOCR、实际Tesseract、实际OFD渲染器；独立platform只跳过同一Windows测试。新增9项均实际执行。字体核验先查看fc-match候选，再用pdffonts -subst确认真正的GB W3替代字体；在交付冻结前更正新像素来源的字体标签和对应新清单哈希，PDF和像素内容未变，旧冻结清单未动。

### 阶段6实际CI

[运行41961673829](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829)，提交e4ded9cb9337207d22004158beaa75b9e5382832，9个任务全部成功。以下计数逐项读取实际日志，skip与通过分列；每组基础矩阵都实际执行新增9项测试。

| 实际任务 | public通过/跳过 | platform通过/跳过 | structure通过/跳过 |
|---|---|---|---|
| [macOS / Python3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225976) | 66/7 | 12/3 | 8/0 |
| [macOS / Python3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225979) | 66/7 | 12/3 | 8/0 |
| [Ubuntu / Python3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225808) | 66/7 | 12/3 | 8/0 |
| [Ubuntu / Python3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225920) | 66/7 | 12/3 | 8/0 |
| [Ubuntu / Python3.14](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225895) | 66/7 | 12/3 | 8/0 |
| [Windows / Python3.11](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225782) | 67/6 | 13/2 | 8/0 |
| [Windows / Python3.12](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225757) | 67/6 | 13/2 | 8/0 |

实际环境：macOS26.6.2 arm64/Python3.11.9、3.12.10；Ubuntu Linux7.0/glibc2.43/Python3.11.18、3.12.16、3.14.9；Windows build26100/Python3.11.9、3.12.10。七组均为pypdf6.21.4、openpyxl3.1.5，链接1571项、发布文件213份及历史结构对照通过。缺失LibreOffice、Poppler、双OCR和实际OFD渲染器的基础测试明确skip；POSIX额外跳过原生Windows共享锁，Windows实际执行。

[独立OCR任务](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225771)：2通过/0跳过，Tesseract5.5.0/chi_sim+eng及RapidOCR1.4.4/ONNXRuntime1.31.1实际执行既有后端测试。[独立LibreOffice任务](https://github.com/KaguraNanaga/audit-skill/actions/runs/41961673829/job/127029225506)：1通过/0跳过，LibreOffice26.2.6.3实际覆盖三条WPS兼容二进制转换路径。它们不证明新增扫描页的实际OCR识别、新OFD发票的页图渲染或模型判断已验证。

字体来源标签修正后，本机单独重跑新增9项测试：9通过、0跳过，1.870秒；本节所列CI也使用了修正后的标签和冻结哈希。回填此CI记录后只修改维护文档和发布清单，最终提交后续CI由交付链接核对，不预填尚未执行的结果。18次正式独立评测、盲评和人工评审仍全部待执行。
