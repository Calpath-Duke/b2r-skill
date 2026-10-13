"""Validate host-retrieved claim evidence. No search client or topic classifier.

The host decides risk, reads sources and records scope. These checks prevent
missing/stale/metadata-only records from being presented as verified science;
they do not authenticate citations or independently interpret a paper.
"""
from urllib.parse import urlsplit

from common import require, text_value

RISKS = {'missing_relation', 'ambiguous_target', 'uncertain_direction',
         'suspected_error', 'model_added_mechanism', 'condition_dependent'}
STATES = {'SUPPORTED', 'CONDITIONAL', 'CONFLICTED', 'NOT_FOUND', 'UNVERIFIED'}


def verification_decision(contract):
    """Route a host assessment, never infer biology from keywords."""
    assessment = contract.get('verification')
    if assessment is None:
        return {'action': 'NOT_ASSESSED', 'relation_ids': [],
                'reason': 'Legacy contract; no risk assessment recorded.'}
    require(isinstance(assessment, dict), 'verification 必须为对象')
    network = assessment.get('network')
    require(network in {'allowed', 'forbidden', 'unavailable'}, 'network 状态无效')
    text_value(assessment.get('note'), '风险判断说明', 10000)
    risks = assessment.get('risks')
    require(isinstance(risks, list), 'verification.risks 必须为列表')
    known = {r['id'] for r in contract['relations']}
    selected = []
    for risk in risks:
        require(isinstance(risk, dict), 'risk 必须为对象')
        rid = risk.get('relation_id')
        require(rid in known and rid not in selected, '风险关系未知或重复')
        reasons = risk.get('reasons')
        require(isinstance(reasons, list) and reasons and
                all(isinstance(r, str) and r in RISKS for r in reasons), '风险原因无效')
        text_value(risk.get('note'), '具体科学缺口', 10000)
        selected.append(rid)
    action = 'SKIP' if not selected else 'VERIFY' if network == 'allowed' else 'BLOCKED'
    return {'action': action, 'network': network, 'relation_ids': selected,
            'reason': assessment['note']}


