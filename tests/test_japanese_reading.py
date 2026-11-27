import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from importlib.util import find_spec
from pathlib import Path

from fastapi.testclient import TestClient

from graspmemoedu.japanese_reading.analysis import POLITE_POINT_ID, POLITE_TOPIC_ID
from graspmemoedu.japanese_reading.app import create_app


@unittest.skipUnless(find_spec("fugashi") and find_spec("unidic_lite"), "install requirements-japanese-reading.txt")
class JapaneseReadingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.topic_file = root / "fixture-topic.json"
        self.progress_db = root / "fixture-progress.sqlite3"
        topic = {"id": POLITE_TOPIC_ID, "version": "fixture-2",
                 "introductions": [{"id": "fixture-introduction"}],
                 "memory_chunks": [{"points": [{"id": POLITE_POINT_ID}]}]}
        self.topic_file.write_text(json.dumps(topic), encoding="utf-8")
        with closing(sqlite3.connect(self.progress_db)) as con, con:
            con.execute("CREATE TABLE topics (learner TEXT, topic TEXT, version TEXT, body TEXT)")
        self.client = self.enterContext(TestClient(create_app(topic_file=self.topic_file, progress_db=self.progress_db),
                                                   base_url="http://127.0.0.1"))

    def _record(self, learner="local", version="fixture-2", seen="fixture-introduction"):
        with closing(sqlite3.connect(self.progress_db)) as con, con:
            con.execute("DELETE FROM topics")
            con.execute("INSERT INTO topics VALUES (?,?,?,?)",
                        (learner, POLITE_TOPIC_ID, version, json.dumps({"read_introductions": [seen]})))

    def _analyze(self, text):
        response = self.client.post("/api/reading/analyze", json={"text": text})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual("".join(item["text"] for item in data["segments"]), text)
        return data

    def test_lexicon_before_study_and_preserving_text(self):
        data = self._analyze("  食べませんでした。\n飲みます。<和語> 🍵")
        self.assertFalse(data["grammar_ready"])
        words = {item["text"]: item for item in data["segments"] if item["kind"] == "word"}
        self.assertEqual((words["食べ"]["lemma"], words["食べ"]["reading"], words["食べ"]["gloss"]),
                         ("食べる", "たべる", "吃"))
        self.assertEqual(words["飲み"]["lemma"], "飲む")
        self.assertFalse(any(item["kind"] == "grammar" for item in data["segments"]))
        with closing(sqlite3.connect(self.progress_db)) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM topics").fetchone(), (0,))

    def test_grammar_requires_current_local_lesson_and_does_not_change_progress(self):
        text = "食べませんでした。飲みません。夕方に行きました。読みます。ますらお。"
        for fixture in ({"learner": "someone-else"}, {"version": "fixture-1"}, {"seen": "another-introduction"}):
            self._record(**fixture)
            self.assertFalse(self._analyze(text)["grammar_ready"])
        self._record()
        before = self.progress_db.read_bytes()
        data = self._analyze(text)
        self.assertTrue(data["grammar_ready"])
        grammar = [item for item in data["segments"] if item["kind"] == "grammar"]
        self.assertEqual([item["text"] for item in grammar], ["ませんでした", "ません", "ました", "ます"])
        self.assertEqual([item["text"] for item in grammar[0]["parts"]], ["ませ", "ん", "でし", "た"])
        self.assertEqual({item["point_id"] for item in grammar}, {POLITE_POINT_ID})
        self.assertEqual(self.progress_db.read_bytes(), before)

    def test_clean_checkout_can_run_and_rejects_other_hosts(self):
        with TestClient(create_app(), base_url="http://127.0.0.1") as client:
            self.assertIn('id="readingApp"', client.get("/").text)
            self.assertEqual(client.get("/reading.js").status_code, 200)
            response = client.post("/api/reading/analyze", json={"text": "食べました。"})
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["lesson_url"])
            self.assertFalse(response.json()["grammar_ready"])
            self.assertEqual(client.get("/", headers={"Host": "external.example"}).status_code, 400)
            self.assertEqual(client.post("/api/reading/analyze", json={"text": "あ" * 2001}).status_code, 422)
