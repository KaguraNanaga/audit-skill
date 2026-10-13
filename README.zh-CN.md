# Evidence Reviewer · 审计证据核查与复核助手

面向内部审计、财务报表审计及其他外部审计任务的辅助 Skill。它帮助审计人员从报告表述追溯原始材料，复算数字，识别期间与会计口径差异，检查完整上下文和反证，并给出可定位的证据及最小必要修改。

English documentation: [README.md](README.md).

公开包版本：**0.4.0-beta.1**。台账引擎沿用 **0.3.1**；两者分别表示发布包和运行引擎版本。变更见 [RELEASE_NOTES.md](RELEASE_NOTES.md)，实际测试及未验证范围见 [VALIDATION.md](VALIDATION.md)。

## 适用范围

内审、外审是业务关系的分类，财务报表审计、内控合规审计和专项审计是目标或内容的分类。使用时先确认审计目标、委托关系、主体、期间、适用标准和所需成果，再选择方法。各类审计共用原件追溯、金额复算和证据边界要求；具体程序按任务及当地有效标准适配。

目前重点覆盖材料核查、底稿整理、报告复核和多轮补证。它不自动完成一项法定审计，不自动签发鉴证意见；风险评估、重要性、抽样、函证与监盘等实际程序仍须由审计人员组织并记录。模型执行核查与判断，Python 脚本负责快照、出处、Decimal 计算、台账和结构校验。校验通过不证明语义正确、证据充分或零幻觉。

| 模式 | 典型任务 |
|---|---|
| `query` 查询 | 找到某笔业务、条款、日期或材料，并说明来源和限制 |
| `verify` 核实 | 核查数字、事实、口径、计算及证据关系 |
| `coverage` 查漏 | 按目标检查遗漏、未执行程序和未读材料 |
| `draft` 编制 | 根据已核实事实起草记录、底稿或报告段落 |
| `review` 复核 | 审查已有报告、底稿和修改意见，提出最小修改 |
| `rules` 规则 | 查询实际适用的制度、政策和标准，记录效力与限制 |

模式可组合。补充材料使用独立 `update` 命令建立新轮次。简单查询可以直接按证据原则完成；需要追踪多轮变化时再建立台账。

## 安装与使用

本包是可本地安装的 Skill 源文件，未包含托管服务或模型密钥。需要能读取文件、运行命令和实际查看图像的智能体宿主；政策检索还需要可用的浏览工具。Word 编辑与排版、复杂表格和图像查看需宿主提供相应工具，本包不会自动安装这些能力。

建议使用 **Python 3.11 或更高版本**及虚拟环境。脚本所用最低语言/标准库接口为 Python 3.9；3.9/3.10 仅做静态判断，未作支持承诺。台账写入依赖 POSIX `fcntl` 文件锁及目录同步：本次在 macOS 检查，Linux/WSL 需使用者自行验证；**原生 Windows 台账写入不支持**。

在本包根目录执行，将虚拟环境建在包外，保持发布文件与本地依赖分开：

```sh
python3 -m venv ../evidence-reviewer-venv
. ../evidence-reviewer-venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -B evidence-reviewer/scripts/review.py --help
```

依赖范围用于限制安装候选，并不表示区间内每个版本都测过。实际验证版本见 [VALIDATION.md](VALIDATION.md)。依赖安装会访问你配置的软件源；可按单位环境要求改用离线安装。

Codex 当前支持从项目的 `.agents/skills/` 或个人的 `~/.agents/skills/` 发现本地 Skill。将 **`evidence-reviewer` 子目录**复制到其中一个位置，保留它的 `SKILL.md`、`LICENSE`、`references/`、`scripts/` 和 `agents/`。例如，在目标不存在时，从本包根目录执行：

```sh
mkdir -p "$HOME/.agents/skills"
cp -R evidence-reviewer "$HOME/.agents/skills/evidence-reviewer"
```

