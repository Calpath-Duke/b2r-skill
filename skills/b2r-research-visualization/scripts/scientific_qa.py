"""Compare a Figure Contract with hash-bound host observations, not image pixels.

The host must inspect the image and supply observations. This module neither
recognizes images nor verifies papers, and never certifies scientific truth.
"""
from datetime import date
import hashlib
import json

from common import require, text_value, digest

RELATIONS = {'composition', 'binding', 'activation', 'inhibition', 'transport',
             'migration', 'conversion', 'release', 'causation', 'association',
             'presentation'}
FIELDS = ('subject', 'relation', 'object', 'direction', 'origin',
          'subject_site', 'object_site')


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
        if rel['relation'] in {'activation', 'inhibition', 'migration', 'transport', 'release', 'causation', 'presentation'}:
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
    return targets


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
    return {'schema_version': 1, 'id': 'brief-contract', 'original_request': brief['original_request'],
            'entities': [{k: e[k] for k in ('id', 'label', 'kind')} for e in brief['entities']],
            'relations': relations,
            'labels': [{'id': str(i), 'value': t} for i, t in enumerate(brief['labels']+brief['protected_values'])]}


def evaluate(contract, observation, image):
    targets = validate_contract(contract)
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
                missing = [k for k in fields if not isinstance(actual.get(k), str) or not actual[k].strip()]
                if missing:
                    row['missing_observation_fields'] = missing
                else:
                    differences = {k: {'expected': expected[k], 'observed': actual[k]}
                                   for k in fields if actual[k] != expected[k]}
                    row['status'] = ('CRITICAL_ERROR' if expected.get('critical', True) else 'NEEDS_REVIEW') if differences else 'PASS'
                    if differences: row['differences'] = differences
        rows.append(row)
    statuses = {r['status'] for r in rows}
    return {'schema_version': 1, 'image_sha256': image_hash,
            'contract_sha256': fingerprint(contract), 'checks': rows,
            'disposition': 'REVIEW_DRAFT' if 'CRITICAL_ERROR' in statuses else
                           'REVIEW_REQUIRED' if 'NEEDS_REVIEW' in statuses else 'CHECKED_ITEMS_ONLY',
            'scientific_expert_review': 'NOT_PERFORMED',
            'notice': 'PASS applies only to listed checks and supplied observations. No automatic image recognition or expert certification.',
            'observation_basis': basis}
