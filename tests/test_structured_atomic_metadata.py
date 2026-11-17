"""Ancestry is metadata: it cannot smuggle content or change sibling ownership."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from scripts.prepare_structured_atomic import course_units


class StructuredMetadataTests(unittest.TestCase):
    def test_complete_ancestry_keeps_topics_only_in_selected_unit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'ancestors.json'
            path.write_text(json.dumps([{'id':'root','title':'Root'},
                {'id':'branch','title':'Branch','parent_id':'root'}]))
            args = SimpleNamespace(unit_id='leaf',unit_title='Leaf',unit_parent='branch',unit_ancestors=path)
            units = course_units(args,['new-a','new-b'])
            self.assertEqual([u['topic_ids'] for u in units],[[],[],['new-a','new-b']])
            self.assertEqual(units[-1]['parent_id'],'branch')
            for rows in ([{'id':'branch','title':'Branch','parent_id':'missing'}],
                         [{'id':'branch','title':'Branch','parent_id':'branch'}],
                         [{'id':'branch','title':'Branch','topic_ids':['existing']}],
                         [{'id':'leaf','title':'Duplicate'}]):
                with self.subTest(rows=rows):
                    path.write_text(json.dumps(rows))
                    with self.assertRaises(ValueError): course_units(args,['new-a'])

    def test_existing_callers_keep_single_unit(self):
        args=SimpleNamespace(unit_id='unit',unit_title='Unit',unit_parent=None)
        self.assertEqual(course_units(args,['new']),[{'id':'unit','title':'Unit','topic_ids':['new']}])