已有同名版本时先比较并备份，避免混合两套文件。依赖虚拟环境独立保留，并在任务中告知宿主实际 Python 路径。安装后在技能列表选中它，或在支持的 Codex 界面使用 `$evidence-reviewer`；未出现时重启宿主。此处仅提供安装说明，不执行安装。路径及发现方式核对自 [OpenAI 官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills)（2026-10-13）；插件市场分发需要另行打包，本包没有发布到市场。

入门请求可以这样写：

> 使用 evidence-reviewer，核对指定材料目录中的报告和附件。审计目标为合同履行复核，截止日及适用制度以材料为准；不确定处标明。逐项给出“报告位置｜原表述｜核查结论｜实际证据｜最小修改”。关键扫描页要实际查看，未读和无法确认的部分单独列出。结果保存在材料目录之外。

## 文件能力与依赖

| 文件或能力 | 当前路径及依赖 | 必须保留的限制 |
|---|---|---|
| TXT、MD、CSV、TSV、JSON、HTML | Python 标准库，按行/记录建立位置 | HTML 为文本解析，不执行页面；文本提取不证明事实正确 |
| SRT、VTT | 标准库，保留时间段与原说话人标签 | 不自动转录音频，不核实说话人身份 |
| DOCX | 标准库解析 XML、文字层及媒体文件 | XML 锚点不是页码；图片未自动绑定正文位置；需要回看版式、签章、修订和邻近内容 |
| 旧版 DOC | macOS `textutil` 转为 DOCX | 转换可能改变分页或对象；其他系统须另用可用工具转换并保留来源 |
| XLSX | `openpyxl`，读取单元格、公式与缓存值 | 不重算公式，不自动检查颜色、局部富文本、图片、图表或凭证续行关系 |
| 旧版 XLS | `soffice`（LibreOffice）转换后按 XLSX 读取 | 转换后的缓存与复杂对象仍需核查 |
| 文本或混合 PDF | `pypdf` 按物理页提取 | 有文字不代表图片内容已读；无文字页登记为待目视，不内置 OCR |
| PDF 页图 | Poppler 的 `pdftoppm` | `render` 只生成图片；必须再用图像工具实际查看，需要时提高分辨率 |
| PNG、JPG、JPEG、TIFF、WebP | 登记原图与指纹，由宿主图像工具查看 | 不自动 OCR；多页 TIFF 需确认所有相关帧，其他图片格式需转换并留痕 |
| Word 逐页渲染 | 当前环境可用的文档渲染器，经 `--docx-renderer` 指定 | 渲染器不随本包提供；输出 Word 还需要文档工具并逐页核验 |
| 外部规则检索 | 宿主实际调用公开搜索/打开工具，脚本导入记录 | 无正文、无附件或未查效力时明确限制；不能用搜索摘要替代原文 |

缺依赖或无法读取时保留失败记录，继续可验证部分，不把读取失败解释为事项不存在。加密 PDF 无可用密码时无法完成读取；本包不绕过密码。必要的系统工具请通过本机认可的软件渠道安装，它们不包含在 `requirements.txt` 中。

## 流程与最小示例

完整流程为：**明确目标与范围 → 读取并定位原件 → 拆分核查命题 → 核对上下文、原页和数字 → 查反证与适用规则 → 形成修改建议 → 校验并保存记录 → 根据补证更新**。

重要结论必须能追到原件及相关上下文；图片依据必须实际查看；重要数字保留来源、口径及复算；交付前检查例外条款、反证和过强措辞。结论分为基本相符、确认有误、需要解释、证据不足；未完成核查另列。发现新证据后更正旧判断并保留理由。

先用 [tests/cases](tests/cases) 中的合成材料演练，不能把预期答案作为审计证据。案例分为 `financial`（财务）、`controls`（内控）、`contract`（合同）及 `responsibility`（责任边界），各自的 `sources/` 才是材料范围，`request.md` 是核查请求。独立测评会话不得查看 `tests/expected.json` 或测试夹具生成器。不要把本包根目录、测试答案或历史生成物交给脚本当作业务来源。

