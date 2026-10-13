# Evidence Reviewer · Audit Evidence Verification and Review Assistant

A skill that helps auditors for internal audit, financial-statement audit, and other external audit work. It supports tracing report language back to source materials, recalculating figures, spotting period and accounting-basis differences, checking full context and contrary evidence, and proposing locatable evidence with the minimum necessary edits.

中文说明见 [README.zh-CN.md](README.zh-CN.md)。

Public package version: **0.4.0-beta.1**. The ledger engine remains **0.3.1**; the two numbers identify the release package and the runtime engine separately. See [RELEASE_NOTES.md](RELEASE_NOTES.md) for changes and [VALIDATION.md](VALIDATION.md) for what was actually tested and what was not.

## Scope

Internal vs external audit describes the engagement relationship; financial-statement, internal-control/compliance, and special-purpose audits describe objectives or subject matter. Before choosing methods, confirm the audit objective, engagement relationship, entity, period, applicable standards, and required deliverables. Source tracing, amount recalculation, and evidence-boundary discipline are shared across audit types; specific procedures must follow the engagement and currently effective local standards.

Current focus: material verification, working-paper organization, report review, and multi-round supplemental evidence. It does **not** automatically complete a statutory audit or issue an assurance opinion. Risk assessment, materiality, sampling, confirmations, inventory observation, and similar procedures remain the auditor's responsibility to plan and document. The model performs review and judgment; Python scripts handle snapshots, citations, Decimal math, the ledger, and structural checks. Passing validation does **not** prove semantic correctness, sufficient evidence, or zero hallucination.

| Mode | Typical tasks |
|---|---|
| `query` | Locate a transaction, clause, date, or document and state sources and limits |
| `verify` | Check figures, facts, accounting bases, calculations, and evidence relationships |
| `coverage` | Check for omissions, unperformed procedures, and unread materials against the objective |
| `draft` | Draft records, working papers, or report paragraphs from verified facts |
| `review` | Review existing reports, working papers, and edit suggestions; propose minimal changes |
| `rules` | Look up applicable policies and standards; record effectiveness and limits |

Modes can be combined. Supplemental materials use a separate `update` command to open a new round. Simple queries can follow evidence principles without a ledger; build a ledger when you need to track multi-round changes.

## Install and use

This package is installable Skill source for local use. It does **not** include a hosted service or model API keys. You need an agent host that can read files, run commands, and actually view images; policy lookup also needs a working browser tool. Word editing/layout, complex tables, and image viewing require host-provided tools—this package does not install those capabilities for you.

Use **Python 3.11 or newer** and a virtual environment. The scripts' minimum language/stdlib surface is Python 3.9; 3.9/3.10 were only assessed statically and are not a support commitment. Ledger writes rely on POSIX `fcntl` file locking and directory sync: this release was checked on macOS; Linux/WSL must be verified by the user; **native Windows ledger writes are not supported**.

From the package root, create the venv **outside** the package so release files stay separate from local dependencies:

```sh
python3 -m venv ../evidence-reviewer-venv
. ../evidence-reviewer-venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -B evidence-reviewer/scripts/review.py --help
```

Dependency ranges limit install candidates; they do not mean every version in the range was tested. See [VALIDATION.md](VALIDATION.md) for versions actually verified. Installs use whatever package index you configured; offline install is fine where policy requires it.

Codex currently discovers local skills from a project's `.agents/skills/` or personal `~/.agents/skills/`. Copy the **`evidence-reviewer` subdirectory** into one of those locations, keeping its `SKILL.md`, `LICENSE`, `references/`, `scripts/`, and `agents/`. For example, when the target does not yet exist, from this package root:

```sh
mkdir -p "$HOME/.agents/skills"
cp -R evidence-reviewer "$HOME/.agents/skills/evidence-reviewer"
```

