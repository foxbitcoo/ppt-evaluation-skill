"""Page-scoped validation, source checks and defect ownership; no provider calls."""
import copy, hashlib, json, re
from decimal import Decimal, InvalidOperation

STATES = {'GOOD', 'BAD', 'UNCERTAIN', 'NOT_APPLICABLE'}
UNIT_SCALE = {'usd million': Decimal(1), '百万美元': Decimal(1),
              'usd billion': Decimal(1000), '十亿美元': Decimal(1000),
              'usd 100 million': Decimal(100), '亿美元': Decimal(100),
              'percent': Decimal(1), '%': Decimal(1), '百分比': Decimal(1),
              'percentage point': Decimal(1), '百分点': Decimal(1),
              'basis point': Decimal('.01'), 'bp': Decimal('.01'), '基点': Decimal('.01')}

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]

def unknown(rule, page, reason):
    return {'rule_id': rule, 'page': page, 'target_id': 'deck' if page is None else f'slide-{page}',
            'status': 'UNCERTAIN', 'rating': None, 'evidence': [], 'reason': reason,
            'issues': [], 'related_issue_ids': []}

def _text(value):
    return re.sub(r'\s+', '', str(value)).casefold()

def _numeric(value):
    try:
        number = Decimal(str(value).replace(',', ''))
    except InvalidOperation:
        raise ValueError('Numeric evidence is not a number')
    if not number.is_finite():
        raise ValueError('Non-finite numeric evidence')
    return number

def _unit(unit):
    u = str(unit).strip().casefold()
    if u in {'percent', '%', '百分比'}: return 'percent', UNIT_SCALE[u]
    if u in {'percentage point', '百分点', 'basis point', 'bp', '基点'}: return 'percentage_point', UNIT_SCALE[u]
    if u in UNIT_SCALE: return 'usd_million', UNIT_SCALE[u]
    return u, Decimal(1)

def _same_measure(left, right):
    return all(_text(left.get(k, '')) and _text(left[k]) == _text(right.get(k, ''))
               for k in ['subject', 'metric', 'period']) and _unit(left.get('unit', ''))[0] == _unit(right.get('unit', ''))[0]

def verify_proof(proof, context, pages):
    """Require a real supplied fact or a same-measure numeric contradiction."""
    if not isinstance(proof, dict): raise ValueError('No independently checkable numeric evidence')
    if proof.get('type') == 'source':
        facts = {f['id']: f for f in context.get('facts', [])}
        fact = facts.get(proof.get('fact_id'))
        claim = proof.get('claim', {})
        if not fact or not fact.get('source'): raise ValueError('Fact ID not supplied with a source')
        if not _same_measure(claim, fact): raise ValueError('Company/metric/period/unit do not match source fact')
        if not claim.get('quote'): raise ValueError('No visible quoted value for source comparison')
        a = _numeric(claim['value']) * _unit(claim['unit'])[1]
        b = _numeric(fact['value']) * _unit(fact['unit'])[1]
        # Rounding follows the displayed value, not a tolerance invented by the judge.
        step = Decimal(10) ** _numeric(claim['value']).as_tuple().exponent
        tolerance = abs(step * _unit(claim['unit'])[1]) / 2
        if abs(a - b) <= tolerance: raise ValueError('Value agrees with source at displayed precision')
        return 'fact:' + fingerprint([fact['id'], str(a)]), {'type': 'source', 'fact_id': fact['id'], 'observed_base': str(a), 'expected_base': str(b), 'tolerance': str(tolerance)}
    if proof.get('type') == 'internal':
        left, right = proof.get('left', {}), proof.get('right', {})
        if not _same_measure(left, right): raise ValueError('Internal claims have different company/metric/period/unit')
        if not all(x.get('quote') and x.get('page') in pages for x in [left, right]): raise ValueError('Two readable source-page quotes required')
        a = _numeric(left['value']) * _unit(left['unit'])[1]
        b = _numeric(right['value']) * _unit(right['unit'])[1]
        if a == b: raise ValueError('Internal values agree after unit conversion')
        return 'internal:' + fingerprint([left['subject'], left['metric'], left['period'], sorted([str(a), str(b)])]), {'type': 'internal', 'left': str(a), 'right': str(b)}
    raise ValueError('Unsupported proof type; absent reference is not a factual error')

