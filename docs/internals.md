# Evidence Reviewer 维护者说明

本文件随仓库分发，不位于 evidence-reviewer 子目录内。模型执行任务的共同原则和路由在该子目录的 SKILL.md；业务项目仍以自身 ledger/ledger.json 为权威记录。

## 当前目录约定

- `evidence-reviewer/SKILL.md`：单一 skill 入口、共同原则、任务到模块的路由。
- `evidence-reviewer/references/common/`：证据、准确性、读取、台账和增量接口等共享规则。
- `evidence-reviewer/references/evidence-review/`：证据复核模块入口和专用方法。
- `evidence-reviewer/scripts/core/`：本地读取、转换、台账、历史和导出等共享实现。包内使用相对 import；循环依赖保留原有函数内延迟 import。
- `evidence-reviewer/scripts/review.py`：统一 CLI 入口及命令注册。`prepare.py` 是已有盘点命令的兼容入口。
- 当前运行代码没有独立的证据复核专用算法，因此不创建空的 evidence_review 代码包。

内部目录迁移不改变 schema 1/2、引擎0.3.1、readers-1.1、renderer 1–7、命令参数、记录字段、导出文字或原件指纹含义。旧渲染器内的文字与格式保持原样。

## 如何新增模块

1. **明确模块范围。** 给出具体任务、输入、输出及不适用情形，先确定哪些能力可复用 core。脚本只做确定性处理；审计判断由实际核查形成。
2. **建立模块资料。** 使用 `references/<module-id>/index.md` 作为模块入口，将专用参考文档放在同一目录。只有存在实际专用代码时才建立 `scripts/<module_package>/`，加 `__init__.py`。路由标识及文档目录用连字符（如 journal-testing），Python 包目录用下划线（如 journal_testing）。共享规则引用 common，不复制出另一套口径。
3. **登记路由。** 在 SKILL.md 的“任务到模块的路由”表增加一行，列为“当前任务｜模块｜按需读取的入口｜运行入口”。目前唯一模块是 evidence-review，query/verify/coverage/draft/review/rules 仍是其既有模式，不是新增 skill。
4. **注册有实际用途的命令。** 当前入口在 review.py 的 `main()`。需要新 CLI 时，同时在子命令参数声明和 commands 映射中注册，处理函数放在实际模块包内并按需 import；复用 core 的能力。模块目录不会自动扫描、执行或自动增加命令。保留现有命令的名称、参数、默认值、退出码与 JSON 契约；本阶段未添加运行命令。
5. **核对来源及兼容性。** 新派生内容记录源版本、指纹、工具版本和参数；新依赖可选且失败明确。需要 schema 变化时先提升引擎版本并补旧台账兼容测试，不静默改写旧账。
6. **补测试并登记发布。** 在 tests 中增加确定性测试；新材料从零合成、单独冻结，预期与 sources 分开。更新 check_release.py 中已登记目录的白名单，禁止把任意开发文件或业务资料纳入分发。根目录维护文档只明确允许 docs/internals.md。
7. **执行验收后记结果。** 运行 test_public.py、test_platform.py、test_structure.py、check_links.py、check_release.py，执行三系统CI；分开报告通过和跳过。同步 RELEASE_MANIFEST、RELEASE_NOTES；VALIDATION 仅填写实际执行结果。变更运行行为前遵守用户分阶段计划与确认要求。

## 阶段 1.5 的对照方法

对照基线为已验收阶段1提交 `a0cb3714fa7a9d543eb1af0b9b436c38204a73b9`，不是本机可能仍指向旧发布的 HEAD。修改前另保存经发布清单校验的包外副本。CI从本地Git对象导出该提交到临时目录，不由运行脚本联网下载。

`tools/compare_structure.py --baseline BASELINE_DIRECTORY` 在同一解释器及依赖下，对同一批冻结的财务、合同、内控和任期合成输入分别调用调整前后的 begin 与 inspect。

- 不排除任何字段。
- 测试进程固定 L.uid 的UUID序列、L.now的时钟；所有ID、时间字段及相互引用仍比较。
- 只把两个项目各自的绝对根路径前缀规范化为 `$PROJECT`，以比较相同的相对结构。
- 原件SHA256、正文、locator、公式、缓存、状态、限制和版本不屏蔽；副本内的原件字节不改写。

另比较排除import节点后的Python AST、搬迁参考文档的原文，以及旧/新台账的 inspect、validate、update、export。对调整前已提交的renderer 7项目删除临时副本中的导出后重建，要求恢复为原字节；旧renderer 1–6历史仍按冻结指纹校验。链接检查为离线文件/锚点检查，不验证外部网站的当前可用性。

## 阶段3实现与历史范围

OCR共用能力放在core，不新增业务模块或skill。schema3新增OCRAttempt和ocr_derived单元，每轮snapshot保存unit_ids；as_of只返回该轮ID范围。历史单位内容不可变，recovery比较原单元的逐ID内容和每轮视图；旧schema前缀重建必须精确匹配事务原哈希。旧账仅在明确update/finalize时升级并备份。新导出器8追加OCR来源警示，旧1–7实现保持；旧轮portable显式视图仍用renderer7，新轮选择renderer8并保留OCR警示。

阶段1.5的AST/文档原文/输出前后对照固定到阶段1提交a0cb3714和阶段1.5提交4701ac6f，两份均按发布清单验证。当前代码继续单独执行旧台账操作和字节回归，不再把新增功能错误要求为结构迁移。CI设置EVIDENCE_REVIEWER_STRUCTURE_CANDIDATE指向固定阶段1.5目录。
