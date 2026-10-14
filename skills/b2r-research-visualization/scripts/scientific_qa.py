"""Compare a Figure Contract with hash-bound host observations, not image pixels.

The host must inspect the image and supply observations. This module neither
recognizes images nor verifies papers, and never certifies scientific truth.
"""
from datetime import date
import hashlib
import json
import re

from common import require, text_value, digest
from visual_grammar import (GRAMMAR, OBSERVED_ENCODINGS, OBSERVED_DEPICTIONS,
                            relation_encoding, entity_depiction, validate_grammar, modification_marker)

RELATIONS = set(GRAMMAR)
DIRECTED = {'activation', 'inhibition', 'neutralization', 'cleavage', 'degradation',
            'migration', 'transport', 'release', 'causation', 'presentation', 'modification'}
FIELDS = ('subject', 'relation', 'object', 'direction', 'origin',
          'subject_site', 'object_site', 'label')

# Standard residue abbreviations are notation, not pathway-specific science.
# Cross-checked against Bio/Data/IUPACData.py in the official Biopython source.
RESIDUES = dict(zip('ala cys asp glu phe gly his ile lys leu met asn pro gln arg ser thr val trp tyr'.split(),
                    'ACDEFGHIKLMNPQRSTVWY'))


def _site_identity(value):
    match = re.fullmatch(r'([A-Za-z]{1,3})\s*(\d+)', value.strip())
    if not match: return None
    residue, number = match.groups()
    code = residue.upper() if len(residue)==1 and residue.upper() in RESIDUES.values() else RESIDUES.get(residue.casefold())
    return (code, int(number)) if code else None


def _unresolved(value):
    return value is None or (isinstance(value,str) and value.strip().casefold() in ('', 'unclear', 'unknown', '?'))


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def dated(value):
    require(isinstance(value, str), '核查日期需为 YYYY-MM-DD')
    date.fromisoformat(value)


def validate_contract(contract):
    require(isinstance(contract, dict) and contract.get('schema_version') == 1,
            'figure_contract.schema_version 需为 1')
    for key in ('id', 'original_request'):
        text_value(contract.get(key), key, 20000)
    entities = contract.get('entities')
    require(isinstance(entities, list) and entities, 'contract.entities 不能为空')
    targets, ids = {}, set()
    for entity in entities:
        require(isinstance(entity, dict), 'entity 必须为对象')
        for key in ('id', 'label', 'kind'):
            text_value(entity.get(key), key, 1000)
        require(entity['id'] not in ids, 'entity id 重复')
        ids.add(entity['id']); targets['entity:'+entity['id']] = entity
    relations = contract.get('relations')
    require(isinstance(relations, list), 'relations 必须为列表')
    for rel in relations:
        require(isinstance(rel, dict), 'relation 必须为对象')
        text_value(rel.get('id'), 'relation id')
        target = 'relation:'+rel['id']
        require(target not in targets, 'relation id 重复')
        require(rel.get('subject') in ids and rel.get('object') in ids,
                'relation 端点未定义')
        require(rel.get('relation') in RELATIONS, 'relation 类型未知')
        require(rel.get('direction') in {'subject_to_object', 'bidirectional', 'undirected'},
                'direction 无效')
        if rel['relation'] in DIRECTED:
            require(rel['direction'] == 'subject_to_object', '方向性关系需显式起终点；双向过程拆为两条')
        text_value(rel.get('context'), 'scientific context', 10000)
        if rel['relation'] in {'migration', 'transport'}:
            require(rel.get('origin') in ids, '迁移/运输必须声明 origin；object 为目的地')
        for key in ('subject_site', 'object_site'):
            if key in rel: text_value(rel[key], key)
        ev = rel.get('evidence', {})
        require(ev.get('status') in {'supported', 'user_provided', 'hypothesis',
                                   'unverified', 'conflicting'}, 'evidence status 无效')
        sources = ev.get('sources', [])
        require(isinstance(sources, list), 'evidence.sources 必须为列表')
        for source in sources:
            require(isinstance(source, dict), 'source 必须为对象')
            text_value(source.get('locator'), '可追溯来源', 2000)
        if ev['status'] == 'supported':
            require(sources and ev.get('scope_review') == 'matched',
                    'supported 需要来源与适用条件核对记录')
            dated(ev.get('checked_at'))
            text_value(ev.get('note'), '证据与条件核对说明', 10000)
        req = rel.get('requirement', {})
        require(req.get('status') in {'preserved', 'uncertain', 'conflict'},
                'requirement status 无效')
        text_value(req.get('note'), '原始需求对应说明', 10000)
        if req.get('quote'):
            require(req['quote'] in contract['original_request'], '需求摘录并非原话')
        if 'critical' in rel: require(isinstance(rel['critical'], bool), 'critical 必须为布尔值')
        targets[target] = rel
    require(isinstance(contract.get('labels', []), list), 'labels 必须为列表')
    for label in contract.get('labels', []):
        require(isinstance(label, dict), 'label 必须为对象')
        for key in ('id', 'value'): text_value(label.get(key), key, 1000)
        target = 'label:'+label['id']
        require(target not in targets, 'label id 重复')
        targets[target] = label
    validate_grammar(contract)
    if 'verification' in contract:
        from evidence import verification_decision
        verification_decision(contract)
    return targets