def _issue(raw, row, context, pages):
    issue = copy.deepcopy(raw)
    for k in ['problem', 'repair', 'location', 'kind']:
        if not isinstance(issue.get(k), str) or not issue[k].strip(): raise ValueError(f'Issue missing {k}')
    if issue.get('severity') not in {'P0', 'P1', 'P2', 'P3'}: raise ValueError('Invalid issue severity')
    if type(issue.get('requires_redraw')) is not bool: raise ValueError('Redraw action must be explicit boolean')
    if issue.get('kind') == 'factual' or row['rule_id'] == 'O02':
        root, verified = verify_proof(issue.get('proof'), context, pages)
        issue['verified_proof'] = verified
    elif issue.get('requirement_id'):
        valid = {r['id'] for r in context.get('requirements', [])}
        if issue['requirement_id'] not in valid: raise ValueError('Unknown task requirement ID')
        root = 'requirement:' + issue['requirement_id']
    else:
        # Conservative matching; different wordings are handled by the explicit deck review.
        root = 'visible:' + fingerprint([row['page'], issue['kind'], _text(issue['location']), _text(issue.get('quote', issue['problem']))])
    affected = issue.get('affected_pages', [row['page']] if row['page'] else [])
    if not isinstance(affected, list) or any(type(n) is not int or n not in pages for n in affected): raise ValueError('Issue references a missing source page')
    if row['page'] is not None and set(affected) - {row['page']}: raise ValueError('Single-page issue cannot claim unseen pages')
    issue.update(root_defect_id=root, primary_rule=row['rule_id'], affected_pages=sorted(set(affected)),
                 id='issue-' + fingerprint([row['rule_id'], row['page'], root]))
    return issue

def normalize_stage(parsed, rules, page, context, source_pages):
    """A bad row never erases other valid page/detail/deck checks."""
    active = {r['id']: r for r in rules}; rows = {}; errors = []; candidates = []
    raw_rows = parsed.get('assessments', []) if isinstance(parsed, dict) else []
    if not isinstance(raw_rows, list): raw_rows = []; errors.append({'reason': 'assessments must be a list'})
    duplicates = set()
    for raw in raw_rows:
        rid = raw.get('rule_id') if isinstance(raw, dict) else None
        try:
            if rid not in active: raise ValueError('Rule outside this stage')
            if rid in rows or rid in duplicates:
                duplicates.add(rid); rows[rid] = unknown(rid, page, 'Conflicting duplicate model assessments')
                raise ValueError('Duplicate rule assessment')
            row = copy.deepcopy(raw); expected = 'deck' if page is None else f'slide-{page}'
            if row.get('page', page) != page: raise ValueError('Wrong source page')
            if row.get('target_id', expected) != expected: raise ValueError('Wrong page/deck target; native object IDs are not required')
            row.update(page=page, target_id=expected)
            row.setdefault('rating', None)
            status, rating = row.get('status'), row['rating']
            if status not in STATES: raise ValueError('Invalid assessment status')
            row.setdefault('reason', ''); row.setdefault('evidence', []); row.setdefault('issues', []); row.setdefault('related_issue_ids', [])
            if not isinstance(row['evidence'], list) or not isinstance(row['issues'], list): raise ValueError('Invalid evidence/issues list')
            if status in {'GOOD', 'BAD'}:
                if type(rating) is not int or not 0 <= rating <= 4 or (rating >= 3) != (status == 'GOOD'): raise ValueError('Rating and status mismatch')
                if not row['evidence']: raise ValueError('Scored assessment has no evidence')
                if status == 'GOOD' and row['issues']: raise ValueError('Owned defects require BAD; suggestions are not defects')
                kept = []
                for issue in row['issues']:
                    try: kept.append(_issue(issue, row, context, source_pages))
                    except (ValueError, KeyError, TypeError) as e:
                        candidates.append({'page': page, 'rule_id': rid, 'issue': issue, 'reason': str(e)})
                row['issues'] = kept
                if status == 'BAD' and not kept: raise ValueError('No independent evidence-backed defect justifies low rating')
            else:
                if rating is not None or not row['reason']: raise ValueError('Unknown/N/A needs null rating and reason')
                row['issues'] = []
            if rid == 'O02' and status == 'GOOD':
                # A broad claim of factual correctness needs reviewed, complete source checking.
                if not context.get('factual_verification_complete_pages') or page not in context['factual_verification_complete_pages']:
                    raise ValueError('Whole-page factual correctness is not independently verified')
            if rid == 'D07' and not context.get('transcript'):
                row = unknown(rid, page, 'No supplied presentation script; actual speech not assessed')
            if rid == 'D01' and not context.get('query'):
                row = unknown(rid, page, 'No supplied Query; task completion not inferred')
            rows[rid] = row
        except (ValueError, KeyError, TypeError) as e:
            errors.append({'page': page, 'rule_id': rid, 'reason': str(e)})
            if rid in active and rid not in duplicates: rows[rid] = unknown(rid, page, str(e))
    for rid in active: rows.setdefault(rid, unknown(rid, page, 'Required check omitted by model'))
    return list(rows.values()), errors, candidates

