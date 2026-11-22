"""Private, transactional Practice source shared by Lesson and review rounds.

One queue belongs to one learner/Topic/Example. Drawing means actually showing
a question, not reserving a round's target in advance. Scoring remains the
responsibility of PracticePolicy and the calling service.
"""

import json
import random


VERSION = 'grouped-v1'


def _error(code, message, status=409):
    # LearningService owns DomainError and imports this module during startup.
    from .service import DomainError
    return DomainError(code, message, status)


class PersistentPracticeQueue:
    VERSION = VERSION

    def __init__(self, learning, rng=None):
        self.learning = learning
        self.rng = rng or random.SystemRandom()

    @staticmethod
    def initialize_schema(con):
        # Do not use executescript: it commits an already-open transaction.
        con.execute('''CREATE TABLE IF NOT EXISTS practice_queues (
            learner TEXT NOT NULL, topic TEXT NOT NULL, module TEXT NOT NULL,
            version TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY(learner, topic, module))''')

    @staticmethod
    def _groups(module):
        practices = module.get('practices', [])
        metadata = ['source_practice' in question for question in practices]
        if any(metadata):
            if len(practices) != 15 or not all(metadata):
                raise _error('invalid_course', '分组练习必须完整包含 5 组，每组 3 题。', 422)
            groups = {group: {} for group in range(1, 6)}
            for question in practices:
                source = question['source_practice']
                if (not isinstance(source, dict)
                        or type(source.get('group')) is not int
                        or type(source.get('member')) is not int
                        or source['group'] not in groups
                        or source['member'] not in (1, 2, 3)
                        or source['member'] in groups[source['group']]):
                    raise _error('invalid_course', '练习分组标记缺失、重复或不合法。', 422)
                groups[source['group']][source['member']] = question['id']
            if any(len(members) != 3 for members in groups.values()):
                raise _error('invalid_course', '每组练习必须包含 3 个不同成员。', 422)
            return [[groups[group][member] for member in (1, 2, 3)]
                    for group in range(1, 6)]
        if len(practices) != 15:
            return None
        return [[question['id'] for question in practices[start:start + 3]]
                for start in range(0, 15, 3)]

    @staticmethod
    def supported(module):
        return PersistentPracticeQueue._groups(module) is not None

    def lesson_seeds(self, module):
        return [group[0] for group in self._groups(module)[:3]]

    def _key(self, module):
        return (*self.learning.key, module['id'])

    def snapshot(self, con, module):
        """Read private state without creating a queue or advancing exposure."""
        row = con.execute('SELECT version,body FROM practice_queues '
                          'WHERE learner=? AND topic=? AND module=?', self._key(module)).fetchone()
        if row is None:
            return None
        if row['version'] != self.learning.course['version']:
            raise _error('course_version_mismatch', '练习队列的课程版本已变化，原队列已保留。')
        state = json.loads(row['body'])
        if state.get('queue_version') != VERSION:
            raise _error('practice_queue_version_mismatch', '练习队列规则版本已变化，原队列已保留。')
        return state

    def _save(self, con, module, state):
        con.execute('''INSERT INTO practice_queues VALUES (?,?,?,?,?)
            ON CONFLICT(learner,topic,module) DO UPDATE SET body=excluded.body''',
            (*self._key(module), self.learning.course['version'],
             json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':'))))

    @staticmethod
    def _new_state(pending):
        return {'queue_version': VERSION, 'pending': list(pending),
                'expanded_groups': [], 'sequence': 0, 'presented': [], 'last_presented': {}}

    @staticmethod
    def _present(state, question_id):
        state['sequence'] += 1
        state['presented'].append(question_id)
        state['last_presented'][question_id] = state['sequence']

    def _fallback(self, state, eligible):
        last_seen = state['last_presented']
        unseen = [item for item in eligible if item not in last_seen]
        return self.rng.choice(unseen) if unseen else min(eligible, key=last_seen.__getitem__)

    @staticmethod
    def _question_ids(module, groups, has_example):
        ids = ([item for group in groups for item in group] if groups else
               [question['id'] for question in module['practices']])
        if has_example:
            ids.append(module['example']['id'])
        return ids

    def has_example(self, con, module):
        state = self.snapshot(con, module)
        return state is not None and module['example']['id'] in state['last_presented']

    def enqueue_example(self, con, module):
        """Record a judged guided example and queue it for a later round."""
        state = self.snapshot(con, module)
        if state is None:
            state = self._new_state(self.lesson_seeds(module) if self.supported(module) else [])
        question_id = module['example']['id']
        self._present(state, question_id)
        if question_id not in state['pending']:
            state['pending'].append(question_id)
        self._save(con, module, state)

    def draw(self, con, module, exclude=(), *, initial=None, selected=None):
        """Take the next eligible question and persist its actual exposure."""
        groups = self._groups(module)
        state = self.snapshot(con, module)
        example_id = module.get('example', {}).get('id')
        has_example = state is not None and example_id in state['last_presented']
        if groups is None and not has_example:
            raise _error('unsupported_practice_queue', '此旧题库继续使用原有练习顺序。')
        all_ids = self._question_ids(module, groups, has_example)
        excluded = set(exclude)
        if selected is not None and (selected not in all_ids or selected in excluded):
            raise _error('invalid_practice_question', '本轮指定的练习不合法或已经推送。', 422)
        if not any(question not in excluded for question in all_ids):
            raise _error('practice_queue_exhausted', '本轮已使用全部练习，不能重复推送。')
        if state is None:
            state = self._new_state(initial if initial is not None else [self.rng.choice(group) for group in groups])
        pending = state['pending']
        question = selected or next((item for item in pending if item not in excluded), None)
        if question is not None:
            if question in pending:
                pending.remove(question)
        else:
            eligible = [item for item in all_ids if item not in excluded and item not in pending]
            question = self._fallback(state, eligible)
        self._present(state, question)
        self._save(con, module, state)
        return question

    def record_result(self, con, module, question_id, correct, *, additions=None, exclude=()):
        """Append by the round's policy, preferring siblings on a group's first miss."""
        if type(correct) is not bool:
            raise ValueError('Only a successful boolean judgement may update practice queues')
        state = self.snapshot(con, module)
        example_id = module.get('example', {}).get('id')
        has_example = state is not None and example_id in state['last_presented']
        groups = self._groups(module)
        if groups is None and not has_example:
            raise _error('unsupported_practice_queue', '此旧题库继续使用原有练习顺序。')
        group_index = next((index for index, group in enumerate(groups or (), 1)
                            if question_id in group), None)
        if group_index is None and not (has_example and (
                question_id == example_id or groups is None
                and any(question['id'] == question_id for question in module['practices']))):
            raise _error('invalid_practice_question', '题目不属于当前 Example。', 422)
        if state is None or question_id not in state['last_presented']:
            raise _error('practice_not_presented', '题目尚未推送，不能记录答题结果。')
        first_group_miss = group_index is not None and group_index not in state['expanded_groups']
        if correct or (additions is None and not first_group_miss):
            return 0
        pending = state['pending']
        previous_size = len(pending)
        unavailable = {*exclude, question_id, *pending}
        siblings = []
        if first_group_miss:
            state['expanded_groups'].append(group_index)
            siblings = [item for item in groups[group_index - 1] if item not in unavailable]
        if additions is None:
            pending.extend(siblings)
        else:
            chosen = siblings[:additions]
            eligible = [item for item in self._question_ids(module, groups, has_example)
                        if item not in unavailable and item not in chosen]
            while eligible and len(chosen) < additions:
                item = self._fallback(state, eligible)
                chosen.append(item)
                eligible.remove(item)
            pending.extend(chosen)
        self._save(con, module, state)
        return len(pending) - previous_size