def glyph_review(target, expected, actual, conditions=''):
    """Compare the glyph the host saw with the relation/entity grammar."""
    missing, differences = [], {}
    if target.startswith('relation:'):
        if expected['relation'] == 'modification':
            wanted = {'modification_type': expected['modification_type'],
                      'marker': modification_marker(expected), 'attached_to': expected['object']}
            if 'modification_site' in expected:
                wanted['modification_site'] = expected['modification_site']
            for key, value in wanted.items():
                seen = actual.get(key)
                if _unresolved(seen):
                    missing.append(key)
                else:
                    text_value(seen, 'observed '+key, 1000)
                    same = seen == value
                    uncertain = False
                    if key in ('modification_type', 'marker'):
                        same = seen.strip().casefold() == value.strip().casefold()
                        if key=='modification_type' and not same:
                            from visual_grammar import MODIFICATION_MARKERS
                            uncertain = seen.casefold() not in MODIFICATION_MARKERS or value.casefold() not in MODIFICATION_MARKERS
                    elif key == 'modification_site':
                        a,b = _site_identity(value),_site_identity(seen)
                        same = seen.strip().casefold() == value.strip().casefold() or (a is not None and a==b)
                        uncertain = not same and (a is None or b is None)
                    if not same:
                        differences[key] = {'expected': value, 'observed': seen}
                        if uncertain:
                            differences[key]['certainty'] = 'uncertain'
        if conditions:
            shown = actual.get('condition_shown')
            if shown not in {'yes', 'no'}:
                missing.append('condition_shown')
            elif shown == 'no':
                differences['condition_shown'] = {'expected': conditions, 'observed': 'not shown',
                                                  'note': 'The figure states this relation beyond its evidence scope.'}
        allowed, preferred = relation_encoding(expected)
        seen = actual.get('encoding')
        if seen is None or seen == 'unclear':
            if 'encoding' in expected or expected['relation'] == 'modification' or seen == 'unclear': missing.append('encoding')
        else:
            require(seen in OBSERVED_ENCODINGS, 'encoding 观察值无效')
            if seen not in allowed:
                differences['encoding'] = {'expected': preferred, 'acceptable': list(allowed), 'observed': seen}
    elif target.startswith('entity:'):
        depiction = entity_depiction(expected)
        seen = actual.get('depiction')
        if seen is not None:
            require(seen in OBSERVED_DEPICTIONS, 'depiction 观察值无效')
        if (depiction and seen is None) or seen == 'unclear':
            missing.append('depiction')
        elif seen == 'chemical_structure' and depiction != 'verified_structure':
            differences['depiction'] = {'expected': depiction or 'no drawn structure', 'observed': seen,
                                        'note': 'Image-model chemical structures are not verified bond topology.'}
    return missing, differences


# Different abstraction levels need review; only opposite causal polarity is
# automatically contradictory, not every different relation name.
TARGETED = {'inhibition', 'neutralization'}
POSITIVE = {'activation', 'causation'}


def opposed_relations(a, b):
    return (a in POSITIVE and b in TARGETED) or (b in POSITIVE and a in TARGETED)


