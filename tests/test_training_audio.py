import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import struct
import unittest
import wave
from contextlib import closing

from graspmemoedu.context_library_api import register_context_library_routes
from graspmemoedu.service import DomainError
from graspmemoedu.training_audio import (FunASRTranscriber, _sentences, decode_recording, public_audio, read_audio,
                                        validate_audio, audio_backup_blobs, validate_audio_archive)
from tests.fixtures import temporary_test_directory
from tests import test_context_library
from tests import test_site_backup


def wav_bytes(seconds=.1, rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(b'\0\0' * int(seconds * rate))
    return stream.getvalue()


def audio_fixture(data=None):
    data = wav_bytes() if data is None else data
    return {'id': 'speech', 'audio': {'version': 1, 'asset': 'audio/' + hashlib.sha256(data).hexdigest() + '.wav',
            'mime_type': 'audio/wav', 'mode': 'read_aloud', 'transcript': 'PRIVATE_REFERENCE'}}, data


class TrainingAudioTests(unittest.TestCase):
    def test_projection_never_returns_asset_or_transcript_before_feedback(self):
        question, _ = audio_fixture()
        public = public_audio(question, 'topic')
        self.assertNotIn('asset', public); self.assertNotIn('PRIVATE_REFERENCE', json.dumps(public))
        self.assertEqual(public_audio(question, 'topic', feedback=True)['transcript'], 'PRIVATE_REFERENCE')

    def test_path_mime_and_hash_are_checked(self):
        question, data = audio_fixture()
        with temporary_test_directory() as folder:
            root = Path(folder); (root / 'audio').mkdir(); path = root / question['audio']['asset']; path.write_bytes(data)
            self.assertEqual(base64.b64decode(read_audio(root / 'topic.json', question)['data_base64']), data)
            path.write_bytes(data + b'altered')
            with self.assertRaises(DomainError): read_audio(root / 'topic.json', question)
        for value in ('../secret.wav', '/secret.wav', 'https://example.com/file.wav', 'audio/not-a-hash.wav'):
            invalid = deepcopy(question); invalid['audio']['asset'] = value
            with self.assertRaises(ValueError): validate_audio(invalid)
        question['audio']['mime_type'] = 'audio/mpeg'
        with self.assertRaises(ValueError): validate_audio(question)

    def test_recording_duration_and_container_are_measured_not_trusted(self):
        valid = wav_bytes(); self.assertEqual(decode_recording(base64.b64encode(valid).decode()), valid)
        for value in [b'webm pretending to be wav', valid[:-2], valid + b'extra', wav_bytes(121), wav_bytes(rate=48000)]:
            with self.subTest(size=len(value)), self.assertRaises(DomainError):
                decode_recording(base64.b64encode(value).decode())
        for value in ('!!!!', '', 'data:audio/wav;base64,AAAA'):
            with self.assertRaises(DomainError): decode_recording(value)

    def test_sse_uses_final_sentences_and_rejects_truncated_or_partial_results(self):
        partial = {'output': {'sentence': {'sentence_id': 1, 'text': 'I can', 'sentence_end': False}}}
        final = {'output': {'sentence': {'sentence_id': 1, 'text': 'I can read.', 'sentence_end': True, 'begin_time': 0, 'end_time': 900}}}
        encoded = lambda obj: ('data: ' + json.dumps(obj) + '\n\n').encode()
        result = _sentences(io.BytesIO(encoded(partial) + encoded(final)))
        self.assertEqual(result['text'], 'I can read.')
        for value in [encoded(partial), encoded(final).rstrip(), encoded({'code': 'ERROR', 'message': 'PRIVATE_ERROR'})]:
            with self.assertRaises(ValueError): _sentences(io.BytesIO(value))

    def test_missing_configuration_and_upstream_failure_are_safe(self):
        with self.assertRaises(DomainError) as missing: FunASRTranscriber(key='')(wav_bytes())
        self.assertEqual(missing.exception.code, 'transcription_unavailable')
        def fail(*args, **kwargs): raise OSError('private endpoint credential text')
        with self.assertRaises(DomainError) as failure: FunASRTranscriber(key='secret', opener=fail)(wav_bytes())
        self.assertNotIn('private', str(failure.exception)); self.assertNotIn('secret', str(failure.exception))

    def test_archive_checks_referenced_audio_bytes_and_relative_restore(self):
        from types import SimpleNamespace
        question, data = audio_fixture()
        with temporary_test_directory() as folder:
            root = Path(folder); (root / 'source/audio').mkdir(parents=True)
            topic = {'id': 't', 'flashcards': [question]}
            (root / 'source' / question['audio']['asset']).write_bytes(data)
            catalog = SimpleNamespace(topics={'t': topic}, topic_paths={'t': root / 'source/topic.json'})
            blobs = audio_backup_blobs(catalog)
            expected = 'courses/' + question['audio']['asset']
            self.assertEqual(validate_audio_archive(blobs, [topic]), {expected})
            restored = root / 'restore' / expected; restored.parent.mkdir(parents=True); restored.write_bytes(blobs[expected])
            self.assertEqual(base64.b64decode(read_audio(root / 'restore/courses/t.json', question)['data_base64']), data)
            with self.assertRaises(ValueError): validate_audio_archive({}, [topic])
            with self.assertRaises(DomainError): validate_audio_archive({expected: data + b'changed'}, [topic])


class TrainingAudioApiTests(unittest.TestCase):
    account = test_context_library.ContextLibraryApiTests.account

    def setUp(self):
        class Transcriber:
            configured = True
            calls = []
            def __call__(self, data):
                self.calls.append(data)
                return {'text': 'An editable transcript.', 'provider': 'fixture', 'segments': []}
        self.transcriber = Transcriber()
        test_context_library.ContextLibraryApiTests.setUp(self)
        question, self.audio_data = audio_fixture()
        self.topic['flashcards'][0]['audio'] = question['audio']
        (self.root / 'audio').mkdir()
        (self.root / question['audio']['asset']).write_bytes(self.audio_data)
        self.audio_query = '?topic_id=' + self.topic['id'] + '&question_id=' + self.topic['flashcards'][0]['id']
        self.body = {'content_version': self.topic['version'], 'mime_type': 'audio/wav',
                     'data_base64': base64.b64encode(self.audio_data).decode()}

    def test_audio_uses_real_topic_permissions_and_omits_private_transcript(self):
        response = self.client.get('/api/training-audio' + self.audio_query, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(base64.b64decode(response.json()['data_base64']), self.audio_data)
        self.assertNotIn('PRIVATE_REFERENCE', response.text)
        _, denied = self.account(is_admin=True)
        self.assertEqual(self.client.get('/api/training-audio' + self.audio_query, headers=denied).status_code, 403)

    def test_transcription_uses_submit_permission_quota_and_does_not_grade(self):
        self.assertTrue(self.client.get('/api/training-audio/status' + self.audio_query, headers=self.headers).json()['transcription_available'])
        response = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['text'], 'An editable transcript.'); self.assertNotIn('score', response.json())
        with closing(self.access._connect()) as con:
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('topics', tables); self.assertNotIn('events', tables)
        self.access.set_permissions(self.learner, features=['learn'])
        denied = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json=self.body)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(len(self.transcriber.calls), 1)

    def test_voice_commands_pass_asr_text_to_the_shared_interpreter_without_refining(self):
        from unittest.mock import patch
        body = {'mime_type': self.body['mime_type'], 'data_base64': self.body['data_base64'], 'profile': 'answer_commands'}
        with patch('graspmemoedu.voice_input.independent_settings', side_effect=AssertionError('extra generation')):
            result = self.client.post('/api/voice-input/transcribe', headers=self.headers, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json(), {'text': 'An editable transcript.'})
        self.assertEqual(self.transcriber.calls, [self.audio_data])

    def test_bad_wav_stale_version_and_unconfigured_provider_never_send_audio(self):
        for patch in ({'data_base64': 'AAAA'}, {'content_version': 'old'}, {'mime_type': 'audio/webm'}):
            response = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json={**self.body, **patch})
            self.assertIn(response.status_code, (409, 422))
        self.transcriber.configured = False
        response = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json=self.body)
        self.assertEqual(response.status_code, 503); self.assertEqual(self.transcriber.calls, [])

    def test_rate_limit_and_guest_cost_boundary(self):
        self.app.state.public_limits.submissions_per_minute = 1
        first = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json=self.body)
        second = self.client.post('/api/training-audio/transcribe' + self.audio_query, headers=self.headers, json=self.body)
        self.assertEqual(first.status_code, 200); self.assertEqual(second.status_code, 429)
        self.access.test_materials.permission_ids.clear(); self.access.test_materials.topics.clear()
        guest = self.access.create_guest()
        response = self.client.post('/api/training-audio/transcribe' + self.audio_query,
                                    headers={'X-Learning-Identity': guest['identity_token']}, json=self.body)
        self.assertEqual(response.status_code, 403)

    def test_general_voice_reuses_account_boundary_and_asr_without_grading(self):
        from unittest.mock import patch
        path = '/api/voice-input/transcribe'
        body = {'mime_type': self.body['mime_type'], 'data_base64': self.body['data_base64'], 'profile': 'answer'}
        with patch('graspmemoedu.voice_input.independent_settings', side_effect=ValueError):
            result = self.client.post(path, headers=self.headers, json=body)
        self.assertEqual(result.status_code, 502, result.text)
        self.assertEqual(self.transcriber.calls, [self.audio_data])
        guest = self.access.create_guest()
        result = self.client.post(path, headers={'X-Learning-Identity': guest['identity_token']}, json=body)
        self.assertEqual(result.status_code, 403)
        self.assertEqual(len(self.transcriber.calls), 1)

    def test_refinement_profiles_route_only_general_and_reject_calculator_prose(self):
        from unittest.mock import Mock
        from graspmemoedu.voice_input import refine_voice
        general = Mock(side_effect=['writing', '正文'])
        self.assertEqual(refine_voice('原文', 'general', general), '正文')
        self.assertEqual(general.call_count, 2)
        answer = Mock(return_value='解为 x=2')
        self.assertEqual(refine_voice('解为 x=2', 'answer', answer), '解为 x=2')
        self.assertEqual(answer.call_count, 1)
        self.assertEqual(refine_voice('二加三', 'calculator', Mock(return_value='2+3')), '2+3')
        for value in ('答案是2+3', '2+3\t', '2+3\n', 'result=5', '`2+3`'):
            with self.subTest(value=value), self.assertRaises(DomainError):
                refine_voice('二加三', 'calculator', Mock(return_value=value))