def apply_decisions(rows, decisions):
    """Only explicit keep/drop/merge; removing a penalty never implies a high grade."""
    rows = copy.deepcopy(rows); issues = {i['id']: i for a in rows for i in a.get('issues', [])}; valid = {}; errors = []
    if not isinstance(decisions, list): return rows, [{'reason': 'Review decisions must be a list'}]
    for d in decisions:
        try:
            key = d['issue_id']
            if key not in issues or key in valid or d.get('action') not in {'keep', 'drop', 'merge'} or not d.get('reason'): raise ValueError('Invalid review decision')
            if d['action'] == 'merge' and (d.get('merge_into') not in issues or d['merge_into'] == key): raise ValueError('Unknown merge owner')
            valid[key] = d
        except (ValueError, KeyError, TypeError) as e: errors.append({'decision': d, 'reason': str(e)})
    bad_merges = [(key, d) for key, d in valid.items() if d['action'] == 'merge' and valid.get(d['merge_into'], {}).get('action', 'keep') != 'keep']
    for key, d in bad_merges:
        errors.append({'decision': d, 'reason': 'Merge owner must be kept; no chains/cycles'}); del valid[key]
    for row in rows:
        kept = []; removed = []
        for issue in row.get('issues', []):
            d = valid.get(issue['id'])
            if not d or d['action'] == 'keep': kept.append(issue); continue
            removed.append(issue['id'])
            if d['action'] == 'merge':
                owner = issues[d['merge_into']]; owner['affected_pages'] = sorted(set(owner['affected_pages'] + issue['affected_pages']))
                row['related_issue_ids'].append(owner['id'])
        row['issues'] = kept
        if removed and row['status'] == 'BAD' and not kept:
            row.update(status='UNCERTAIN', rating=None, reason='Penalty removed/merged; independent replacement grade not established')
    return rows, errors

def deduplicate(rows):
    """Canonical facts/requirements override model-generated IDs; semantic merges are explicit."""
    rows = copy.deepcopy(rows); groups = {}; changes = []
    for row in rows:
        for issue in row.get('issues', []): groups.setdefault(issue['root_defect_id'], []).append((row, issue))
    for root, group in groups.items():
        if len(group) < 2: continue
        priority = {'O02': 0, 'D01': 0}
        owner_row, owner = min(group, key=lambda x: (priority.get(x[0]['rule_id'], 1), x[0]['page'] or 0, x[0]['rule_id']))
        owner['affected_pages'] = sorted({p for _, i in group for p in i['affected_pages']})
        retained = False
        for row, issue in group:
            if row is owner_row and not retained: retained = True; continue
            row['issues'].remove(issue); row['related_issue_ids'].append(owner['id'])
            changes.append({'merged': issue['id'], 'owner': owner['id'], 'reason': root})
            if row['status'] == 'BAD' and not row['issues']:
                row.update(status='UNCERTAIN', rating=None, reason='Same root charged elsewhere; independent rating not established')
    return rows, changes