If a same-named install already exists, compare and back it up first so two trees are not mixed. Keep the dependency venv separate and tell the host the real Python path for the task. After install, select it in the skill list or use `$evidence-reviewer` where Codex supports that; restart the host if it does not appear. These are install instructions only—this README does not perform the install. Paths and discovery were checked against the [OpenAI Skills documentation](https://learn.chatgpt.com/docs/build-skills) (2026-10-13). Marketplace distribution needs separate packaging; this package is not published to a marketplace.

A starter request can look like:

> Use evidence-reviewer to check the report and attachments in the given materials directory. The audit objective is contract-performance review; cutoff date and applicable rules follow the materials; mark uncertainties. For each item give "report location | original wording | review conclusion | actual evidence | minimal edit". Actually view critical scanned pages; list unread and unconfirmed parts separately. Keep results outside the materials directory.

## File capabilities and dependencies

| File / capability | Current path and dependency | Hard limits to keep |
|---|---|---|
| TXT, MD, CSV, TSV, JSON, HTML | Python stdlib; line/record locators | HTML is text-parsed, pages are not executed; extraction does not prove facts |
| SRT, VTT | Stdlib; keep time ranges and speaker labels | No auto speech-to-text; speaker identity is not verified |
| DOCX | Stdlib XML parse of text layer and media | XML anchors are not page numbers; images are not auto-bound to body position; layout, seals, revisions, and nearby content need visual review |
| Legacy DOC | macOS `textutil` → DOCX | Conversion may change pagination/objects; other OSes need another available converter and must keep provenance |
| XLSX | `openpyxl`; cells, formulas, cached values | Does not recalculate formulas; does not auto-check colors, partial rich text, images, charts, or voucher continuation |
| Legacy XLS | `soffice` (LibreOffice) then XLSX path | Converted caches and complex objects still need review |
| Text or mixed PDF | `pypdf` by physical page | Text present ≠ images read; textless pages stay pending visual review; no built-in OCR |
| PDF page images | Poppler `pdftoppm` | `render` only produces images; you must open them with an image tool and raise resolution when needed |
| PNG, JPG, JPEG, TIFF, WebP | Register original + fingerprint; host image tool views | No auto OCR; multi-page TIFF needs all relevant frames; other formats need conversion with an audit trail |
| Word page render | Host document renderer via `--docx-renderer` | Renderer is not shipped; Word output still needs a document tool and page-by-page check |
| External rule lookup | Host search/open tools; scripts import records | No body, no attachment, or unchecked effectiveness → state limits; search snippets cannot replace originals |

When a dependency is missing or a read fails, keep the failure record, continue with what can be verified, and do not treat a read failure as proof that an event does not exist. Encrypted PDFs without a usable password cannot be read; this package does not bypass passwords. Install required system tools through channels your environment allows; they are not in `requirements.txt`.

## Workflow and minimal example

End-to-end flow: **clarify objective and scope → read and locate originals → split review propositions → check context, original pages, and figures → look for contrary evidence and applicable rules → form edit suggestions → validate and save records → update from supplemental evidence**.

Important conclusions must trace to originals and relevant context; image-based points must be actually viewed; important figures keep source, basis, and recalculation; before delivery, check exceptions, contrary evidence, and over-strong wording. Conclusions are: substantially consistent, confirmed incorrect, needs explanation, or insufficient evidence; unfinished review is listed separately. When new evidence arrives, correct prior judgments and keep the rationale.

Practice first with the synthetic materials under [tests/cases](tests/cases). Do **not** treat expected answers as audit evidence. Cases cover `financial`, `controls`, `contract`, and `responsibility`; only each case's `sources/` is in scope, and `request.md` is the review request. Independent evaluation sessions must not open `tests/expected.json` or the fixture generator. Do not pass this package root, test answers, or historical outputs to the scripts as business sources.

The following example, run from the package root, copies the financial case into a temp directory and finishes read preparation—it does **not** produce a business conclusion:

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
request = {"goal": "Check amounts, bases, and conclusions in the synthetic financial case", "modes": ["verify"],
           "source_roots": [str(demo / "sources")], "output": {"format": "md"}}
(demo / "request.json").write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
script = str(Path("evidence-reviewer/scripts/review.py").resolve())
subprocess.run([sys.executable, "-B", script, "begin", "--project", str(demo / "project"),
                "--request", str(demo / "request.json")], check=True)
subprocess.run([sys.executable, "-B", script, "inspect", "--project", str(demo / "project")], check=True)
print("Demo directory:", demo)
DEMO_PY
```

Then have the host continue verification using `tests/cases/financial/request.md` and the units actually obtained. The demo directory is newly created; clean it up when finished.

When a ledger is needed, prepare the request per [workflow.md](evidence-reviewer/references/workflow.md) and run `begin`, `inspect`; fill the assessment from this round's actual reading, then `check-assessment`, `finalize`, and `validate`. `begin` only prepares snapshots and read units—it does not emit automatic audit conclusions; facts and judgments in `assessment.json` must come from actual review. Keep the project **outside** the materials directory and use a new project path.

Ledger outputs include `review.md`, `handoff.md`, `changes.md`, and `history.md`; draft tasks also get `draft.md`. User deliverables can still be one verification table or replaceable paragraphs. Inside the project, original snapshots, caches, and history are sensitive audit material; moving the whole project may break old absolute export links, and there is no automatic migration tool.

## Testing and validation

From the package root:

```sh
python3 -B tests/test_public.py
python3 -B tools/check_release.py
```

Coverage and results are documented in [VALIDATION.md](VALIDATION.md). Deterministic tests check reading, calculation, boundary handling, and file consistency; if PDF/XLSX dependencies are missing, related tests may skip explicitly—do not count skips as passes. The release check verifies file contents, missing files, and extras, ignoring `.git` metadata that is not part of the package; keep venvs, business projects, and caches outside the package. Fixtures ship with the package; only rebuild them when needed with `Pillow` and `reportlab` via `python3 -B tests/generate_fixtures.py`—those are not core runtime dependencies. Model-behavior tests must use sessions that have not seen expected answers, and must save actual tool actions and conclusions. Passing synthetic cases does **not** mean every audit type, file format, or real engagement has been validated.

When filing issues, provide a synthetic or fully redacted minimal case, package version, engine version, Python/dependency versions, reproduction steps, and expected vs actual behavior. Do not put real working papers, contracts, payroll lists, or sensitive paths from full error dumps into public issues.

## Data handling and license

The package's Python scripts have no built-in network, telemetry, or upload path; they write material copies, excerpts, calculations, and history under the project directory you specify. Model hosts, browser tools, external renderers, and connectors each have their own data handling and permissions. **Using local files does not mean model inference stays offline, and it is not a "data never leaves this machine" promise.** Choose host and data permissions per your organization's requirements. For external lookups, use only necessary public keywords; do not send unauthorized audit originals, personal data, or trade secrets to search services, connectors, or public repositories.

Original code, method docs, and synthetic cases in this package are licensed under the [Apache License 2.0](LICENSE). Font subsets embedded in PDF fixtures remain under the separate [Bitstream Vera font license](tests/FONT_LICENSE.txt); third-party dependencies keep their own licenses. User materials, official standards, and external sources do **not** become Apache-2.0-licensed merely because they were reviewed or linked. Publishers must have the right to publish what they provide; this license does not opine on confidentiality or copyright status of specific materials. The public package contains only selected code, docs, and synthetic tests—keep real engagement projects outside the package.
