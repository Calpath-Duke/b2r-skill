"""Compile one Figure Contract + layout plan into Classic/Refined image requests.

The host still understands the science and writes the plan. This module only
turns the shared relations, layout and labels into consistent requests so the two
options cannot drift apart, and emits the matching image-QA checklist.
"""
from common import require, text_value, fields
from scientific_qa import validate_contract, fingerprint
from visual_grammar import relation_instruction, entity_instruction, checklist, DEPICTIONS

ARCHITECTURES = {
    'pathway': 'mechanism pathway: upstream signals at the start, compartments as thin lanes or bands '
               '(extracellular / membrane / cytoplasm / nucleus) and one dominant flow direction to effector '
               'and outcome; parallel inputs run as parallel lanes that converge',
    'staged_process': 'staged process strip: 3-6 numbered stages in one row (wrap once at most), the same '
                      'object keeps its identity across stages, one transition arrow between neighbours',
    'taxonomy_convergence': 'taxonomy convergence: each family is a separate module holding its member '
                            'methods/items, members gathered by bracket lines to the family label, family '
                            'labels converge with arrows onto one outcome node',
    'workflow': 'research workflow: inputs, procedures, readouts, integration and conclusion in reading '
                'order; parallel branches merge at the integration step',
    'hub_spoke': 'hub-and-spoke overview: the central theme as a hub, domain sectors or satellite modules '
                 'of equal visual weight around it, each listing its members',
    'multiscale': 'multi-scale zoom: tissue or organ context, magnification callout to the cell, then to '
                  'the molecular mechanism, with zoom lines connecting the scales',
    'comparison': 'side-by-side comparison: aligned panels with identical layout per condition; only the '
                  'differing elements change',
    'cycle': 'cycle: stations around a loop with directional arrows; the return path runs outside',
}

CLASSIC = (
    'STYLE - Scientific 2D Classic (journal schematic, as in Nature Reviews or Trends review figures): '
    'pure white background; every object is a clean scientific symbol with one uniform dark-grey outline '
    '(same stroke weight everywhere) and one flat fill; 4-5 muted semantic colours plus grey, each colour '
    'meaning one object family throughout. No gradients, highlights, gloss, textures, grain, drop shadows, '
    'glow, 3D shading or perspective. Membranes are a simple double line; proteins are flat rounded '
    'silhouettes; cells are outline contours with only the organelles the mechanism needs; complexes are '
    'touching flat shapes. Modules are separated by whitespace, thin rules or very light tinted panels with '
    'bold titles - not heavy cards, clip-art or poster graphics. Connectors are thin uniform charcoal lines '
    'with small filled heads; inhibition uses flat T-bars. Clean sans-serif labels, sentence case, two or '
    'three consistent sizes, placed beside objects with short leader lines.')

REFINED = (
    'STYLE - Scientific 2D Refined (polished biomedical illustration for a review journal): the same '
    'objects, relations, positions, colours and labels as the plan, now drawn as refined 2D illustration: '
    'gentle two-tone shading inside shapes, soft gradients, delicate lipid-bilayer membranes, the needed '
    'organelles, slight overlaps for layering and a softly tinted contextual backdrop for tissue or '
    'extracellular space. Depth stays modest and evenly lit: no specular highlights, glossy spheres, '
    'photoreal or 3D rendering, or heavy shadows. Arrows and T-bars stay crisp flat vector lines above the '
    'artwork; labels stay clean sans-serif on clear background.')

EXCLUDE = ('Draw each named object once unless the layout names a second appearance. Do not add mechanisms, '
           'arrows, molecules, numbers, statistics, references, legends or text that are not listed. Never draw '
           'chemical skeletal formulas, rings or bonds for drugs. No watermark.')

# Image models drop or misplace these first, so they are stated before the flow.
KEY = {'inhibition', 'neutralization', 'cleavage', 'modification'}
CHAINABLE = {'activation', 'causation', 'conversion'}


def simple(rel, guard):
    return (rel['relation'] in CHAINABLE and not rel.get('label') and not rel.get('encoding') and
            not guard.get('conditions') and rel.get('evidence', {}).get('status') != 'hypothesis')


def chains(rels):
    """Merge A->B, B->C into one path statement where B has no other simple edge."""
    out_deg, in_deg = {}, {}
    for r in rels:
        out_deg[r['subject']] = out_deg.get(r['subject'], 0) + 1
        in_deg[r['object']] = in_deg.get(r['object'], 0) + 1
    by_subject = {r['subject']: r for r in rels if out_deg[r['subject']] == 1}
    linked = lambda node: in_deg.get(node, 0) == 1 and out_deg.get(node, 0) == 1
    starts = [r for r in rels if not linked(r['subject'])]
    paths, used = [], set()
    for r in starts + rels:
        if r['id'] in used: continue
        path = [r]; used.add(r['id'])
        while linked(path[-1]['object']) and by_subject[path[-1]['object']]['id'] not in used:
            path.append(by_subject[path[-1]['object']]); used.add(path[-1]['id'])
        paths.append(path)
    return paths


