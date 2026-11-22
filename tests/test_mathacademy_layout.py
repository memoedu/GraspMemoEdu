import unittest

from graspmemoedu.catalog import Catalog
from graspmemoedu.lesson_display import LessonDisplay, display_key
from graspmemoedu.mathacademy_layout import ML1_COURSE, source_ordered_topic
from graspmemoedu.materials import topic_blocks
from graspmemoedu.service import create_learning_service
from graspmemoedu.source_content import reading_blocks
from tests.fixtures import DeterministicJudge, temporary_test_directory
from tests.test_ordered_learning import active, ordered_topic, payload


def source_topic():
    topic = ordered_topic()
    topic.update(id='ma-topic-1', source_adapter='mathacademy')
    topic['introductions'][1]['html'] = ('<p>Earlier example recap</p>\n'
        '<h1 id="method">Method <svg><path d="M0 0"/></svg></h1><p>Details</p>'
        '<h2>Conditions</h2><p>When it applies</p>'
        '<h1 id="alternate">Another method</h1><ul><li>Steps</li></ul>')
    return topic


class MathAcademyLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_test_directory()
        self.addCleanup(self.temp.cleanup)

    def test_catalog_projections_preserve_source_and_translation_bindings(self):
        original = source_topic()
        original['introductions'].append({'id': 'intro-last', 'title': 'Final', 'html': '<p>Final recap</p>'})
        original['content_order'].append({'id': 'intro-last', 'kind': 'introduction'})
        tid = original['id']
        catalogs = [Catalog([{'id': cid, 'topics': [{'id': tid}]}], {tid: original}, tid, {})
                    for cid in (ML1_COURSE, 'ma-course-140')]
        scoped, other = catalogs
        topic = scoped.topic(tid)
        self.assertIs(scoped.topics[tid], original)
        self.assertIs(other.topic(tid), original)
        self.assertEqual(topic['version'], original['version'])
        self.assertIs(topic['modules'], original['modules'])
        body = original['introductions'][1]['html']
        localized = body.replace('Earlier example recap', '前例补充').replace('Another method', '另一方法')
        display = LessonDisplay(self.temp.name, topic)
        display.values = {display_key('html', body): localized}
        reader = reading_blocks(topic, display)
        fragments = [b for b in reader if b['id'].startswith('intro-b')]
        self.assertEqual([b['id'] for b in fragments], ['intro-b', 'intro-b--body-2', 'intro-b--body-3'])
        self.assertEqual(''.join(b['html'] for b in fragments), localized)
        self.assertTrue(fragments[1]['html'].startswith('<h1 id="method"'))
        self.assertIn('<h2>Conditions</h2>', fragments[1]['html'])
        self.assertTrue(fragments[2]['html'].startswith('<h1 id="alternate">另一方法'))
        self.assertEqual(reader[reader.index(fragments[0]) - 1]['id'], original['modules'][0]['practices'][-1]['id'])
        self.assertEqual(reader[reader.index(fragments[-1]) + 1]['id'], original['modules'][1]['example']['id'])
        materials = {b['id']: b for b in topic_blocks(topic, display=display)}
        for block in fragments:
            self.assertEqual(materials['introduction:' + block['id']]['html'], block['html'])

    def test_split_recap_follows_practice_and_only_nearest_block_is_guidance(self):
        topic = source_ordered_topic(source_topic())
        service = create_learning_service(topic, self.temp.name, DeterministicJudge())
        self.assertEqual(active(service.state())['phase'], 'choice')
        state = service.choose(payload(service, choice='unmastered'))
        self.assertEqual(active(state)['introduction_ids'], ['intro-a'])
        state = service.advance(payload(service))
        self.assertEqual(active(state)['phase'], 'guided_choice')
        service.choose(payload(service, choice='view_solution'))
        service.advance(payload(service))
        for _ in range(3):
            submitted = service.submit(payload(service, answer='correct'))
            service.process_submission(submitted['submission_id'])
            service.advance(payload(service))
        for ident in ('intro-b', 'intro-b--body-2'):
            self.assertEqual(active(service.state())['introduction_id'], ident)
            service = create_learning_service(topic, self.temp.name, DeterministicJudge())
            service.advance(payload(service))
        self.assertEqual(active(service.state())['question_id'], 'module-2-example')
        self.assertEqual(active(service.choose(payload(service, choice='unmastered')))['introduction_ids'],
                         ['intro-b--body-3'])

    def test_existing_guidance_step_can_continue_and_skipped_examples_stay_skipped(self):
        raw = source_topic()
        raw['introductions'].append({'id': 'intro-last', 'title': 'Final', 'html': '<p>Final recap</p>'})
        raw['content_order'].append({'id': 'intro-last', 'kind': 'introduction'})
        service = create_learning_service(raw, self.temp.name, DeterministicJudge())
        old = active(service.choose(payload(service, choice='unmastered')))
        service = create_learning_service(source_ordered_topic(raw), self.temp.name, DeterministicJudge())
        self.assertEqual(active(service.state())['id'], old['id'])
        self.assertEqual(active(service.advance(payload(service)))['phase'], 'guided_choice')
        state = service.skip_module(payload(service))
        first = state['skipped_modules'][0]
        for _ in range(2):
            state = service.advance(payload(service))
        self.assertEqual(active(state)['question_id'], 'module-2-example')
        state = service.skip_module(payload(service))
        self.assertEqual(state['status'], 'in_progress')
        self.assertEqual(active(state)['introduction_id'], 'intro-last')
        state = service.advance(payload(service))
        self.assertEqual(state['status'], 'completed')
        reopened = service.unlock(service.topic_id, first['module_id'], first['event_id'])
        self.assertEqual(active(reopened)['question_id'], 'module-1-example')