def contract_clash(contract, seen):
    """An extra edge that re-targets or reverses a planned one is a conflict, not a decoration."""
    ids, kinds = {}, {e['id']: e['kind'] for e in contract['entities']}
    for e in contract['entities']:
        ids[e['id'].casefold()] = ids[e['label'].casefold()] = e['id']
    s, o = ids.get(seen['subject'].casefold(), seen['subject']), ids.get(seen['object'].casefold(), seen['object'])
    # A planned second target is not retargeting, including an uncertain
    # abstraction of that relation. The extra scan never automatically PASSes.
    if any(s == r['subject'] and o == r['object'] and not opposed_relations(seen['relation'], r['relation'])
           and seen['direction'] == r['direction'] for r in contract['relations']):
        return None
    for rel in contract['relations']:
        target = 'relation:' + rel['id']
        same_pair = {s, o} == {rel['subject'], rel['object']}
        reversed_ = (s != rel['subject'] and rel['relation'] in DIRECTED and seen['relation'] in DIRECTED
                     and rel['direction'] == seen['direction'] == 'subject_to_object')
        if same_pair and (opposed_relations(seen['relation'], rel['relation']) or reversed_):
            return target, 'opposite causal polarity or reversed directed relation'
        targeted = rel['relation'] in TARGETED or (rel['relation'] == 'binding' and kinds.get(s) == 'antibody')
        seen_targeted = seen['relation'] in TARGETED or (seen['relation'] == 'binding' and kinds.get(s) == 'antibody')
        modification = rel['relation'] == seen['relation'] == 'modification'
        if s == rel['subject'] and ((targeted and seen_targeted) or modification) and o != rel['object']:
            return target, f"planned {rel['relation']} drawn onto a different object"
    return None


def revision_review(previous, previous_contract, report, contract):
    """Compare QA of an edited image with its parent. Earlier PASS is never carried over."""
    require(previous.get('contract_sha256') == fingerprint(previous_contract), '上一版 QA 与其契约不匹配')
    before, after = validate_contract(previous_contract), validate_contract(contract)
    changed = sorted(t for t in after if t not in before or fingerprint(before[t]) != fingerprint(after[t]))
    old = {r['target']: r['status'] for r in previous['checks'] if r['axis'] == 'image'}
    new = {r['target']: r['status'] for r in report['checks'] if r['axis'] == 'image'}
    rank = {'PASS': 0, 'NEEDS_REVIEW': 1, 'CRITICAL_ERROR': 2}
    regressed = sorted(t for t in new if t in old and rank[new[t]] > rank[old[t]] and
                       not (old[t] == 'PASS' and new[t] == 'NEEDS_REVIEW'))
    return {'previous_image_sha256': previous['image_sha256'], 'previous_disposition': previous['disposition'],
            'changed_contract_targets': changed, 'removed_contract_targets': sorted(set(before) - set(after)),
            'fixed': sorted(t for t in new if old.get(t) == 'CRITICAL_ERROR' and new[t] == 'PASS'),
            'improved': sorted(t for t in new if old.get(t) == 'CRITICAL_ERROR' and new[t] == 'NEEDS_REVIEW'),
            'still_critical': sorted(t for t in new if old.get(t) == 'CRITICAL_ERROR' and new[t] == 'CRITICAL_ERROR'),
            'regressed': regressed,
            'unrequested_regressions': [t for t in regressed if t not in changed],
            'no_longer_confirmed': sorted(t for t in new if old.get(t) == 'PASS' and new[t] == 'NEEDS_REVIEW'),
            'notice': 'The edited image is reviewed on its own observations; unrequested_regressions are content the edit was not asked to change.'}