def validate_plan(plan, contract):
    fields(plan, ['schema_version', 'title', 'purpose', 'aspect', 'architecture', 'regions',
                  'reading_order', 'refined_stage', 'notes'], 'render plan')
    require(plan.get('schema_version') == 1, 'render plan schema_version 需为 1')
    for key in ('title', 'purpose', 'reading_order'):
        text_value(plan.get(key), key, 2000)
    arch = plan.get('architecture')
    arch = [arch] if isinstance(arch, str) else arch
    require(isinstance(arch, list) and 1 <= len(arch) <= 2 and all(a in ARCHITECTURES for a in arch),
            '构图 architecture 需为 1-2 个已知结构：' + ', '.join(ARCHITECTURES))
    regions = plan.get('regions')
    require(isinstance(regions, list) and regions, 'regions 不能为空')
    known = {e['id'] for e in contract['entities']}
    placed = []
    for region in regions:
        fields(region, ['id', 'label', 'position', 'contains', 'note'], 'region')
        for key in ('id', 'position'): text_value(region.get(key), key, 1000)
        contains = region.get('contains', [])
        require(isinstance(contains, list) and all(c in known for c in contains), 'region.contains 引用未知实体')
        placed += contains
    if 'refined_stage' in plan: text_value(plan['refined_stage'], 'refined_stage', 2000)
    return arch, sorted(known - set(placed))


def compile_requests(contract, plan, evidence_report=None):
    validate_contract(contract)
    arch, unplaced = validate_plan(plan, contract)
    names = {e['id']: e['label'] for e in contract['entities']}
    kinds = {e['id']: e['kind'] for e in contract['entities']}
    held = {}
    if evidence_report:
        for g in evidence_report['render_constraints']:
            held[g['relation_id']] = g
    head = f'Title: "{plan["title"]}". Purpose: {plan["purpose"]}. Canvas {plan.get("aspect", "16:9")} landscape.'
    lines = ['LAYOUT - ' + '; combined with '.join(ARCHITECTURES[a] for a in arch) + '.']
    for region in plan['regions']:
        members = ', '.join(names[c] for c in region.get('contains', []))
        label = f' titled "{region["label"]}"' if region.get('label') else ''
        lines.append(f'- {region["position"]}: region{label}' + (f' containing {members}' if members else '') +
                     (f'; {region["note"]}' if region.get('note') else '') + '.')
    lines.append(f'Reading order: {plan["reading_order"]}.')
    blocked, key, relations, complexes, flow = [], [], [], {}, []
    for rel in contract['relations']:
        guard = held.get(rel['id'], {})
        if guard.get('action') == 'clarify_conflict_preserve_user_input':
            blocked.append(rel['id']); continue
        if rel['relation'] in {'composition', 'membership'} and not guard.get('conditions'):
            group = (rel['relation'], rel['object'])
            if group not in complexes:
                complexes[group] = []
                relations.append(group)
            complexes[group].append(names[rel['subject']])
            continue
        if simple(rel, guard):
            flow.append(rel); continue
        text = relation_instruction(rel, names, kinds)
        if guard.get('conditions'):
            text += f'; mark this connector with an asterisk (*) and add one small footnote at the bottom: "* {guard["conditions"]}"'
        critical = rel['relation'] in KEY or rel.get('encoding') == 'blocked' or rel.get('subject_site') or rel.get('object_site')
        (key if critical else relations).append(text)
    def grouped(group):
        kind, obj = group
        members = ', '.join(complexes[group])
        if kind == 'composition':
            return f'{members} drawn as abutting components of one assembled {names[obj]}, with no arrows between the components'
        return f'the "{names[obj]}" module groups {members} (inside the module or joined by a bracket line), with no arrows among them'
    relations = [grouped(r) if isinstance(r, tuple) else r for r in relations]
    paths = chains(flow)
    targets = {}
    for path in paths:
        if len(path) == 1: targets.setdefault(path[0]['object'], []).append(path[0])
    converging = {o for o, group in targets.items() if len(group) > 1}
    for path in paths:
        if len(path) == 1 and path[0]['object'] in converging:
            obj = path[0]['object']
            if obj in targets:
                sources = ', '.join(names[r['subject']] for r in targets.pop(obj))
                relations.append(f'separate converging arrows from {sources}, each arrowhead ending on {names[obj]}')
            continue
        nodes = [names[path[0]['subject']]] + [names[r['object']] for r in path]
        relations.append('solid arrows in sequence ' + ' → '.join(nodes) + ', each arrowhead ending on the next object')
    if key:
        lines.append('KEY INTERACTIONS - most important, draw precisely:')
        lines += [f'- {t}.' for t in key]
    lines.append('RELATIONS - draw exactly these connections; each connector touches only the named objects:')
    lines += [f'{i}. {t}.' for i, t in enumerate(relations, 1)]
    depictions = [d for d in (entity_instruction(e) for e in contract['entities']) if d]
    if depictions:
        lines.append('OBJECT DEPICTION - ' + '; '.join(depictions) + '.')
    labels = ([names[e] for e in names] + [r['label'] for r in plan['regions'] if r.get('label')] +
              [l['value'] for l in contract.get('labels', [])])
    labels = list(dict.fromkeys(labels))
    lines.append('LABELS - spell exactly: ' + ', '.join(f'"{l}"' for l in labels) + '.')
    if plan.get('notes'): lines.append(plan['notes'])
    lines.append(EXCLUDE)
    shared = '\n'.join(lines)
    refined_stage = plan.get('refined_stage')
    classic = '\n'.join([head, CLASSIC, shared])
    refined = '\n'.join([head, REFINED + (f' Context staging for this option only: {refined_stage}.'
                                          if refined_stage else ''), shared])
    warnings = [f'实体未放入任何区域：{", ".join(unplaced)}'] if unplaced else []
    if blocked:
        warnings.append('CONFLICTED 关系未写入请求，需先与用户确认：' + ', '.join(blocked))
    return {'schema_version': 1, 'contract_sha256': fingerprint(contract), 'plan_sha256': fingerprint(plan),
            'architecture': arch, 'requests': {'classic2d': classic, 'refined2d': refined},
            'qa_checklist': checklist(contract, {g['relation_id']: g.get('conditions', '') for g in held.values()}), 'blocked_relations': blocked, 'warnings': warnings,
            'notice': 'Requests are compiled from the host plan; the generated images still need actual viewing and QA.'}


