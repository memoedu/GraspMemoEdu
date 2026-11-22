"""Lesson integration boundaries for persistent grouped Practice queues."""

from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import random
import unittest
import uuid

from graspmemoedu.service import DomainError, LearningService
from graspmemoedu.review import ReviewBackend
from graspmemoedu.fsrs_engine import utc_time
from tests.fixtures import DeterministicJudge, synthetic_course, temporary_test_directory


class GroupedLessonTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_test_directory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.course = synthetic_course()
        self.restart()
        self.service.practice_queue.rng = random.Random(618)

    def restart(self, learner='local'):
        self.service = LearningService(self.course, self.path, DeterministicJudge(), learner_id=learner)

    def payload(self, **extra):
        state = self.service.state()
        return {'request_id': str(uuid.uuid4()), 'expected_revision': state['revision'],
                'attempt_id': state['attempt_id'], 'step_id': state['active_step_id'], **extra}

    def active(self, state=None):
        state = state or self.service.state()
        return next(step for step in state['steps'] if step['id'] == state['active_step_id'])

    def queue(self):
        with closing(self.service._connect()) as con:
            return self.service.practice_queue.snapshot(con, self.course['modules'][0])

    def advance(self):
        return self.service.advance(self.payload())

    def study(self):
        state = self.service.choose(self.payload(choice='unmastered'))
        while self.active(state)['kind'] != 'practice':
            if self.active(state)['phase'] == 'guided_choice':
                state = self.service.choose(self.payload(choice='view_solution'))
            else:
                state = self.advance()
        return state

    def answer(self, correct):
        item = self.service.submit(self.payload(answer='correct' if correct else 'wrong'))
        self.service.process_submission(item['submission_id'])
        return self.service.submission(item['submission_id'])['state']

    def test_guided_example_counts_once_and_returns_in_a_due_review(self):
        grouped_course = self.course
        for grouped, correct in ((True, True), (True, False), (False, True), (False, False)):
            with self.subTest(grouped=grouped, correct=correct):
                self.course = deepcopy(grouped_course)
                module = self.course['modules'][0]
                if not grouped:
                    module['practices'] = module['practices'][:7]
                learner = f'guided-{grouped}-{correct}'
                self.restart(learner)
                example_id = module['example']['id']
                guidance = self.service.choose(self.payload(choice='unmastered'))
                self.assertEqual(self.active(guidance)['kind'], 'introduction')
                choice = self.advance()
                self.assertEqual(self.active(choice)['actions'], ['attempt_example', 'view_solution'])
                self.assertIsNone(self.active(choice)['explanation_html'])
                with self.assertRaises(DomainError):
                    self.advance()
                request = self.payload(choice='attempt_example')
                answer = self.service.choose(request)
                self.assertEqual(self.service.choose(request), answer)
                self.assertEqual(self.active(answer)['actions'], ['submit'])
                self.assertIsNone(self.queue())
                state = self.answer(correct)
                summary = state['modules'][0]
                self.assertEqual(summary['practice_answered_count'], 1)
                self.assertEqual(summary['practice_error_count'], int(not correct))
                self.assertEqual(summary['practice_target_count'], (3 if grouped else 2) + int(not correct))
                self.assertEqual(summary['status'], 'in_progress')
                self.assertIsNotNone(self.active(state)['explanation_html'])
                self.assertEqual(self.queue()['pending'].count(example_id), 1)

                self.restart(learner)
                when = datetime.now(timezone.utc)
                review = ReviewBackend(self.service, clock=lambda: when)
                shown = [example_id]
                for _ in range(summary['practice_target_count'] - 1):
                    shown.append(self.active(self.advance())['question_id'])
                    state = self.answer(True)
                self.assertEqual(len(shown), len(set(shown)))
                self.assertEqual(state['modules'][0]['mastery'], 4 if correct else 3)
                pending = self.queue()['pending']
                for expected in pending[:pending.index(example_id) + 1]:
                    when = utc_time(review.next_due_at()) + timedelta(seconds=1)
                    current = review.begin(module['id'], request_id=str(uuid.uuid4()))
                    question_id = current['practice']['id']
                    self.assertEqual(question_id, expected)
                    payload = {'request_id': str(uuid.uuid4()), 'expected_revision': current['revision'],
                               'question_id': question_id, 'answer': 'correct'}
                    reserved = review.submit(current['session_id'], payload)
                    review.process_submission(reserved['submission_id'])
                    self.assertEqual(review.submission(reserved['submission_id'])['state']['mastery'], 4)

    def test_direct_example_reaches_review_and_wrong_answer_uses_the_first_miss_rule(self):
        self.course['modules'][0]['practices'] = self.course['modules'][0]['practices'][:7]
        self.restart('sequential-review')
        when = datetime.now(timezone.utc)
        review = ReviewBackend(self.service, clock=lambda: when)
        self.service.choose(self.payload(choice='mastered'))
        state = self.answer(True)
        self.assertEqual(state['modules'][0]['mastery'], 4)
        when = utc_time(review.next_due_at()) + timedelta(seconds=1)
        current = review.begin('module-1', request_id=str(uuid.uuid4()))
        example_id = self.course['modules'][0]['example']['id']
        self.assertEqual(current['practice']['id'], example_id)
        payload = {'request_id': str(uuid.uuid4()), 'expected_revision': current['revision'],
                   'question_id': example_id, 'answer': 'wrong'}
        reserved = review.submit(current['session_id'], payload)
        review.process_submission(reserved['submission_id'])
        state = review.submission(reserved['submission_id'])['state']
        self.assertEqual(state['practice_target_count'], 2)
        self.assertEqual(len(self.queue()['pending']), 1)
        state = review.advance(current['session_id'], {**payload, 'request_id': str(uuid.uuid4()),
                                                       'expected_revision': state['revision']})
        self.assertTrue(state['practice']['id'].startswith('module-1-practice-'))

    def test_wrong_direct_example_in_sequential_lesson_does_not_skip_the_first_practice(self):
        self.course['modules'][0]['practices'] = self.course['modules'][0]['practices'][:7]
        self.restart('sequential-lesson')
        self.service.choose(self.payload(choice='mastered'))
        state = self.answer(False)
        self.assertEqual(state['modules'][0]['practice_target_count'], 3)
        self.assertEqual(self.active(self.advance())['kind'], 'introduction')
        self.assertEqual(self.active(self.advance())['phase'], 'reading')
        self.assertEqual(self.active(self.advance())['question_id'], 'module-1-practice-1')
        self.answer(False)
        self.assertEqual(self.service.state()['modules'][0]['practice_target_count'], 5)

    def test_legacy_attempt_keeps_sequential_questions_and_never_creates_queue(self):
        with self.service._transaction() as con:
            state = self.service._load(con)
            self.service._attempt(state).pop('practice_queue_version')
            self.service._attempt(state).pop('practice_policy')
            self.service._attempt(state)['practice_target_count'] = 2
            self.service._save(con, state)
        self.restart()
        state = self.study()
        self.assertEqual(self.active(state)['question_id'], 'module-1-practice-1')
        self.answer(False)
        self.restart()
        state = self.advance()
        self.assertEqual(self.active(state)['question_id'], 'module-1-practice-2')
        self.assertIsNone(self.queue())

    def test_started_grouped_round_retains_previous_first_miss_policy(self):
        self.study()
        with self.service._transaction() as con:
            state = self.service._load(con)
            self.service._attempt(state)['practice_policy'] = {
                'version': 'lesson-v2', 'targets': [3, 5, 7, 9], 'ratings': [4, 3, 2, 1]}
            self.service._save(con, state)
        self.restart()
        state = self.answer(False)
        self.assertEqual(state['modules'][0]['practice_target_count'], 5)
        self.assertEqual(self.queue()['pending'][-2:], ['module-1-practice-2', 'module-1-practice-3'])
        self.assertEqual(self.active(self.advance())['question_id'], 'module-1-practice-4')

    def test_refresh_and_replayed_advance_do_not_consume_extra_questions(self):
        self.study()
        before = self.queue()
        self.assertEqual(before['sequence'], 1)
        self.service.state()
        self.restart()
        self.assertEqual(self.queue(), before)
        self.answer(True)
        payload = self.payload()
        state = self.service.advance(payload)
        after = self.queue()
        self.assertEqual(after['sequence'], 2)
        self.assertEqual(self.service.advance(payload), state)
        self.service.state()
        self.assertEqual(self.queue(), after)

    def test_new_lesson_starts_with_exact_three_seeds_and_three_correct_settle(self):
        self.study()
        self.assertEqual(self.queue()['pending'], ['module-1-practice-4', 'module-1-practice-7'])
        delivered = []
        for index in range(3):
            if index:
                self.restart(); self.advance()
            delivered.append(self.active()['question_id'])
            state = self.answer(True)
            self.assertEqual(state['modules'][0]['practice_target_count'], 3)
            self.assertEqual(state['modules'][0]['mastery'], 4 if index == 2 else None)
        self.assertEqual(delivered, ['module-1-practice-1', 'module-1-practice-4', 'module-1-practice-7'])
        self.assertEqual(self.queue()['pending'], [])

    def test_fourth_error_does_not_append_more_questions_or_score(self):
        self.study()
        for index in range(3):
            if index:
                self.advance()
            self.answer(False)
        before = self.queue()
        self.assertEqual(len(before['pending']), 5)
        self.advance()
        before_verdict = self.queue()
        state = self.answer(False)
        self.assertEqual(self.queue(), before_verdict)
        self.assertEqual(state['modules'][0]['practice_target_count'], 8)
        self.assertIsNone(state['modules'][0]['mastery'])
        self.assertEqual(state['status'], 'paused')

    def test_existing_policyless_round_keeps_old_targets_and_random_queue(self):
        with self.service._transaction() as con:
            state = self.service._load(con)
            attempt = self.service._attempt(state)
            attempt.pop('practice_policy')
            attempt['practice_target_count'] = 2
            self.service._save(con, state)
        self.restart(); self.study()
        self.assertEqual(len(self.queue()['pending']), 4)
        self.answer(True); self.advance()
        state = self.answer(True)
        self.assertEqual(state['modules'][0]['practice_target_count'], 2)
        self.assertEqual(state['modules'][0]['mastery'], 4)

    def test_same_group_errors_still_grow_target_by_two_and_never_repeat(self):
        self.study()
        answers = [False, True, True, False, False, True, True, True]
        delivered = []
        for index, correct in enumerate(answers):
            if index:
                self.advance()
            delivered.append(self.active()['question_id'])
            state = self.answer(correct)
            errors = answers[:index + 1].count(False)
            self.assertEqual(state['modules'][0]['practice_target_count'], (3, 4, 6, 8)[errors])
        self.assertEqual(delivered[3], 'module-1-practice-2')
        self.assertEqual(len(delivered), len(set(delivered)))
        self.assertEqual(state['modules'][0]['mastery'], 1)

    def test_completed_lesson_records_the_actual_policy_version_in_fsrs(self):
        ReviewBackend(self.service)
        self.study()
        for index in range(3):
            if index:
                self.advance()
            self.answer(True)
        with closing(self.service._connect()) as con:
            row = con.execute("SELECT mastery,policy_version FROM review_ratings WHERE source='lesson'").fetchone()
        self.assertEqual(tuple(row), (4, 'lesson-v3'))

    def test_non_grouped_seven_question_bank_keeps_its_valid_two_question_target(self):
        from copy import deepcopy
        course = deepcopy(self.course)
        course['modules'][0]['practices'] = course['modules'][0]['practices'][:7]
        self.service = LearningService(course, self.path / 'seven', DeterministicJudge())
        self.study(); self.answer(True); self.advance()
        state = self.answer(True)
        self.assertEqual(state['modules'][0]['practice_target_count'], 2)
        self.assertEqual(state['modules'][0]['mastery'], 4)

    def test_group_expansion_preserves_lesson_targets_scores_and_fourth_error_pause(self):
        cases = [([True, True, True], 4), ([False, True, True, True], 3),
                 ([False, False, True, True, True, True], 2),
                 ([False, False, False, True, True, True, True, True], 1),
                 ([False, False, False, False], None)]
        for case_index, (answers, mastery) in enumerate(cases):
            with self.subTest(mastery=mastery):
                self.restart(learner=f'case-{case_index}')
                self.study()
                for index, correct in enumerate(answers):
                    if index:
                        self.advance()
                    state = self.answer(correct)
                    errors = answers[:index + 1].count(False)
                    module = state['modules'][0]
                    self.assertEqual(module['practice_answered_count'], index + 1)
                    self.assertEqual(module['practice_target_count'], (3, 4, 6, 8)[min(errors, 3)])
                    self.assertEqual(len(self.queue()['pending']), max(0, (3, 4, 6, 8)[min(errors, 3)] - index - 1))
                    self.assertEqual(len(self.queue()['expanded_groups']), min(errors, 3))
                self.assertEqual(module['mastery'], mastery)
                self.assertEqual(module['status'], 'paused' if mastery is None else 'completed')
                self.assertEqual(self.queue()['sequence'], len(answers))

    def test_reset_during_judgement_cannot_recreate_deleted_queue(self):
        self.study()
        item = self.service.submit(self.payload(answer='wrong'))
        self.assertIsNotNone(self.queue())

        def reset_while_judging(*_args):
            self.service.reset_progress(self.payload())
            return {'status': 'judged', 'correct': False, 'reason': 'late result'}

        self.service.judge = reset_while_judging
        self.service.process_submission(item['submission_id'])
        self.assertIsNone(self.queue())
        self.assertEqual(self.service.submission(item['submission_id'])['status'], 'discarded')
        self.assertEqual(self.service.state()['modules'][0]['practice_error_count'], 0)

    def test_unlock_new_attempt_continues_remaining_queue_and_group_flags(self):
        self.study()
        for index in range(4):
            if index:
                self.advance()
            state = self.answer(False)
        before = self.queue()
        old_attempt = state['attempt_id']
        state = self.service.unlock(self.course['id'], 'module-1', state['pause']['event_id'])
        self.assertNotEqual(state['attempt_id'], old_attempt)
        self.restart()
        self.assertEqual(self.queue(), before)
        state = self.study()
        self.assertEqual(self.active(state)['question_id'], 'module-1-practice-1')
        self.assertEqual(self.queue()['expanded_groups'], before['expanded_groups'])
        self.assertEqual(self.queue()['sequence'], before['sequence'] + 1)


if __name__ == '__main__':
    unittest.main()