class TrainingAudioBackupTests(unittest.TestCase):
    setUp = test_site_backup.SiteBackupAcceptanceTests.setUp
    _complete = test_site_backup.SiteBackupAcceptanceTests._complete
    _payload = test_site_backup.SiteBackupAcceptanceTests._payload
    _backup = test_site_backup.SiteBackupAcceptanceTests._backup

    def test_site_backup_restores_audio_and_private_context_records(self):
        from graspmemoedu.catalog import Catalog
        from graspmemoedu.config import Settings
        from graspmemoedu.context_library import ContextLibraryStore
        from graspmemoedu.site_backup import restore_site
        question, data = audio_fixture()
        topic = self.topics['portable-a']
        topic['modules'][0]['example']['audio'] = question['audio']
        topic['reading_materials'] = [{'id': 'reading', 'title': 'Reading',
                                     'paragraphs': [{'id': 'p', 'text': 'A context.'}], 'annotations': []}]
        self.paths[topic['id']].write_text(json.dumps(topic), encoding='utf-8')
        path = self.external / question['audio']['asset']; path.parent.mkdir(); path.write_bytes(data)
        ledger = ContextLibraryStore(self.access._connect)
        ledger.save(self.guest['access'], topic, topic['reading_materials'][0], {'action': 'memory',
                    'content_version': topic['version'], 'paragraph_id': 'p',
                    'quote': {'exact': 'context', 'prefix': 'A ', 'suffix': '.', 'start': 2, 'end': 9}})
        destination = self.root / 'audio-restored'
        restore_site(self._backup(), destination)
        catalog = Catalog.load(Settings.load(destination))
        restored_topic = catalog.topic(topic['id'])
        restored_question = restored_topic['modules'][0]['example']
        self.assertEqual(base64.b64decode(read_audio(catalog.topic_paths[topic['id']], restored_question)['data_base64']), data)
        from graspmemoedu.access import AccessStore
        access = AccessStore(destination, [{'id': t['id'], 'title': t['title']} for t in catalog.topics.values()])
        records = ContextLibraryStore(access._connect).records(self.guest['access']['learner_id'], restored_topic,
                                                               restored_topic['reading_materials'][0])
        self.assertEqual(records[0]['context'], 'A context.'); self.assertEqual(records[0]['memory_status'], 'candidate')


if __name__ == '__main__': unittest.main()
