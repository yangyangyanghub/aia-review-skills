#!/usr/bin/env python3
"""Render a locally validated JSON review into an internal Markdown working report."""
import argparse
from html import escape
import json
from pathlib import Path
from validate_review import validate

def cell(value):
    if value is None:
        return '—'
    return escape(str(value)).replace('|', '\\|').replace('\r', '').replace('\n', '<br>')

def render(data, result):
    p = data['project']
    lines = ['# 建筑设计院 AI 辅助校审工作稿', '',
             '> 内部辅助工作记录；技术判断及正式审签以院内责任流程为准。', '']
    if data['mode'] == 'synthetic':
        lines += ['> **合成演示：全部工程条件、依据与人工记录为虚构测试数据，不能用于真实工程。**', '']
    for key, label in [('name','项目'),('region','地区'),('building_type','类型'),('stage','阶段'),('review_date','审查日期'),('baseline_date','适用基准日'),('baseline_id','图纸基线'),('scope_ref','范围来源')]:
        lines.append(f'- {label}：{cell(p[key])}')
    lines += ['', '## 记录校验与审签准备', '',
              '- 结构校验：'+('有效' if result['schema_valid'] else '存在错误'),
              '- 本次是否重新核对文件字节哈希：'+('是' if result['source_files_verified'] else '否'),
              '- 记录准备状态：'+('满足套件记录条件，待实际人工审签' if result['signoff_readiness']=='ready_for_human_signoff' else '存在阻塞，见下列清单'),
              '- 此状态不能证明图纸安全、范围完整、授权有效、人员身份、电子签章或网络隔离。', '']
    for item in result['errors']+result['blockers']:
        lines.append('- '+cell(item))
    s=result['stats']
    lines += ['', '## 覆盖与未评估', '', '| 口径 | 数量或比例 |','|---|---|',
              f'| 加载规则 | {s["rules_loaded"]} |',f'| 计划检查 | {s["planned"]} |',
              f'| 实际求值 | {s["evaluated"]} |',f'| 疑点数 | {s["findings"]} |']
    for status,count in sorted(s['status_counts'].items()):
        lines.append(f'| {cell(status)} | {count} |')
    for key,label in [('evaluated_rate','计划求值率'),('applicable_evaluated_rate','适用项求值率')]:
        lines.append(f'| {label} | '+('不可计算' if s[key] is None else f'{s[key]:.1%}')+' |')
    lines += ['', '以上分母仅来自本轮已登记范围，不能证明已覆盖全部规范条款；零疑点不能证明整体设计通过。', '',
              '## 检查执行清单', '', '| ID | 规则 | 状态 | 结果 | 原因及范围 |', '|---|---|---|---|---|']
    for c in data['checks']:
        lines.append('| '+' | '.join(cell(c.get(k)) for k in ['id','rule_id','status','result','reason'])+' |')
    lines += ['', '## 疑点与闭环', '', '| ID | 专业 | 风险/置信 | 位置与观察 | 依据 | 人工处置 | 闭环 |', '|---|---|---|---|---|---|---|']
    for f in data['findings']:
        loc='; '.join(f'{e["source_id"]}: {e["locator"]}' for e in f['evidence'])
        lines.append('| '+' | '.join(cell(v) for v in [f['id'],f['discipline'],f['priority']+'/'+f['confidence'],loc+'; '+f['observation'],', '.join(f['basis_ids']),f['review']['status'],f['closure']['status']])+' |')
    if not data['findings']:
        lines += ['', '本轮已登记检查未生成疑点，仍须结合范围、未评估项和实际人工校审核实。']
    for f in data['findings']:
        lines += ['', f'### {cell(f["id"])} {cell(f["title"])}', '', '- 建议动作：'+cell(f['suggested_action'])]
        for e in f['evidence']:
            lines.append(f'- 证据：{cell(e["source_id"])} / {cell(e["locator"])}；哈希 `{e["source_sha256"]}`；片段：{cell(e["excerpt"])}')
        for label,key in [('人工处置记录','review'),('设计回复与复查记录','closure')]:
            lines += ['- '+label+'：', '', '```json',json.dumps(f[key],ensure_ascii=False,indent=2),'```']
    lines += ['', '## 依据索引', '', '| ID | 标识/条号 | 状态/适用性 | 核验 | 来源 |', '|---|---|---|---|---|']
    for b in data['bases']:
        lines.append('| '+' | '.join(cell(v) for v in [b['id'],(b.get('identifier') or '未核验')+' / '+(b.get('clause') or '未核验'),b['status']+' / '+b['applicability'],(b.get('verified_at') or '未核验')+' / '+(b.get('verified_by') or '未核验'),b.get('source_ref')])+' |')
    lines += ['', '## 来源与版本', '', '| ID | 路径 | 版本 | 能力 | SHA-256 |', '|---|---|---|---|---|']
    for src in data['sources']:
        lines.append('| '+' | '.join(cell(src[k]) for k in ['id','path','revision','capability','sha256'])+' |')
    lines += ['', '本报告只汇总实际填报与脚本可验证的记录；未运行真实 CAD/BIM 解析、工程计算或签名验证的能力不得描述为已完成。']
    return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('review',type=Path)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--root',type=Path)
    ap.add_argument('--verify-files',action='store_true')
    args=ap.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError('Output already exists; use a new revision filename')
        data=json.loads(args.review.read_text(encoding='utf-8'))
        result=validate(data,args.root or args.review.parent,args.verify_files)
        if result['errors']:
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 2
        content=render(data,result)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x',encoding='utf-8') as f:
            f.write(content)
        print(json.dumps({'output':str(args.output.resolve()),'signoff_readiness':result['signoff_readiness'],
                          'blockers':len(result['blockers']),'mode':data['mode']},ensure_ascii=False))
        return 0
    except (OSError,ValueError) as exc:
        ap.exit(2,f'Report rendering failed: {exc}\n')

if __name__=='__main__':
    raise SystemExit(main())