def validate_ledger(contract, ledger):
    from scientific_qa import fingerprint, dated
    require(isinstance(ledger, dict) and ledger.get('schema_version') == 1,
            'evidence_ledger.schema_version 需为 1')
    require(ledger.get('contract_sha256') == fingerprint(contract), '证据台账不属于此契约/条件')
    plan = verification_decision(contract)
    require(plan['action'] != 'NOT_ASSESSED', '证据台账需要当前风险判断')
    searches, sources, claims = {}, {}, {}
    for key in ('searches', 'sources', 'claims'):
        require(isinstance(ledger.get(key), list), 'ledger.'+key+' 必须为列表')
    for search in ledger['searches']:
        require(isinstance(search, dict), 'search 必须为对象')
        for key in ('id', 'query', 'tool', 'tool_reference'):
            text_value(search.get(key), 'search.'+key, 4000)
        require(search['id'] not in searches, '重复 search id')
        require(search.get('outcome') in {'completed', 'failed'}, 'search outcome 无效')
        require(search.get('public_terms_only') is True, '台账仅收录公开关键词检索；非公开材料需独立授权')
        dated(search.get('checked_at'))
        if search['outcome'] == 'failed': text_value(search.get('error'), '实际检索失败原因', 4000)
        searches[search['id']] = search
    require(plan['network'] != 'forbidden' or not searches, '用户禁止联网，不能执行检索')
    require(plan['network'] != 'unavailable' or not any(s['outcome'] == 'completed' for s in searches.values()),
            '网络不可用不能声称在线检索完成')
    require(plan['action'] != 'SKIP' or not searches, '无风险任务不应产生外部检索')
    for source in ledger['sources']:
        require(isinstance(source, dict), 'source 必须为对象')
        for key in ('id', 'title', 'url'):
            text_value(source.get(key), 'source.'+key, 4000)
        url = urlsplit(source['url'])
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                '来源需为无凭据的 HTTPS 地址')
        require(source['id'] not in sources, '重复 source id')
        require(source.get('read_scope') in {'metadata', 'abstract', 'full_text'}, '阅读范围无效')
        dated(source.get('checked_at'))
        refs = source.get('search_ids')
        require(isinstance(refs, list) and refs and all(isinstance(s, str) and s in searches and
                searches[s]['outcome'] == 'completed' for s in refs), '来源缺少实际完成的检索/读取记录')
        integrity = source.get('integrity', {})
        require(isinstance(integrity, dict) and integrity.get('status') in
                {'not_checked', 'none_observed', 'corrected', 'retracted', 'expression_of_concern'},
                '记录来源的撤稿/更正检查范围')
        text_value(integrity.get('note'), '撤稿/更正说明', 4000)
        if integrity['status'] in {'corrected', 'retracted', 'expression_of_concern'}:
            text_value(integrity.get('locator'), '更正/撤稿可追溯定位', 2000)
        sources[source['id']] = source
    known = {r['id'] for r in contract['relations']}
    for claim in ledger['claims']:
        require(isinstance(claim, dict), 'claim 必须为对象')
        rid = claim.get('relation_id')
        require(rid in known and rid not in claims, 'claim 关系未知或重复')
        state = claim.get('status')
        require(state in STATES, 'claim evidence status 无效')
        require(claim.get('origin') in {'user_result', 'user_statement', 'external_literature', 'model_inference'},
                'claim.origin 需区分实验结果、用户陈述、外部证据与推断')
        text_value(claim.get('note'), '逐关系证据结论', 10000)
        search_ids = claim.get('search_ids', [])
        require(isinstance(search_ids, list) and all(isinstance(s, str) and s in searches for s in search_ids),
                'claim.search_ids 引用未知')
        assessments = claim.get('assessments', [])
        require(isinstance(assessments, list), 'claim.assessments 必须为列表')
        support, limited, contradict = [], [], []
        seen = set()
        for item in assessments:
            require(isinstance(item, dict), 'assessment 必须为对象')
            sid = item.get('source_id')
            require(sid in sources and sid not in seen, 'assessment 来源未知或重复')
            seen.add(sid)
            src = sources[sid]
            require(set(src['search_ids']) & set(search_ids), 'claim 未关联对应来源的读取记录')
            require(item.get('finding') in {'supports', 'contradicts', 'unclear'}, 'finding 无效')
            require(item.get('scope_match') in {'matched', 'limited', 'unknown'}, 'scope_match 无效')
            for key in ('passage', 'summary', 'scope_note'):
                text_value(item.get(key), 'assessment.'+key, 10000)
            readable = src['read_scope'] != 'metadata'
            usable = src['integrity']['status'] not in {'retracted', 'expression_of_concern'}
            if src['integrity']['status'] == 'corrected':
                usable = item.get('correction_reviewed') is True
            if readable and usable and item['scope_match'] == 'matched':
                if item['finding'] == 'supports': support.append(sid)
                if item['finding'] == 'contradicts': contradict.append(sid)
            if readable and usable and item['finding'] == 'supports' and item['scope_match'] == 'limited':
                limited.append(sid)
        if state == 'SUPPORTED':
            require(support and set(support) == seen and not limited and not contradict,
                'SUPPORTED 需实际内容与条件匹配，不能忽略限制或反证')
        elif state == 'CONDITIONAL':
            require((limited or support) and not contradict, 'CONDITIONAL 需要可用的条件性支持')
            text_value(claim.get('conditions'), '必须保留的适用条件', 10000)
        elif state == 'CONFLICTED':
            require(contradict, 'CONFLICTED 需要可追溯且适用的反证，不以证据缺失冒充错误')
        elif state == 'NOT_FOUND':
            require(any(searches[s]['outcome'] == 'completed' for s in search_ids),
                    'NOT_FOUND 需要实际完成的有界检索')
            require(not support and not limited and not contradict, '已有支持或反证不能标记 NOT_FOUND')
        if plan['network'] != 'allowed':
            require(state == 'UNVERIFIED', '禁止/不可用网络的本轮外部核验只能为 UNVERIFIED')
        claims[rid] = claim
    return claims


def evaluate_evidence(contract, ledger=None):
    from scientific_qa import validate_contract, fingerprint, FIELDS
    validate_contract(contract)
    plan = verification_decision(contract)
    claims = validate_ledger(contract, ledger) if ledger is not None else {}
    rows, guards = [], []
    for rel in contract['relations']:
        claim = claims.get(rel['id'])
        state = claim['status'] if claim else 'UNVERIFIED'
        rows.append({'relation_id': rel['id'], 'evidence_status': state,
                     'origin': claim['origin'] if claim else 'not_recorded',
                     'status': 'PASS' if state == 'SUPPORTED' else 'NEEDS_REVIEW',
                     'note': claim['note'] if claim else '本轮没有逐关系外部核验记录。',
                     'source_ids': [a['source_id'] for a in claim.get('assessments', [])] if claim else [],
                     'conditions': claim.get('conditions', '') if claim else ''})
        guards.append({'relation_id': rel['id'], **{k: rel[k] for k in FIELDS if k in rel},
                       'context': rel['context'], 'evidence_status': state,
                       'conditions': claim.get('conditions', '') if claim else '',
                       'action': 'clarify_conflict_preserve_user_input' if state == 'CONFLICTED' else
                                 'retain_conditions' if state == 'CONDITIONAL' else
                                 'do_not_complete_missing_mechanism' if state in {'UNVERIFIED', 'NOT_FOUND'} else
                                 'preserve_verified_relation'})
    return {'schema_version': 1, 'contract_sha256': fingerprint(contract),
            'ledger_sha256': fingerprint(ledger) if ledger is not None else None,
            'decision': plan, 'claims': rows, 'render_constraints': guards,
            'scientific_expert_review': 'NOT_PERFORMED',
            'notice': 'Host retrieval and source interpretation records; validation does not prove citation authenticity. NOT_FOUND is limited to recorded searches. User results are never overwritten.'}
