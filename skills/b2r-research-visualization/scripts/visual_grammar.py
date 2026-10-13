"""Relation/entity visual grammar shared by render requests and image QA.

One table decides how each contract relation must look and which glyphs an
observer may report for it. Requests are compiled from the table; QA compares the
glyph the host actually saw. It does not recognize pixels or judge biology.
"""
from common import require, text_value

ENCODINGS = {
    'arrow': 'solid line ending in a filled arrowhead on the object',
    'dashed_arrow': 'dashed line ending in an arrowhead',
    't_bar': 'line ending in a flat perpendicular bar on the object, no arrowhead',
    'contact': 'shapes touch at the stated site, no connector line',
    'blocked': 'interaction drawn interrupted by a bar or cross at the blocked step',
    'cut': 'scissors or break mark on the substrate, product drawn separately',
    'merge': 'components drawn abutting as one assembled complex',
    'grouped': 'placed inside the family module or joined to its label by a bracket line',
    'line': 'plain line without arrowheads',
    'fragments': 'object drawn broken into fragments',
}
OBSERVED_ENCODINGS = set(ENCODINGS) | {'none', 'unclear'}

# relation -> (acceptable observed encodings, default encoding, request template)
GRAMMAR = {
    'activation': (('arrow', 'dashed_arrow'), 'arrow',
                   'solid arrow from {s} whose arrowhead ends on {o}'),
    'inhibition': (('t_bar',), 't_bar',
                   'place {s} right beside {o}; a short flat T-bar (⊣) from {s}{ssite} touches {o}{osite}; no arrowhead on this line'),
    'neutralization': (('contact', 'blocked', 't_bar'), 'contact',
                       'place {s} right beside {o}: {s} physically captures {o}{osite} and the captured {o} is '
                       'shown blocked from acting (bar or cross on that step); never an arrow from {s} to {o}'),
    'binding': (('contact', 'blocked'), 'contact', '{s}{ssite} touches {o}{osite}; no arrow between them'),
    'cleavage': (('cut', 'arrow'), 'cut',
                 '{s} is the enzyme acting on {o}: draw {o} cut (break mark) with its product drawn '
                 'separately; {s} points at {o}, not at the product'),
    'conversion': (('arrow',), 'arrow', 'transform arrow from {s} to its product {o}, both labeled'),
    'composition': (('merge', 'contact'), 'merge',
                    '{s} drawn as an abutting component inside the assembled {o}'),
    'membership': (('grouped', 'line'), 'grouped',
                   '{s} is listed inside the {o} module or joined to it by a bracket line; no arrow'),
    'transport': (('arrow', 'dashed_arrow'), 'arrow',
                  'path arrow moving {s} from {origin} into {o}'),
    'migration': (('arrow', 'dashed_arrow'), 'arrow',
                  'path arrow moving {s} from {origin} to {o}'),
    'release': (('arrow', 'dashed_arrow'), 'arrow',
                'arrow from {s} to the released {o}, which keeps its identity'),
    'degradation': (('fragments', 'arrow'), 'fragments',
                    '{o} shown broken into fragments next to {s}'),
    'causation': (('arrow', 'dashed_arrow'), 'arrow', 'arrow from {s} to {o}'),
    'association': (('line',), 'line', 'plain line between {s} and {o} without arrowheads (association, not cause)'),
    'presentation': (('contact',), 'contact', '{s}{ssite} directly contacts {o}{osite} (antigen presentation); no arrow between them'),
}
DEPICTIONS = {
    'token': 'labeled token (rounded tag or capsule with the name); no bonds, rings or skeletal formula',
    'glyph': 'simple schematic symbol identified by its label',
    'verified_structure': 'structure rendered by code from the cited structure source, not by the image model',
}
OBSERVED_DEPICTIONS = {'token', 'glyph', 'chemical_structure', 'verified_structure', 'unclear'}
SMALL_MOLECULE_KINDS = {'small_molecule', 'small-molecule drug', 'compound'}


def relation_encoding(rel):
    allowed, default, _ = GRAMMAR[rel['relation']]
    hypothetical = rel.get('evidence', {}).get('status') == 'hypothesis'
    preferred = rel.get('encoding') or ('dashed_arrow' if hypothetical and 'dashed_arrow' in allowed else default)
    if rel['relation'] == 'binding':
        # A blocked binding means the opposite of a binding; neither stands in for the other.
        allowed = ('blocked',) if preferred == 'blocked' else tuple(a for a in allowed if a != 'blocked')
    return allowed, preferred


