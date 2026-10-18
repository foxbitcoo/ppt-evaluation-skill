"""Versioned ideal-delivery scoring, separate from raw truth/validation judgments."""
import copy, math

POLICY = 'ideal-delivery@0.3.0'
TECHNICAL = ('Required check omitted', 'Expected page/rule not assessed', 'Wrong source page',
             'Wrong page/deck target', 'Conflicting duplicate', 'Invalid assessment',
             'Invalid evidence/issues', 'Rating and status mismatch', 'Scored assessment has no evidence',
             'Owned defects require BAD')

def build_delivery(result, rules, gap_score=40):
    if not isinstance(gap_score, (int, float)) or not math.isfinite(gap_score) or not 0 <= gap_score <= 50:
        raise ValueError('Evidence-gap score must be between 0 and 50')
    rows = copy.deepcopy(result['assessments']); extra = []; failures = []; sources = result.get('source_pages_missing',[])
    for row in rows:
        row['effective_score'] = None; row['score_basis'] = 'assessment'
        if row['status'] == 'NOT_APPLICABLE': continue
        if row['rating'] is not None:
            row['effective_score'] = row['rating'] * 25; continue
        reason = row.get('reason', '')
        if row.get('related_issue_ids') or 'Penalty removed/merged' in reason or 'Same root charged elsewhere' in reason:
            row.update(score_basis='reference_only', status='NOT_APPLICABLE'); continue
        if row['page'] in sources or any(term in reason for term in TECHNICAL):
            row['score_basis'] = 'evaluation_failure'; failures.append({'rule_id': row['rule_id'], 'page': row['page'], 'reason': reason}); continue
        rid, page = row['rule_id'], row['page']
        # Do not charge the same missing citation again as a factual-evidence gap.
        citation = next((a for a in rows if a['rule_id']=='O07' and a['page']==page and a['status']=='BAD'), None)
        if rid == 'O02' and citation:
            row.update(score_basis='reference_only', status='NOT_APPLICABLE'); continue
        if rid == 'D07' and not result.get('context', {}).get('transcript'):
            problem = '未交付可与页序对应的讲稿，距离完整汇报交付仍有缺项。'
            repair = '补充逐页讲稿或明确指定PPT备注为讲稿，核对每页主旨、转场与时间安排。'
        elif rid == 'O02':
            problem = '本页重要事实尚未建立完整、可复核的证据链；按证据交付不足计分，不等于认定数字错误。'
            repair = '补充关键指标的来源页码或章节、原表、期间与单位，并逐项核对页面数值和推导。'
        else:
            problem = '当前交付证据不足以支持这一质量维度达到理想标准。'
            repair = '补充本维度对应的可见内容与依据，结合原页重新确认主张、结构和表达。'
        issue = {'id': f'gap-{rid}-{page or "deck"}', 'root_defect_id': f'delivery-gap:{rid}:{page}',
                 'primary_rule': rid, 'kind': 'delivery_gap', 'severity': 'P2',
                 'location': '整稿交付' if page is None else '本页的证据与说明',
                 'affected_pages': [] if page is None else [page], 'problem': problem, 'repair': repair,
                 'requires_redraw': False, 'score_policy': POLICY, 'truth_verdict': False}
        row.update(status='DELIVERY_GAP', effective_score=gap_score, score_basis='delivery_gap', issues=[issue]); extra.append(issue)
    levels = {}; pages = []; by_rule = {r['id']: r for r in rules}
    for level in ['object','slide','deck']:
        metrics = []
        for rule in [r for r in rules if r['level']==level]:
            items = [a for a in rows if a['rule_id']==rule['id'] and a['status']!='NOT_APPLICABLE']
            scored = [a for a in items if a['effective_score'] is not None]
            score = sum(a['effective_score'] for a in scored)/len(scored) if scored else None
            metrics.append({'rule_id':rule['id'], 'name':rule['name'], 'weight':rule['weight'], 'applicable':bool(items),
                            'mean_rating':score/25 if score is not None else None,
                            'coverage':len(scored)/len(items) if items else 1,
                            'counts':{}, 'gap_checks':sum(a['score_basis']=='delivery_gap' for a in items)})
        active = [m for m in metrics if m['applicable']]; graded = [m for m in active if m['mean_rating'] is not None]
        den = sum(m['weight'] for m in graded)
        score = round(25*sum(m['weight']*m['mean_rating'] for m in graded)/den,1) if den else None
        complete = all(m['coverage']==1 for m in active)
        levels[level] = {'observed_score':score, 'complete_score':score if complete else None,
                         'coverage':sum(m['weight']*m['coverage'] for m in active)/sum(m['weight'] for m in active) if active else 1,
                         'rules':metrics}
    for p in result['manifest']['pages']:
        entry = {'page':p['page']}
        for level in ['object','slide']:
            active = [a for a in rows if a['page']==p['page'] and by_rule[a['rule_id']]['level']==level and a['status']!='NOT_APPLICABLE']
            scored = [a for a in active if a['effective_score'] is not None]
            entry[level] = {'observed_score':round(sum(a['effective_score'] for a in scored)/len(scored),1) if scored else None,
                            'coverage':len(scored)/len(active) if active else 1}
        pages.append(entry)
    issues = copy.deepcopy(result['audit_scores']['issues']) + extra
    scores = {'levels':levels, 'pages':pages, 'issues':issues, 'overall_complete':None,
              'overall_observed_conditional':None, 'layer_weights':result.get('layer_weights'), 'policy':POLICY}
    return {'policy':POLICY, 'gap_score':gap_score, 'rows':rows, 'scores':scores, 'evaluation_failures':failures,
            'note':'40分是交付证据不足的政策评分，不是事实错误判断；技术故障不扣作者分。'}
