from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

from training_fixtures import training_bank
from graspmemoedu.training_content import TrainingCatalog,fingerprint
from graspmemoedu.training import TrainingService
from graspmemoedu.oj_progress import location
from graspmemoedu.hydro_sync import extend,migrate_version
from scripts.sync_hydro import create_remote_stage, prepare, templates
from graspmemoedu.review_cards import point_id

class HydroSyncTests(unittest.TestCase):
    def test_staging_timeout_checks_the_same_directory_before_upload(self):
        timeout = subprocess.TimeoutExpired('ssh', 45)
        with patch('scripts.sync_hydro.run', side_effect=[timeout, None]) as remote:
            stage = create_remote_stage('example.invalid')
        create, verify = remote.call_args_list
        self.assertRegex(stage, r'^/tmp/graspmemoedu-hydro-sync-[0-9a-f]{32}$')
        self.assertEqual(create.args[0][-1], 'mkdir -m 700 -- ' + stage)
        self.assertEqual(create.kwargs['timeout'], 45)
        self.assertEqual(verify.args[0][:-1], create.args[0][:-1])
        self.assertIn('-nT', verify.args[0])
        self.assertIn('d=' + stage + ';', verify.args[0][-1])
        self.assertEqual(verify.kwargs['timeout'], 30)

    def test_unverified_staging_never_reaches_upload(self):
        timeout = subprocess.TimeoutExpired('ssh', 45)
        with patch('scripts.sync_hydro.run', side_effect=[timeout, RuntimeError('unverified')]) as remote:
            with self.assertRaisesRegex(RuntimeError, 'unverified'):
                create_remote_stage('example.invalid')
        self.assertEqual(remote.call_count, 2)
        with patch('scripts.sync_hydro.run', side_effect=RuntimeError('mkdir failed')) as remote:
            with self.assertRaisesRegex(RuntimeError, 'mkdir failed'):
                create_remote_stage('example.invalid')
        self.assertEqual(remote.call_count, 1)

    def test_accepted_facts_are_private_and_create_no_attempt_or_fsrs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'training-banks').mkdir()
            bank=training_bank();(root/'training-banks/isolated-bank.json').write_text(json.dumps(bank))
            catalog=TrainingCatalog(root);service=TrainingService(catalog,root,'owner')
            before=(root/'learning.sqlite3').read_bytes()
            path=location(root,'owner');path.parent.mkdir()
            path.write_text(json.dumps({'learner_id':'owner','bank_id':bank['id'],'questions':{'essay':{'submitted':True,'accepted':True,'accepted_at':'2026-10-26T00:00:00+00:00'}}}))
            self.assertTrue(service.group(bank['id'],'group-a')['questions'][0]['completed'])
            self.assertFalse(TrainingService(catalog,root,'other').group(bank['id'],'group-a')['questions'][0]['completed'])
            self.assertEqual((root/'learning.sqlite3').read_bytes(),before)

    def test_submission_without_ac_is_not_completion(self):
        from graspmemoedu.oj_progress import project_group
        row={'questions':[{'id':'q','completed':False,'completed_count':0}]}
        result=project_group(row,{'q':{'submitted':True,'accepted':False}})
        self.assertFalse(result['questions'][0]['completed'])
        self.assertTrue(result['questions'][0]['oj_status']['submitted'])

    def test_append_keeps_all_existing_questions_and_is_idempotent(self):
        bank=training_bank();bank['groups'].insert(0,{'id':'oj','title':'OJ','questions':[]})
        bank['version']=fingerprint(bank)
        q=deepcopy(next(q for g in bank['groups'] for q in g.get('questions',[])));q['id']='new-q'
        entry={'pid':'T9999','question':q,'topic':{'math_css':''}}
        result,added=extend(bank,[entry]);self.assertEqual(len(added),1)
        self.assertEqual(result['groups'][:len(bank['groups'])],bank['groups'])
        self.assertEqual(extend(result,[entry])[0],result)
        bad=deepcopy(entry);bad['question']['title']='changed'
        with self.assertRaises(ValueError):extend(result,[bad])

    def test_version_migration_preserves_cards_dates_and_foreign_keys(self):
        con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row
        con.executescript('''CREATE TABLE review_points(id TEXT PRIMARY KEY,subject TEXT,kind TEXT,container TEXT,version TEXT,source_point TEXT,created_at TEXT);
        CREATE TABLE review_reservations(paper TEXT,point TEXT REFERENCES review_points(id));
        CREATE TABLE training_memory(learner TEXT,bank TEXT,question TEXT,version TEXT,card_json TEXT,due_at TEXT);
        CREATE TABLE unrelated(id TEXT,body TEXT);''')
        old='a'*64;new='b'*64;pid=point_id('training','bank',old,'q')
        con.execute('INSERT INTO review_points VALUES (?,?,?,?,?,?,?)',(pid,'cs','training','bank',old,'q','yesterday'))
        con.execute('INSERT INTO review_reservations VALUES (?,?)',('paper',pid))
        con.execute('INSERT INTO training_memory VALUES (?,?,?,?,?,?)',('learner','bank','q',old,'{"stability": 45}','2026-11-01'))
        con.execute('INSERT INTO unrelated VALUES (?,?)',('keep','untouched'))
        migrate_version(con,'bank',old,new)
        self.assertEqual(con.execute('SELECT point FROM review_reservations').fetchone()[0],point_id('training','bank',new,'q'))
        row=con.execute('SELECT * FROM training_memory').fetchone()
        self.assertEqual((row['card_json'],row['due_at']),('{"stability": 45}','2026-11-01'))
        self.assertEqual(con.execute('SELECT body FROM unrelated').fetchone()[0],'untouched')

    def test_numeric_source_number_is_append_only_and_path_safe(self):
        bank=training_bank();bank['groups'].insert(0,{'id':'oj','title':'OJ','questions':[]})
        bank['version']=fingerprint(bank)
        q=deepcopy(next(q for g in bank['groups'] for q in g.get('questions',[])));q['id']='numeric-q'
        entry={'pid':'42','question':q,'topic':{'math_css':''}}
        result,added=extend(bank,[entry])
        self.assertEqual(result['groups'][-1]['id'],'oj-42')
        self.assertEqual(len(added),1)
        self.assertEqual(extend(result,[entry])[1],[])
        for pid in ['../42','42/1','-42','42;exit','',42]:
            with self.subTest(pid=pid),self.assertRaises(ValueError):
                extend(bank,[{**entry,'pid':pid}])

    def test_packaged_multitype_submission_keeps_contract_without_fake_main(self):
        body='### 枚举 `Heading`\n```java\nEAST, NORTH\n```\n### 类 `Agent`\n```java\nprivate final int id;\npublic Agent(Heading heading);\npublic Heading getHeading();\n```\n只提交 Main.java，不要编写 `main` 方法。\n```java\npackage demo.model;\n```'
        files,source=templates(body)
        self.assertEqual(source,'src/Main.java')
        self.assertTrue(files[source].startswith('package demo.model;\n'))
        self.assertIn('// public Agent(Heading heading);',files[source])
        self.assertIn('// private final int id;',files[source])
        self.assertNotIn('static void main',files[source])
        self.assertIn('//Todo',files[source])

    def test_no_main_canary_accepts_english_and_other_chinese_wording(self):
        for requirement in ['不编写 `main()`。','Do not write a `main` method.','不需要编写 main 方法。']:
            body='### 类 `Catalog`\n```java\npublic Catalog();\npublic void add(Item item);\n```\n'+requirement
            with self.subTest(requirement=requirement):
                files,source=templates(body)
                self.assertIn('// public void add(Item item);',files[source])
                self.assertNotIn('Scanner',files[source])
        with self.assertRaisesRegex(ValueError,'No Java source contract'):
            templates('不要编写 main 方法。')
        with self.assertRaisesRegex(ValueError,'Conflicting submission package'):
            templates('不编写 main。\n```java\npackage a;\npackage b;\n```')

    def test_no_main_assignment_preserves_inline_declarations(self):
        for requirement in ['不需要自行编写main方法。','不要包含包声明、其他类型或 `main()` 方法。']:
            with self.subTest(requirement=requirement):
                files,source=templates(requirement+'\n- `public Widget(int size)`\n- `public int getSize()`')
                self.assertIn('// public Widget(int size)',files[source])
                self.assertIn('// public int getSize()',files[source])
                self.assertNotIn('static void main',files[source])
                self.assertNotIn('Scanner',files[source])

    def test_interrupted_prepare_reuses_multifile_author_binding_and_preserves_answer(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in ['student','author']:
                course=root/name;(course/'OJ/Practice').mkdir(parents=True)
                (course/'course-info.yaml').write_text('title: Recovery fixture\ncontent: [OJ]\n')
                (course/'settings.gradle').write_text('')
                (course/'OJ/Practice/lesson-info.yaml').write_text('content: []\n')
            config={'student':str(root/'student'),'author':str(root/'author'),
                    'hydro_config':str(root/'hydro.json'),'manifest':str(root/'manifest.json'),
                    'data_dir':str(root/'data'),'bank_id':'isolated-bank'}
            (root/'hydro.json').write_text(json.dumps({'bindings':[]}))
            (root/'manifest.json').write_text(json.dumps({'tasks':{}}))
            body='只提交 class `Widget`，不要编写 main 方法。请根据题目要求实现全部方法，保留已有程序。[教师测试文件](file://WidgetTest.java)\n```java\nString getName();\n```\n```java\npublic class Demo { public static void main(String[] args) {} }\n```'
            snapshot={'origin':'https://example.invalid','domain':'fixture','user_id':1,
                      'fetched_at':'2026-01-01T00:00:00Z','complete':True,
                      'problems':[{'pid':'R123','title':'Fixture','config':{'langs':['java']},'content':json.dumps({'zh':body}),
                                   'additional_file':[{'name':'WidgetTest.java'}]}],
                      'statuses':{'R123':{'submitted':False,'accepted':False}}}
            work=root/'first';work.mkdir()
            task=prepare(config,work,snapshot,{'published_pids':[]})[0]
            rel=task['task_path'];entry=task['source']
            student=root/'student'/rel/entry;student.write_text('// learner owns this answer\n')
            author=root/'author'/rel
            original=(author/entry).read_bytes()
            metadata=yaml.safe_load((author/'task-info.yaml').read_text())
            metadata['files'].append({'name':'oj-status.md','visible':True})
            (author/'task-info.yaml').write_text(yaml.safe_dump(metadata))
            (author/'oj-status.md').write_text('runtime status')
            # Retry must reuse initialized author files without invoking a new template rule.
            retry=root/'retry';retry.mkdir()
            with patch('scripts.sync_hydro.templates',side_effect=AssertionError('must reuse the original template')):
                self.assertEqual(prepare(config,retry,snapshot,{'published_pids':[]})[0]['source'],entry)
            self.assertEqual(student.read_text(),'// learner owns this answer\n')
            stage=retry/'staging'/rel
            self.assertEqual((stage/entry).read_bytes(),original)
            self.assertTrue((stage/'src/Demo.java').is_file())
            self.assertFalse((stage/'src/Main.java').exists())
            self.assertIn('(https://example.invalid/d/fixture/p/R123/file/WidgetTest.java)',(stage/'task.md').read_text(encoding='utf-8'))
            self.assertFalse((stage/'assets').exists())
            self.assertNotIn('oj-status.md',[f['name'] for f in yaml.safe_load((stage/'task-info.yaml').read_text())['files']])

    def test_non_main_class_uses_source_method_contract(self):
        for name in ['User','Wallet']:
            body='只提交 class `'+name+'`，不要编写 main 方法。String `account`、double `money`。\n```java\nString getAccount();\nvoid deposit(double value);\n```\n```java\npublic class Example { public static void main(String[] args) {} }\n```'
            files,source=templates(body)
            self.assertEqual(source,'src/'+name+'.java')
            self.assertIn('public void deposit(double value)',files[source])
            self.assertNotIn('static void main',files[source])
            self.assertIn('src/Example.java',files)
