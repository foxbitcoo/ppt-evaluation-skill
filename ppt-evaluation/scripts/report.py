#!/usr/bin/env python3
"""Aggregate page-scoped judgments and derive every final narrative from final rows."""
import argparse, base64, collections, copy, html, json, math, mimetypes
from pathlib import Path
from protocol import unknown
LABELS = {'object': '页内细节', 'slide': '单页表达', 'deck': '整稿'}

def canonical_rows(assessments, rules, manifest, context):
    if not manifest or manifest.get('evaluation_unit') != 'rendered_page':
        raise ValueError('This is the v0.2 page protocol; rerun legacy object-based input separately')
    pages = [p['page'] for p in manifest['pages']]
    if len(pages) != len(set(pages)): raise ValueError('Repeated source page')
    expected = {(r['id'], n): r for r in rules for n in ([None] if r['level'] == 'deck' else pages)}
    rows = {}; roots = set()
    for raw in assessments:
        row = copy.deepcopy(raw); key = (row.get('rule_id'), row.get('page'))
        if key not in expected or key in rows: raise ValueError('Duplicate or unknown page/rule target')
        if row.get('target_id') != ('deck' if key[1] is None else f'slide-{key[1]}'): raise ValueError('Wrong page target')
        if row['rule_id'] == 'D07' and not context.get('transcript'): row = unknown('D07', None, 'No supplied script')
        if row['rule_id'] == 'D01' and not context.get('query'): row = unknown('D01', None, 'No supplied Query')
        state, rating = row.get('status'), row.get('rating')
        if state in {'GOOD', 'BAD'}:
            if type(rating) is not int or not 0 <= rating <= 4 or (rating >= 3) != (state == 'GOOD') or not row.get('evidence'): raise ValueError('Invalid evidence-backed grade')
            if state == 'BAD' and not row.get('issues'): raise ValueError('Low rating without an owned defect')
        elif state not in {'UNCERTAIN', 'NOT_APPLICABLE'} or rating is not None or not row.get('reason'):
            raise ValueError('Unknown/N/A must have a reason and no grade')
        for i in row.get('issues', []):
            if i['root_defect_id'] in roots: raise ValueError('Same root charged twice')
            roots.add(i['root_defect_id'])
            if i['primary_rule'] != row['rule_id']: raise ValueError('Wrong defect owner')
        rows[key] = row
    for rid, page in expected: rows.setdefault((rid, page), unknown(rid, page, 'Expected page/rule not assessed'))
    return [rows[k] for k in expected]

def aggregate(assessments, rules, weights=None, manifest=None, inventories=None, context=None):
    context = context or {}; rows = canonical_rows(assessments, rules, manifest, context)
    levels = {}; page_scores = []
    for level in LABELS:
        metrics = []
        for r in [r for r in rules if r['level'] == level]:
            items = [a for a in rows if a['rule_id'] == r['id']]
            applicable = [a for a in items if a['status'] != 'NOT_APPLICABLE']; graded = [a for a in applicable if a['rating'] is not None]
            metrics.append({'rule_id': r['id'], 'name': r['name'], 'weight': r['weight'], 'applicable': bool(applicable),
                            'mean_rating': sum(a['rating'] for a in graded) / len(graded) if graded else None,
                            'coverage': len(graded) / len(applicable) if applicable else 1,
                            'counts': dict(collections.Counter(a['status'] for a in items))})
        app = [r for r in metrics if r['applicable']]; graded = [r for r in app if r['mean_rating'] is not None]
        den = sum(r['weight'] for r in graded); full = sum(r['weight'] for r in app)
        observed = round(25 * sum(r['weight'] * r['mean_rating'] for r in graded) / den, 1) if den else None
        coverage = sum(r['weight'] * r['coverage'] for r in app) / full if full else 1
        complete = observed if math.isclose(coverage, 1) else None
        if not context.get('page_mapping_reviewed') and manifest.get('page_mapping_status') != 'EXPLICIT_SOURCE_PAGE_MAP': complete = None
        levels[level] = {'observed_score': observed, 'complete_score': complete, 'coverage': round(coverage, 4), 'rules': metrics}
    for page in manifest['pages']:
        row = {'page': page['page']}
        for level in ['object', 'slide']:
            ids = {r['id'] for r in rules if r['level'] == level}; items = [a for a in rows if a['page'] == page['page'] and a['rule_id'] in ids and a['status'] != 'NOT_APPLICABLE']; graded = [a for a in items if a['rating'] is not None]
            row[level] = {'observed_score': round(25 * sum(a['rating'] for a in graded) / len(graded), 1) if graded else None, 'coverage': len(graded) / len(items) if items else 1}
        page_scores.append(row)
    total = conditional = None
    if weights:
        if len(weights) != 3 or not all(isinstance(w, (int, float)) and math.isfinite(w) and w > 0 for w in weights): raise ValueError('Three finite positive weights required')
        vals = [levels[x]['complete_score'] for x in LABELS]; obs = [levels[x]['observed_score'] for x in LABELS]
        if all(v is not None for v in vals): total = round(sum(v*w for v,w in zip(vals,weights))/sum(weights),1)
        if all(v is not None for v in obs): conditional = round(sum(v*w for v,w in zip(obs,weights))/sum(weights),1)
    return {'levels': levels, 'pages': page_scores, 'overall_complete': total, 'overall_observed_conditional': conditional, 'layer_weights': weights,
            'issues': [i for a in rows for i in a.get('issues', [])], 'warning': 'PROVISIONAL_NOT_CALIBRATED; coverage is valid judgment coverage, not exhaustive factual truth'}

def refresh(result, rules):
    result['assessments'] = canonical_rows(result['assessments'], rules, result['manifest'], result.get('context', {}))
    result['scores'] = aggregate(result['assessments'], rules, result.get('layer_weights'), result['manifest'], context=result.get('context', {}))
    if result.get('context', {}).get('score_policy') == 'ideal-delivery@0.3.0':
        from delivery_score import build_delivery
        result['audit_scores'] = copy.deepcopy(result['scores'])
        result['delivery'] = build_delivery(result, rules, result.get('context', {}).get('evidence_gap_score', 40))
        result['scores'] = result['delivery']['scores']
    # Final findings never come from a stale model summary.
    result['final_summary'] = {'assessed_pages': sorted({a['page'] for a in result['assessments'] if a['page'] is not None and a['rating'] is not None}),
                               'open_issues': [{'id': i['id'], 'problem': i['problem'], 'affected_pages': i['affected_pages']} for i in result['scores']['issues']],
                               'unknown_checks': sum(a['status'] == 'UNCERTAIN' for a in result['assessments']),
                               'score_scope': 'Observation only unless complete_score is present; not human calibrated'}
    return result

def image_data(path):
    f = Path(path)
    return 'data:' + (mimetypes.guess_type(f.name)[0] or 'image/png') + ';base64,' + base64.b64encode(f.read_bytes()).decode()

def render(result, out):
    # Score and final issues remain the single source of truth; diagnostics stay separate.
    from reader_report import render_reader
    rules=json.loads((Path(__file__).resolve().parents[1]/'references/rubric.json').read_text())['rules']
    refresh(result,rules)
    return render_reader(result,out,rules)

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('result'); ap.add_argument('--out',required=True); a=ap.parse_args(); d=json.loads(Path(a.result).read_text()); render(d,a.out); print(a.out)
