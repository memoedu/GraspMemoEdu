"""Authored Topic sections and references to the existing training catalog.

References own neither question text nor scheduling state. Reading examples are
ungraded content; legacy Example/Practice modules retain their original meaning.
"""
import re

IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z')
REFERENCE_FIELDS = {'bank_id', 'group_id', 'question_id', 'version'}


def validate_reference(value):
    if not isinstance(value, dict) or set(value) != REFERENCE_FIELDS:
        raise ValueError('A bank question requires only its canonical source reference')
    for key in ('bank_id', 'group_id', 'question_id'):
        if not isinstance(value[key], str) or not IDENTIFIER.fullmatch(value[key]) or len(value[key]) > 64:
            raise ValueError('Invalid bank question reference identity')
    if not isinstance(value['version'], str) or not re.fullmatch(r'[a-f0-9]{64}', value['version']):
        raise ValueError('A bank question reference must pin its source version')


def validate_sections(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError('Topic sections must be a nonempty ordered array')
    seen = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {'id', 'title', 'level', 'parent_id'}:
            raise ValueError('Invalid authored Topic section')
        ident = row['id']
        if not isinstance(ident, str) or not IDENTIFIER.fullmatch(ident) or ident in seen:
            raise ValueError('Invalid or duplicate Topic section identity')
        if not isinstance(row['title'], str) or len(row['title']) > 300 or '\n' in row['title']:
            raise ValueError('Invalid Topic section title')
        if type(row['level']) is not int or not 1 <= row['level'] <= 6:
            raise ValueError('Invalid Topic section heading level')
        parent = row['parent_id']
        if parent is not None and (parent not in seen or seen[parent]['level'] >= row['level']):
            raise ValueError('Topic sections must preserve an acyclic parent-before-child heading tree')
        seen[ident] = row
    return seen


def authored_sequence(topic):
    return bool(topic.get('sections') or topic.get('bank_questions')
                or any(i.get('example') or i.get('footnotes') for i in topic.get('introductions', [])))


def question_references(topic):
    return topic.get('bank_questions', [])


def has_embedded_practice(topic):
    return bool(question_references(topic) or topic.get('practice_group'))


def practice_progress(con, learner_id, bank, group, answer_keys, *, finished=False):
    reference = {'bank_id': bank['id'], 'group_id': group['id'], 'version': bank['version']}
    required = [q['id'] for q in group['questions'] if answer_keys.get(q['id'])]
    completed = set()
    if required and con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_attempts'").fetchone():
        completed = {row[0] for row in con.execute('''SELECT DISTINCT question FROM training_attempts
            WHERE learner=? AND bank=? AND group_id=? AND version=? AND phase='done' ''',
            (learner_id, bank['id'], group['id'], bank['version']))}
    return {**reference, 'required_ids': required,
            'completed_ids': [ident for ident in required if ident in completed],
            'ready': finished or set(required) <= completed}


def completed_reference(con, learner_id, reference):
    """Use precisely the bank's existing completion criterion and version."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='training_attempts'").fetchone():
        return False
    return bool(con.execute('''SELECT 1 FROM training_attempts WHERE learner=? AND bank=?
        AND group_id=? AND question=? AND version=? AND phase='done' LIMIT 1''',
        (learner_id, reference['bank_id'], reference['group_id'], reference['question_id'], reference['version'])).fetchone())


def completion(con, learner_id, topic):
    return {item['id']: completed_reference(con, learner_id, item['reference']) for item in question_references(topic)}


def introduction_html(intro):
    """Compatibility readers and Q&A receive all visible reading fields."""
    return intro.get('html', '') + intro.get('example', '') + ''.join(note['html'] for note in intro.get('footnotes', []))


def section_for(topic, entry):
    ident = entry.get('section_id')
    return next((s for s in topic.get('sections', []) if s['id'] == ident), None)


def validate_reading_lineage(value, introduction_ids):
    if (not isinstance(value, dict) or set(value) != {'content_version', 'introductions'}
            or not isinstance(value['content_version'], str) or not value['content_version']
            or not isinstance(value['introductions'], dict) or not value['introductions']):
        raise ValueError('Invalid reading progress lineage')
    destinations = []
    for old_id, new_ids in value['introductions'].items():
        if (not IDENTIFIER.fullmatch(old_id) or not isinstance(new_ids, list)
                or any(not isinstance(i, str) or i not in introduction_ids for i in new_ids)):
            raise ValueError('Invalid reading progress mapping')
        destinations.extend(new_ids)
    if len(set(destinations)) != len(destinations) or set(destinations) != set(introduction_ids):
        raise ValueError('Reading lineage must cover each new Introduction once')
