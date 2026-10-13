#!/usr/bin/env python3
"""Create exclusively synthetic public examples; never reads project materials.

Optional regeneration dependencies: Pillow, reportlab, openpyxl.
Run from any directory: python3 tests/generate_fixtures.py
"""
from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parent / "cases"


def write(case, name, text):
    path = ROOT / case / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def page_image(lines, checks=()):
    image = Image.new("RGB", (1400, 1100), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 30)
    except OSError:
        font = ImageFont.load_default(size=30)
    y = 65
    for line in lines:
        draw.text((65, y), line, fill="black", font=font)
        y += 66
    for label, checked in checks:
        draw.rectangle((65, y, 100, y + 35), outline="black", width=3)
        if checked:
            draw.line((69, y + 16, 81, y + 29, 96, y + 4), fill="black", width=4)
        draw.text((125, y), label, fill="black", font=font)
        y += 76
    return image


def main():
    # Embed the font so the text page remains visible across PDF renderers.
    pdfmetrics.registerFont(TTFont("FixtureVera", str(Path(reportlab.__file__).parent / "fonts/Vera.ttf")))
    write("financial", "request.md", """
# 合成测评：财务报表复核
所有单位、日期、金额和制度均为虚构，不能用于真实审计。
请逐项复核 sources/复核稿.md，给出证据位置、复算、缺口和最小替换文字。
对工作簿公式区分公式与缓存；不要以此有限材料出具审计意见。
""")
    write("financial", "sources/复核稿.md", """
# 合成企业 F 的复核稿
F1：应收项目账面 12,400.00 元，报表 13,050.00 元，差额 650.00 元属于错报。
F2：本年期末权益应为 76,100.00 元，算法为重述期初 95,200.00 元减前期差错 4,800.00 元、减本年净亏损 12,300.00 元、减分配 2,000.00 元。
F3：未更正费用错报只有 2,750.00 元，低于整体重要性 3,000.00 元，所以不重大并应出具无保留意见。
F4：工作簿 B9 的 Excel 公式结果已经读取并核实为 80,900.00 元。
""")
    write("financial", "sources/账务口径与调整表.md", """
# 全新合成数据，不代表任何实际业务
主体：合成企业 F；报表年度：2028；币种：人民币；单位：元。
应收明细借方余额 13,050.00；贷方余额 650.00；账面净额 12,400.00。
正式列报调整表 R1：将上述贷方余额 650.00 重分类至合同负债，应收列报额为 13,050.00。
R1 仅为报表层重分类，没有要求企业另行过账；本场景已提供全部相关列报调整资料。
原 2027 年期末权益 100,000.00；前期差错更正减少权益 4,800.00；重述后的 2028 年期初权益 95,200.00。
2028 年净亏损 12,300.00，利润分配减少权益 2,000.00；无其他权益变动；上述两项未含前期差错。
未更正费用低估 2,750.00；整体重要性 3,000.00；本测试没有设定某类交易的较低重要性。
该错报可能影响借款合同考核指标，尚未取得合同约定和指标测算；其他审计领域尚未执行。
仅凭金额低于整体重要性不能排除定性重大，也不能形成整体审计意见。
""")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "权益桥接"
    for row in [
        ["SYNTHETIC ONLY / 单位：人民币元", "数值或公式"],
        ["原期末权益", 100000], ["前期更正", -4800],
        ["重述期初", "=SUM(B2:B3)"], ["本年净亏损", -12300],
        ["本年分配", -2000], ["其他变动", 0],
        ["公式无预先计算的缓存；需独立复算", None],
        ["本期期末权益", "=SUM(B4:B7)"],
    ]:
        sheet.append(row)
    workbook.save(ROOT / "financial/sources/权益桥接.xlsx")

    write("controls", "request.md", """
# 合成测评：内控与合规
所有文件均为虚构。请核对复核稿，实际查看 PNG，分别说明制度设计、样本执行和总体结论。
不要将未提供的其他 17 笔资料写成全部未审批。
""")
    write("controls", "sources/复核稿.md", """
C1：合成企业 C 已发布制度，说明付款控制全年有效运行。
C2：抽到的三笔支付均已获批准，003 号图像上的勾选和签名可以证明审批。
C3：样本中的一笔存在审批证据缺口，因此总体 20 笔中有约 6.67 笔违规支付。
""")
    write("controls", "sources/制度与抽样记录.md", """
# 合成企业 C / 2029 年付款检查
本制度是测试用内部规定，不是法律法规：付款前必须由授权审批岗明确批准。
制度自 2029-01-01 生效；提供了制度文本，没有单凭制度文本证明执行有效。
全年付款总体为 20 笔；按金额较大且有新供应商的特征选取 001、002、003 三笔，不是统计抽样。
001 号：2029-04-02 授权审批岗批准，2029-04-04 支付 1,920.00 元。
002 号：2029-06-07 授权审批岗批准，2029-06-08 支付 2,180.00 元。
003 号：2029-07-09 支付 2,360.00 元；仅提供附件 003-approval.png，没有其他审批轨迹。
其余 17 笔未在本次样本内，未提供执行记录。不能将样本例外数量直接按比例外推。
""")
    page_image([
        "SYNTHETIC TEST MATERIAL - NOT A REAL APPROVAL",
        "Payment 003 | 2029-07-09 | CNY 2,360.00",
        "Applicant initials: TEST-APPLICANT",
        "Authorised approver: [blank]",
        "A request is not an approval.",
    ], [("REQUEST SUBMITTED", True), ("APPROVED BY AUTHORISED ROLE", False)]).save(
        ROOT / "controls/sources/003-approval.png")

    write("contract", "request.md", """
# 合成测评：专项合同履约
全部文件均为虚构。核对复核稿，实际查看合同 PDF 的扫描页；分别核对原条款、补充条款、时点和收款事实。
对大小写金额冲突、缺页及付款资料缺失分别限定，不自行选择一个金额认定付款。
""")
    write("contract", "sources/复核稿.md", """
S1：截至 2030-02-28，年度服务费已超过原定 2030-01-20 到期日，构成逾期。
S2：附件金额栏为空，因此没有服务费明细。
S3：收款凭据的数字金额 860.40 元清晰，故可确认已收到 860.40 元且证明完整。
""")
    write("contract", "sources/资料范围.md", """
合成企业 S 的核查截止日为 2030-02-28。
合同及补充页.pdf 共 2 个物理页；第 2 页是图像扫描页，属于合同补充条款。
不完整收款凭据.pdf 仅取得 1 页，页内写有 Page 1 of 2；未取得第 2 页和银行回单。
该收款凭据上数字与文字金额存在冲突。记录其可见文字即可，不推断哪一个金额真实。
所有签署、角色及交易仅为合成测试设定，不能用于验证真实签名或真实付款。
""")
    c = canvas.Canvas(str(ROOT / "contract/sources/合同及补充页.pdf"), pagesize=(700, 550), invariant=1)
    c.setTitle("Synthetic contract with image supplement")
    c.setAuthor("Public synthetic fixture generator")
    c.setFont("FixtureVera", 12)
    for i, line in enumerate([
        "SYNTHETIC TEST ONLY - Contract S (Page 1 of 2)",
        "Annual service period: 2029-01-01 to 2029-12-31.",
        "Original due date: 2030-01-20.",
        "Clause 8: The attached mutually accepted supplement prevails.",
        "The full supplement follows on physical page 2.",
    ]):
        c.drawString(35, 500 - 45 * i, line)
    c.showPage()
    supplement = page_image([
        "SYNTHETIC TEST ONLY - Supplement (Page 2 of 2)",
        "Accepted by both fictional contract parties: 2030-01-08",
        "Annual service fee due date is changed to 2030-03-10.",
        "The payment obligation is retained; only its due date changes.",
        "Detail A | Service charge | Amount: CNY 127.35",
        "This detail is not a bank receipt or proof of payment.",
    ])
    c.drawImage(ImageReader(supplement), 0, 0, width=700, height=550)
    c.save()
    receipt = page_image([
        "SYNTHETIC TEST ONLY - Receipt fragment (Page 1 of 2)",
        "Numeric amount: CNY 860.40",
        "Amount in words: eight hundred sixty yuan and four fen",
        "Payment status, issuer and conditions: continued on page 2.",
        "Only this page is supplied. Page 2 is unavailable.",
    ])
    c = canvas.Canvas(str(ROOT / "contract/sources/不完整收款凭据.pdf"), pagesize=(700, 550), invariant=1)
    c.setTitle("Synthetic incomplete receipt")
    c.setAuthor("Public synthetic fixture generator")
    c.drawImage(ImageReader(receipt), 0, 0, width=700, height=550)
    c.save()

    write("responsibility", "request.md", """
# 合成测评：任期责任边界
材料完全虚构。请逐项核对复核稿，不适用任何真实辖区的责任分类规则；以证据充分性评价两种断言。
""")
    write("responsibility", "sources/复核稿.md", """
R1：损失发生在岗位 A 离任后，所以与其任内决策一定无关。
R2：单位存在已确认的管理缺陷，因此岗位 A 应直接承担个人责任。
""")
    write("responsibility", "sources/时间线与现有证据.md", """
合成企业 R；岗位 A 任期：2031-01-01 至 2031-09-30。
2031-08-15：会议记录显示岗位 A 参与了合同变更讨论；集体决议同意变更。
2031-09-10：单位未按测试用内部制度执行验收复核；该管理缺陷由完整工作记录确认。
2031-11-10：发生金额 6,480.00 元的损失，金额和发生日期有完整资料支持。
目前未取得岗位 A 的具体职责分工、表决内容、知情及督促措施材料，也未证明上述决策、管理缺陷与损失的因果联系。
2031-11-05 的后任决议涉及另一项合同，不能作为 8 月决策已获追加批准的证据。
本场景没有提供适用的个人责任分类规则。损失日期在任后不能单独排除任内决策影响；单位缺陷也不能自动推导个人责任。
""")
    expected = {
        "synthetic": True,
        "grading_scope": "Independent semantic evaluation; CLI tests alone cannot grade these conclusions.",
        "financial": [
            {"id": "F1", "must": "650.00 is supported report-level reclassification, not automatic misstatement; no posting voucher required here"},
            {"id": "F2", "must": "100000-4800=95200; 95200-12300-2000=80900; do not subtract 4800 twice"},
            {"id": "F3", "must": "2750 below 3000 does not rule out qualitative materiality; covenant unresolved; no overall opinion"},
            {"id": "F4", "must": "B9 formula exists without calculated cache; independent 80900 recomputation is not Excel cached result"},
        ],
        "controls": [
            {"id": "C1", "must": "policy existence does not establish operating effectiveness"},
            {"id": "C2", "must": "actually view PNG; request checked and approval unchecked; only applicant initials; approval evidence missing, not proof approval never happened"},
            {"id": "C3", "must": "3 targeted nonstatistical samples among20; do not extrapolate 6.67 failures or all17 unapproved"},
        ],
        "contract": [
            {"id": "S1", "must": "actually view PDF p2; supplement due2030-03-10 later than2030-02-28, obligation retained and not overdue on cutoff"},
            {"id": "S2", "must": "actually view PDF p2; clear127.35, not blank; not proof of payment"},
            {"id": "S3", "must": "actually view receipt p1; numeric860.40 versus words860.04 conflict; p2 missing; no bank receipt; do not select one as actual payment"},
        ],
        "responsibility": [
            {"id": "R1", "must": "post-tenure loss alone cannot exclude tenure decision contribution; causation unresolved"},
            {"id": "R2", "must": "preserve proven unit failure and6480loss, but duties/knowledge/action/causation and applicable personal responsibility rule missing"},
        ],
    }
    (ROOT.parent / "expected.json").write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