def contract_from_brief(brief):
    """Reuse structured Brief. Missing context/evidence stays unverified.

    Not a natural-language extractor: the current host interprets raw requests.
    Migration origins and binding sites require host enrichment where relevant.
    """
    from figure_brief import validate_brief
    validate_brief(brief)
    require(isinstance(brief, dict), '短文本 Brief 由宿主选择关键关系；不做关键词推断')
    relations = []
    for r in brief['relations']:
        relations.append({'id': r['id'], 'subject': r['subject'], 'object': r['object'],
                          'relation': r['type'], 'direction': 'subject_to_object',
                          'context': brief['topic'],
                          'evidence': {'status': 'hypothesis' if 'hypothesis' in r['status']
                                       else 'user_provided' if r['status'] == 'user_provided'
                                       else 'unverified', 'sources': [],
                                       'brief_source': r['source']},
                          'requirement': {'status': 'uncertain', 'note': 'Brief 已转换，宿主需核对原话与方向/区室。'}})
        if r['type'] == 'modification':
            for key in ('modification_type', 'modification_site', 'marker'):
                if key in r: relations[-1][key] = r[key]
    return {'schema_version': 1, 'id': 'brief-contract', 'original_request': brief['original_request'],
            'entities': [{k: e[k] for k in ('id', 'label', 'kind')} for e in brief['entities']],
            'relations': relations,
            'labels': [{'id': str(i), 'value': t} for i, t in enumerate(brief['labels']+brief['protected_values'])]}