def entity_depiction(entity):
    if 'depiction' in entity:
        return entity['depiction']
    return 'token' if entity['kind'] in SMALL_MOLECULE_KINDS else None


def validate_grammar(contract):
    for rel in contract['relations']:
        if 'encoding' in rel:
            require(rel['encoding'] in GRAMMAR[rel['relation']][0],
                    f"{rel['id']} 的 encoding 与 {rel['relation']} 不相容")
    for entity in contract['entities']:
        if 'depiction' in entity:
            require(entity['depiction'] in DEPICTIONS, 'depiction 无效')
            if entity['depiction'] == 'verified_structure':
                text_value(entity.get('structure_source'), '化学结构来源（如 PubChem CID/SMILES）', 2000)


def is_antibody(kind):
    return 'antibody' in kind.casefold()


def relation_instruction(rel, names, kinds=None):
    template = GRAMMAR[rel['relation']][2]
    site = lambda key: f" at its {rel[key]}" if rel.get(key) else ''
    text = template.format(s=names[rel['subject']], o=names[rel['object']],
                           origin=names.get(rel.get('origin'), 'the origin'),
                           ssite=site('subject_site'), osite=site('object_site'))
    if rel.get('encoding') == 'blocked' and rel['relation'] == 'binding':
        text = (f"{names[rel['subject']]} faces {names[rel['object']]}{site('object_site')} but their binding is shown "
                "prevented: a small cross or bar between them, no connector arrow")
    elif rel.get('encoding') and rel['encoding'] != GRAMMAR[rel['relation']][1]:
        text += f"; draw it as a {ENCODINGS[rel['encoding']]}"
    elif rel.get('evidence', {}).get('status') == 'hypothesis':
        text += '; dashed with "?" because it is a hypothesis'
    if rel.get('label'):
        text += f'; label the connector "{rel["label"]}"'
    if (kinds and is_antibody(kinds[rel['subject']]) and rel.get('encoding') != 'blocked'
            and rel['relation'] in {'binding', 'inhibition', 'neutralization'}):
        # Image models default to an upright Y resting on its stem; the stem then touches the target.
        text += (f"; orient {names[rel['subject']]} so its two Fab arm tips open toward and touch {names[rel['object']]} "
                 f"and its single Fc stem points away (upside-down Y when {names[rel['object']]} is below it)")
    return text


def entity_instruction(entity):
    depiction = entity_depiction(entity)
    if depiction is None and not is_antibody(entity['kind']):
        return None
    if is_antibody(entity['kind']) and depiction in (None, 'glyph'):
        return f'"{entity["label"]}": Y-shaped antibody glyph; two Fab arm tips bind its target, Fc stem points away'
    return f'"{entity["label"]}": {DEPICTIONS[depiction]}'


def checklist(contract, conditions=None):
    """What the host must look for. Never prefilled with expected answers."""
    conditions = conditions or {}
    items = []
    for entity in contract['entities']:
        item = {'target': 'entity:'+entity['id'], 'look_for': f"Is {entity['label']} present and identifiable?",
                'report': ['id']}
        if entity_depiction(entity):
            item['report'].append('depiction')
            item['depiction_options'] = sorted(OBSERVED_DEPICTIONS)
        items.append(item)
    names = {e['id']: e['label'] for e in contract['entities']}
    for rel in contract['relations']:
        allowed, _ = relation_encoding(rel)
        fields = ['subject', 'relation', 'object', 'direction'] + [k for k in ('origin', 'subject_site', 'object_site', 'label') if k in rel]
        item = {'target': 'relation:'+rel['id'],
                'look_for': f"Which objects does the connector between {names[rel['subject']]} and "
                            f"{names[rel['object']]} actually touch, and what glyph sits at each end?",
                'report': fields+['encoding'], 'encoding_options': sorted(OBSERVED_ENCODINGS)}
        if conditions.get(rel['id']):
            item['report'].append('condition_shown')
            item['condition_options'] = ['yes', 'no', 'unclear']
            item['look_for'] += ' Is its evidence condition stated next to it?'
        items.append(item)
    for label in contract.get('labels', []):
        items.append({'target': 'label:'+label['id'], 'look_for': 'Exact visible text', 'report': ['value']})
    if contract['relations']:
        items.append({'target': 'unplanned_relations', 'look_for': 'Every other arrow, T-bar or contact line in the '
                      'image that is not one of the relations above: which objects it touches and its end glyph.',
                      'report': ['relation_scan']})
    return items