以下示例从本包根目录运行，将财务案例复制到临时目录并完成读取准备，**尚未作出业务结论**：

```sh
python3 -B - <<'DEMO_PY'
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

demo = Path(tempfile.mkdtemp(prefix="evidence-review-demo-"))
shutil.copytree("tests/cases/financial/sources", demo / "sources")
request = {"goal": "核对合成财务案例的金额、口径与结论", "modes": ["verify"],
           "source_roots": [str(demo / "sources")], "output": {"format": "md"}}
(demo / "request.json").write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
script = str(Path("evidence-reviewer/scripts/review.py").resolve())
subprocess.run([sys.executable, "-B", script, "begin", "--project", str(demo / "project"),
                "--request", str(demo / "request.json")], check=True)
subprocess.run([sys.executable, "-B", script, "inspect", "--project", str(demo / "project")], check=True)
print("演练目录：", demo)
DEMO_PY
```

再让宿主按 `tests/cases/financial/request.md` 和已取得的实际单元继续核查。演练目录由命令新建，使用结束后可自行清理。

需要台账时，按 [workflow.md](evidence-reviewer/references/workflow.md) 准备请求并执行 `begin`、`inspect`；依据本轮实际阅读填写评估，再执行 `check-assessment`、`finalize` 和 `validate`。`begin` 仅准备快照与读取单元，不输出自动审计结论；`assessment.json` 的事实和判断必须由实际核查形成。项目必须位于材料目录之外，并使用新的项目路径。

台账输出包括 `review.md`、`handoff.md`、`changes.md`、`history.md`，编制任务另有 `draft.md`。用户交付仍可集中为一张核查表或可替换段落。项目内部保留原件快照、缓存和历史，均按敏感审计材料管理；整个项目移址可能使旧导出绝对链接失效，当前没有自动迁移工具。

## 验证与反馈

从本包根目录运行：

```sh
python3 -B tests/test_public.py
python3 -B tools/check_release.py
```

测试覆盖及结果以 [VALIDATION.md](VALIDATION.md) 为准。确定性测试验证读取、计算、边界处理和文件一致性；缺少 PDF/XLSX 依赖时相关测试可能明确跳过，不能把跳过记为通过。发布检查核对文件内容、缺失和额外文件，忽略不随包发布的 `.git` 元数据；虚拟环境、业务项目、缓存应保留在包外。现成测试夹具随包提供；只有需要重建夹具时才另外安装 `Pillow`、`reportlab` 并执行 `python3 -B tests/generate_fixtures.py`，这些不是核心运行依赖。模型行为测试须使用未见预期答案的会话，并保存实际工具操作和结论。合成案例通过不等于所有审计类型、文件格式或真实项目都已验证。

提交问题时提供合成或充分脱敏的最小案例、包版本、引擎版本、Python/依赖版本、复现步骤、预期及实际表现。不要把真实底稿、合同、工资名册或完整报错中的敏感路径直接放入公开问题区。

## 数据处理与许可

本包 Python 脚本没有内置联网、遥测或上传接口；它会在指定项目目录写入材料副本、摘录、计算和历史。模型宿主、浏览工具、外部渲染器或连接器各有自己的数据处理方式与权限。**使用本地文件不等于模型推理全程离线，也不构成“数据不出本机”的承诺。** 使用前按单位要求选择宿主与数据权限；对外查询使用必要的公开关键词，不把未授权的审计原文、个人信息或商业秘密发送到搜索服务、连接器或公开仓库。

本包原创代码、方法文档和合成案例采用 [Apache License 2.0](LICENSE)。PDF 样例内嵌的字体子集另按 [Bitstream Vera 字体许可](tests/FONT_LICENSE.txt) 使用；第三方依赖按各自许可使用。用户材料、官方标准及外部来源不因被核查或链接而获得 Apache 2.0 授权。发布者应有权发布其提供的内容；此授权不代表对具体材料的保密或版权状态作出认定。公开包只包含选定的代码、说明与合成测试资料，真实业务项目应放在包外。