def evaluate(contract, observation, image, evidence_ledger=None):
    targets = validate_contract(contract)
    evidence_report = None
    if evidence_ledger is not None or 'verification' in contract:
        from evidence import evaluate_evidence
        evidence_report = evaluate_evidence(contract, evidence_ledger)
    evidence_rows = {r['relation_id']: r for r in evidence_report['claims']} if evidence_report else {}
    image_hash = digest(image)
    rows = []
    checks = {}
    basis = 'unobserved'
    if observation is not None:
        require(isinstance(observation, dict), 'scientific_observation 必须为对象')
        require(observation.get('image_sha256') == image_hash, '观察记录不属于此图像')
        require(observation.get('contract_sha256') == fingerprint(contract), '观察记录不属于此契约')
        basis = observation.get('basis')
        require(basis in {'image_view', 'layer_inspection', 'synthetic_fixture'}, '观察方式未知')
        text_value(observation.get('method'), '观察工具/方法', 2000)
        require(isinstance(observation.get('checks'), list), 'observations.checks 必须为列表')
        for check in observation['checks']:
            require(isinstance(check, dict), 'observation check 必须为对象')
            target = check.get('target')
            require(target in targets and target not in checks, '未知或重复观察对象')
            require(check.get('visibility') in {'clear', 'uncertain', 'absent'}, 'visibility 无效')
            text_value(check.get('note'), '具体图像观察', 10000)
            text_value(check.get('location'), '图中位置', 2000)
            checks[target] = check
    for target, expected in targets.items():
        if target.startswith('relation:'):
            req = expected['requirement']
            rows.append({'target': target, 'axis': 'request', 'status':
                         'PASS' if req['status'] == 'preserved' else 'NEEDS_REVIEW',
                         'note': req['note'], 'basis': 'host_request_interpretation'})
            ev = expected['evidence']
            if expected['id'] in evidence_rows:
                rows.append({'target': target, 'axis': 'evidence',
                             **evidence_rows[expected['id']], 'basis': 'host_retrieval_scope_review'})
            else:
                rows.append({'target': target, 'axis': 'evidence', 'status':
                         'PASS' if ev['status'] == 'supported' else 'NEEDS_REVIEW',
                         'note': ev.get('note', ev['status']), 'evidence_status': ev['status'],
                             'basis': 'recorded_source_scope_review'})
        check = checks.get(target)
        row = {'target': target, 'axis': 'image', 'basis': basis, 'status': 'NEEDS_REVIEW',
               'note': '尚未观察此检查项'}
        if check:
            row.update(note=check['note'], location=check['location'])
            if check['visibility'] == 'absent':
                row['status'] = 'CRITICAL_ERROR' if expected.get('critical', True) else 'NEEDS_REVIEW'
            elif check['visibility'] == 'clear':
                actual = check.get('observed', {})
                require(isinstance(actual, dict), 'observed 必须为对象')
                fields = [k for k in FIELDS if k in expected] if target.startswith('relation:') else ['value'] if target.startswith('label:') else ['id']
                missing = [k for k in fields if not isinstance(actual.get(k), str) or not (actual[k].strip() or k == 'label')]
                if expected.get('relation') == 'modification':
                    missing = sorted(set(missing) | {k for k in fields if k != 'label' and _unresolved(actual.get(k))})
                conditions = evidence_rows.get(expected.get('id'), {}).get('conditions', '') if target.startswith('relation:') else ''
                glyph_missing, glyph_differences = glyph_review(target, expected, actual, conditions)
                if missing or glyph_missing:
                    row['missing_observation_fields'] = missing + glyph_missing
                if not (missing or glyph_missing) or expected.get('relation') == 'modification':
                    differences = {k: {'expected': expected[k], 'observed': actual[k]}
                                   for k in fields if isinstance(actual.get(k), str)
                                   and (actual[k].strip() or k == 'label')
                                   and not (expected.get('relation') == 'modification' and k != 'label'
                                            and _unresolved(actual[k])) and actual[k] != expected[k]}
                    differences.update(glyph_differences)
                    hard_differences = dict(differences)
                    if expected.get('relation') == 'modification':
                        hard_differences = {k:v for k,v in hard_differences.items() if v.get('certainty') != 'uncertain'}
                    if (target.startswith('relation:') and 'relation' in differences
                            and not opposed_relations(expected['relation'], actual['relation'])):
                        hard_differences.pop('relation')
                        # A glyph consistent with a different observed abstraction
                        # is uncertain, not independently proven wrong.
                        if actual['relation'] in GRAMMAR:
                            allowed, _ = relation_encoding(actual)
                            if actual.get('encoding') in allowed:
                                hard_differences.pop('encoding', None)
                    row['status'] = (('CRITICAL_ERROR' if expected.get('critical', True) else 'NEEDS_REVIEW')
                                     if hard_differences else 'NEEDS_REVIEW'
                                     if differences or missing or glyph_missing else 'PASS')
                    if differences: row['differences'] = differences
        rows.append(row)
    # A correct requested edge does not exclude an extra, unsupported mechanism.
    # This is a separate host image observation, never inferred from the prompt.
    if contract['relations']:
        scan = observation.get('relation_scan') if observation else None
        row = {'target': 'unplanned_relations', 'axis': 'image', 'basis': basis,
               'status': 'NEEDS_REVIEW', 'note': '尚未检查图中是否新增契约外机制'}
        if scan is not None:
            require(isinstance(scan, dict) and scan.get('visibility') in {'clear', 'uncertain'}, 'relation_scan 无效')
            text_value(scan.get('note'), '新增机制实际观察', 10000)
            require(isinstance(scan.get('unexpected_relations'), list), 'unexpected_relations 必须为列表')
            extras = scan['unexpected_relations']
            for extra in extras:
                require(isinstance(extra, dict) and extra.get('visibility') in {'clear','uncertain'}, '额外关系观察无效')
                require(extra.get('assessment') in {'unsupported','conflicting'}, '区分未核验新增机制与明确冲突')
                for key in ('location','note'): text_value(extra.get(key), key, 10000)
                if extra['assessment'] == 'conflicting':
                    require(extra.get('conflicts_with') in targets and extra['conflicts_with'].startswith('relation:'), '明确冲突需指向受保护关系')
                if extra['visibility'] == 'clear':
                    for key in ('subject','relation','object','direction'):
                        text_value(extra.get('observed', {}).get(key), key, 1000)
                    if extra['assessment'] == 'unsupported':
                        clash = contract_clash(contract, extra['observed'])
                        if clash:
                            extra.update(assessment='conflicting', conflicts_with=clash[0], escalated=clash[1])
            row.update(note=scan['note'], unexpected_relations=extras)
            row['status'] = 'CRITICAL_ERROR' if any(e['visibility']=='clear' and e['assessment']=='conflicting' for e in extras) else (
                'PASS' if scan['visibility']=='clear' and not extras else 'NEEDS_REVIEW')
        rows.append(row)
    statuses = {r['status'] for r in rows}
    return {'schema_version': 1, 'image_sha256': image_hash,
            'contract_sha256': fingerprint(contract), 'checks': rows,
            'evidence_qa': evidence_report,
            'disposition': 'REVIEW_DRAFT' if 'CRITICAL_ERROR' in statuses else
                           'REVIEW_REQUIRED' if 'NEEDS_REVIEW' in statuses else 'CHECKED_ITEMS_ONLY',
            'scientific_expert_review': 'NOT_PERFORMED',
            'notice': 'PASS applies only to listed checks and supplied observations. No automatic image recognition or expert certification.',
            'observation_basis': basis}