def compile_correction(contract, report):
    """Turn critical image-QA rows into one targeted edit request; everything that passed is kept."""
    validate_contract(contract)
    require(report.get('contract_sha256') == fingerprint(contract), 'QA 报告与当前契约不匹配')
    names = {e['id']: e['label'] for e in contract['entities']}
    kinds = {e['id']: e['kind'] for e in contract['entities']}
    named = lambda v: names.get(v, v) if isinstance(v, str) else v
    rels = {'relation:'+r['id']: r for r in contract['relations']}
    ents = {'entity:'+e['id']: e for e in contract['entities']}
    labels = {'label:'+l['id']: l for l in contract.get('labels', [])}
    fixes, keep, targets = [], [], []
    for row in report['checks']:
        if row['axis'] != 'image': continue
        t, diff = row['target'], row.get('differences', {})
        if row['status'] == 'PASS':
            if t in rels:
                r = rels[t]
                keep.append(relation_instruction(r, names, kinds) if r['relation']=='modification'
                            else f"{names[r['subject']]} {r['relation']} {names[r['object']]}")
            continue
        if row['status'] != 'CRITICAL_ERROR': continue
        where = f" (near {row['location']})" if row.get('location') else ''
        if t in rels:
            r = rels[t]
            text = f"Fix {names[r['subject']]} {r['relation']} {names[r['object']]}{where}: " + relation_instruction(r, names, kinds)
            seen = [f"{k} {named(v['observed']) or '(none)'}" for k, v in diff.items() if k != 'condition_shown']
            if seen: text += '; the image currently shows ' + ', '.join(seen)
            if 'condition_shown' in diff: text += f'; write the condition next to it: "{diff["condition_shown"]["expected"]}"'
            if not diff: text += '; it is missing from the image'
        elif t in ents:
            e = ents[t]
            text = (f'Replace the drawn chemical structure of "{e["label"]}"{where} with a {DEPICTIONS["token"]}'
                    if 'depiction' in diff else f'Add "{e["label"]}", which is missing')
        elif t in labels:
            text = f'Correct the text{where} to "{labels[t]["value"]}"' + (
                f' (currently "{diff["value"]["observed"]}")' if 'value' in diff else '')
        else:
            for x in row.get('unexpected_relations', []):
                if x['assessment'] != 'conflicting': continue
                o = x['observed']
                fixes.append(f"Remove the extra {o['relation']} connector from {named(o['subject'])} to "
                             f"{named(o['object'])} near {x['location']}")
                targets.append({'target': t, 'location': x['location']})
            continue
        fixes.append(text); targets.append({'target': t, 'location': row.get('location')})
    if not fixes:
        return {'request': None, 'targets': [], 'keep': keep, 'strategy': 'none',
                'notice': 'No CRITICAL_ERROR rows; unresolved NEEDS_REVIEW items need viewing, not an edit.'}
    lines = ['Edit this figure. Make only these corrections:'] + [f'{i}. {f}.' for i, f in enumerate(fixes, 1)]
    if keep: lines.append('Keep these relations exactly as drawn: ' + '; '.join(keep) + '.')
    lines.append('Change nothing else: same layout, objects, colours, style and all other labels.')
    # Tested: bitmap edits failed to move objects even for two fixes; many fixes means regenerate.
    strategy = 'targeted_edit_or_vector_overlay' if len(fixes) <= 3 else 'regenerate_from_compiled_request_then_recheck'
    return {'request': '\n'.join(lines), 'targets': targets, 'keep': keep, 'strategy': strategy,
            'notice': 'Moving endpoints, T-bars and text is more reliable as a vector overlay on the image than as a bitmap edit; re-run QA on the result.'}
