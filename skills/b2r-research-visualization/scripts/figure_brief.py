"""Optional host-authored planning records. No NLP classifier or visual evaluator."""
from common import require, text_value, digest, write_json

STATES = {'user_provided', 'source_statement', 'user_hypothesis',
          'author_hypothesis', 'ai_inference', 'visual_simplification'}
RELATIONS = {'composition', 'binding', 'activation', 'inhibition', 'transport',
             'conversion', 'release', 'causation', 'association'}
VISUAL_TARGETS = {'order', 'identity', 'style', 'layout', 'file'}
TEXT_TARGETS = VISUAL_TARGETS | {'content', 'relations', 'labels', 'values'}


def strings(value, name):
    require(isinstance(value, list), f'{name} 必须是列表')
    for item in value:
        text_value(item, name, 10000)
    return value


def evidence_source(value):
    """Retain structured provenance used by host workflows instead of flattening it."""
    if isinstance(value, str):
        text_value(value, 'source', 20000)
        return
    require(isinstance(value, dict), 'source 需为摘录/定位文本或来源对象')
    require(any(isinstance(value.get(k), str) and value[k].strip()
                for k in ['excerpt', 'citation', 'locator']), 'source 对象缺少摘录或真实定位')
    for key in ['excerpt', 'citation', 'locator']:
        if key in value:
            text_value(value[key], 'source '+key, 20000)
    if 'verified' in value:
        require(isinstance(value['verified'], bool), 'source.verified 必须是布尔值')


def validate_brief(brief):
    """Check a record's integrity, not scientific truth or prompt completeness."""
    if isinstance(brief, str):
        text_value(brief, 'figure_brief', 20000)
        return TEXT_TARGETS
    require(isinstance(brief, dict), 'figure_brief 必须是对象')
    for key in ['original_request', 'topic', 'purpose']:
        text_value(brief.get(key), key, 20000)
    entities = brief.get('entities')
    require(isinstance(entities, list) and entities, 'entities 不能为空')
    ids = set()
    for entity in entities:
        require(isinstance(entity, dict), 'entity 必须是对象')
        for key in ['id', 'label', 'kind', 'visual']:
            text_value(entity.get(key), key, 10000)
        evidence_source(entity.get('source'))
        require(entity['id'] not in ids, '重复 entity id')
        require(entity.get('status') in STATES, 'entity 证据状态无效')
        ids.add(entity['id'])
    relations = brief.get('relations')
    require(isinstance(relations, list), 'relations 必须是列表')
    relation_ids = set()
    for rel in relations:
        require(isinstance(rel, dict), 'relation 必须是对象')
        text_value(rel.get('id'), 'relation id')
        evidence_source(rel.get('source'))
        require(rel['id'] not in relation_ids, '重复 relation id')
        require(rel.get('subject') in ids and rel.get('object') in ids,
                'relation 端点必须引用已有科学对象')
        require(rel.get('type') in RELATIONS, 'relation 类型无效')
        require(rel.get('status') in STATES, 'relation 证据状态无效')
        require(rel['status'] != 'visual_simplification' or rel['type'] in {'composition', 'association'},
                '视觉简化不能支持新增方向性生物关系')
        relation_ids.add(rel['id'])
    for key in ['stages', 'outcomes', 'labels', 'protected_values', 'unknowns', 'locks']:
        strings(brief.get(key), key)
    composition = brief.get('composition')
    require(isinstance(composition, dict), 'composition 必须是对象')
    for key in ['layout', 'reading_order']:
        text_value(composition.get(key), key, 10000)
    strings(composition.get('regions'), 'regions')
    style = brief.get('style')
    require(isinstance(style, dict), 'style 必须是对象')
    text_value(style.get('name'), 'style name', 200)
    text_value(style.get('reason'), 'style reason', 10000)
    return ({'entity:'+i for i in ids} | {'relation:'+i for i in relation_ids}
            | {'label:'+str(i) for i in range(len(brief['labels']))}
            | {'value:'+str(i) for i in range(len(brief['protected_values']))}
            | VISUAL_TARGETS)


def prepare_context(record, image):
    """Bind human/model observation records to the actual image, never auto-pass it."""
    observations = record.get('host_observations', {})
    if not isinstance(observations, dict) or 'figure_brief' not in observations:
        return None  # Backward compatible with all previous host records.
    brief = observations['figure_brief']
    required = validate_brief(brief)
    gate = observations.get('quality_gate')
    report = {'status': 'PENDING', 'scientific_expert_review': 'PENDING',
              'notice': 'Record coverage only; not automated image understanding or scientific certification.',
              'image_sha256': digest(image), 'missing_targets': sorted(required)}
    if gate is not None:
        require(isinstance(gate, dict), 'quality_gate 必须是对象')
        require(gate.get('image_sha256') == report['image_sha256'],
                'quality_gate 哈希不匹配：不能沿用另一张图的查看记录')
        text_value(gate.get('method'), 'quality_gate method', 10000)
        checks = gate.get('checks')
        require(isinstance(checks, list), 'quality_gate checks 必须是列表')
        seen = set()
        for check in checks:
            require(isinstance(check, dict), 'quality check 必须是对象')
            target = check.get('target')
            require(target in required and target not in seen, '未知或重复 quality target')
            require(check.get('status') in {'observed', 'issue', 'not_verified'}, 'quality check status 无效')
            text_value(check.get('observation'), '具体查看发现', 10000)
            seen.add(target)
        missing = sorted(required - seen)
        pending = [c['target'] for c in checks if c['status'] == 'not_verified']
        issues = [c for c in checks if c['status'] == 'issue']
        status = 'HAS_FINDINGS' if issues else 'INCOMPLETE' if missing or pending else 'HOST_REVIEW_RECORDED'
        report.update(status=status, method=gate['method'], checks=checks,
                      missing_targets=missing, unverified_targets=pending, issues=issues)
    return {'brief': brief, 'gate': report}


def save_context(context, folder):
    if context is None:
        return None
    if isinstance(context['brief'], str):
        (folder/'figure-brief.md').write_text(context['brief'], encoding='utf-8')
    else:
        write_json(folder/'figure-brief.json', context['brief'])
    write_json(folder/'quality-gate.json', context['gate'])
    return {k: context['gate'][k] for k in ['status', 'scientific_expert_review', 'missing_targets']}
