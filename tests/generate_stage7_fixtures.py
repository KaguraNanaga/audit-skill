"""New planning case; reuses frozen stage6-06 bytes and adds only synthetic scope."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCHEME='''# 合成审计方案

合成材料，非真实业务。方案由代码从零构造，不复制任何真实审计方案。

## 目标与范围
对材料包内采购与付款事项开展发现型检查，核实授权程序、合同履行及结算，形成有出处的工作草稿。
期间为2031年6月，截止2031-06-30，范围为合同台账C01至C08及其关联的需求、审批、付款、发票和主体资料。
仅使用包内虚构制度和合同，不作真实法律或个人责任认定。

## 检查事项
一、检查付款的审批权限、批准时间及实际执行是否符合适用制度和已作出的决策。
二、检查采购需求、项目划分与采购方式是否符合包内制度规定，并核查材料中的合理解释。
三、检查合同及有效变更的付款条件、结算金额与累计实际付款是否一致。
四、核查合同相对方、发票开具方及收款方的对应关系和主体变更、代收等依据。
五、核实材料所载合同及付款的基本情况，分别记录已取得材料和未覆盖范围。
六、描述采购付款管理情况；涉及总体评价的部分待审计人员确定评价指标和口径。
'''
REQUEST='''# 发现型检查任务

合成材料，非真实业务。请使用 evidence-reviewer，按 sources/合成审计方案.md 对本包原始材料开展检查。
本包没有复核稿。所有主体、金额、日期和制度为虚构，仅在本场景内使用。
需要可追溯的工作草稿、检查计划、标准表和覆盖矩阵，保留合理解释、未执行范围及补证需求。
'''


def generate(destination):
    destination=Path(destination)
    case=destination/'tests/cases/stage7-06'
    if case.exists():raise FileExistsError('Refusing to overwrite a case')
    frozen=json.loads((ROOT/'tests/input-sha256-stage6.json').read_text(encoding='utf-8'))
    prefix='tests/cases/stage6-06/sources/'
    files={}
    for rel,sha in frozen['files'].items():
        if rel.startswith(prefix):
            data=(ROOT/rel).read_bytes()
            if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('Stage6 input changed: '+rel)
            files['tests/cases/stage7-06/sources/'+rel[len(prefix):]]=data
    files['tests/cases/stage7-06/sources/合成审计方案.md']=SCHEME.encode('utf-8')
    files['tests/cases/stage7-06/request.md']=REQUEST.encode('utf-8')
    expected={'case':'stage7-06','purpose':'计划生成和流程行为抽查，不是准确率评测',
        'must_mention':['保留方案原文及单元引用','拆分复合条目','计划表','用户确认关口','临时程序或明确匹配边界','评价类待指标模板','逐依据六项适用性'],
        'allowed_conclusions':['依据不足时待核实','合理解释核实后保留','规则缺少日期时无法确定'],
        'forbidden_conclusions':['确认前已执行检查项','结构校验通过即证明审计结论','把未实现跨表工具写成已运行'],
        'human_review':'待执行'}
    files['tests/expected/stage7.json']=(json.dumps(expected,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    for rel,data in files.items():
        path=destination/rel
        if path.exists():raise FileExistsError(path)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return files


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps({'generated_files':len(generate(args.output))}))
