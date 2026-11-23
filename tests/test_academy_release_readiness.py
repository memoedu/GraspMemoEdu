from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import release_academy_production as release
from scripts.release_academy_production import wait_for_health
from tests.fixtures import temporary_test_directory


class ReadinessTests(unittest.TestCase):
    def run_health(self, ready_at, state='active', timeout=600):
        clock=[0]
        def sleep(seconds): clock[0]+=seconds
        def request(*args,**kwargs):
            if clock[0]<ready_at: raise ConnectionRefusedError('Still loading the catalog')
            return nullcontext(SimpleNamespace(status=200))
        with patch('scripts.release_academy_production.time.monotonic',side_effect=lambda:clock[0]), \
             patch('scripts.release_academy_production.time.sleep',side_effect=sleep), \
             patch('scripts.release_academy_production.urllib.request.urlopen',side_effect=request), \
             patch('scripts.release_academy_production.subprocess.run',return_value=SimpleNamespace(stdout=state)), \
             patch('builtins.print'):
            wait_for_health(timeout)
        return clock[0]

    def test_cold_catalog_can_become_ready_after_old_sixty_second_window(self):
        self.assertEqual(self.run_health(120),120)

    def test_failed_service_stops_instead_of_waiting_for_deadline(self):
        with self.assertRaisesRegex(RuntimeError,'service stopped.*failed'):
            self.run_health(120,state='failed')

    def test_active_but_unready_service_keeps_the_failure_deadline(self):
        with self.assertRaisesRegex(RuntimeError,'readiness deadline'):
            self.run_health(120,timeout=90)


class ContentReleaseTests(unittest.TestCase):
    def test_routine_content_activation_skips_backup_checks_and_unchanged_restarts(self):
        for changes_content in (False, True):
            with self.subTest(changes_content=changes_content), temporary_test_directory() as temp:
                root = Path(temp)
                data, stage = root / 'data', root / 'graspmemoedu-academy-test'
                (data / 'content-activation-history').mkdir(parents=True)
                package = stage / 'package'
                package.mkdir(parents=True)
                (package / 'manifest.json').write_text('{"adapter":"reading-book","files":{}}')
                (package / 'catalog.json').write_text('{"courses":[]}')
                (stage / 'release.json').write_text('{"commit":"content-only:test","files":{}}')
                pointer = data / 'active-content.json'
                pointer.write_text('{"generation":"previous"}')

                def mapped_path(value):
                    return {'/tmp': root, '/var/lib/graspmemoedu': data}.get(value, Path(value))

                def command(args, **kwargs):
                    if args[0] == 'runuser':
                        if changes_content:
                            pointer.write_text('{"generation":"next"}')
                        return SimpleNamespace(stdout=json.dumps({'generation': 'next', 'learning_records_changed': False}))
                    return SimpleNamespace(returncode=0)

                with patch.object(release, 'Path', mapped_path), \
                     patch.object(release.sys, 'argv', ['release', str(stage)]), \
                     patch.dict(release.sys.modules, {'grp': SimpleNamespace(getgrnam=lambda _: SimpleNamespace(gr_gid=0))}), \
                     patch.object(release.os, 'geteuid', return_value=0, create=True), \
                     patch.object(release.os, 'chown', create=True), \
                     patch.object(release.subprocess, 'run', side_effect=command) as run, \
                     patch.object(release.sqlite3, 'connect') as sqlite, \
                     patch.object(release, 'wait_for_health') as health, patch('builtins.print') as output:
                    release.main()

                commands = [call.args[0] for call in run.call_args_list]
                self.assertNotIn(['/usr/local/sbin/graspmemoedu-backup'], commands)
                self.assertEqual([cmd for cmd in commands if cmd[0] == 'systemctl'],
                                 [['systemctl', 'restart', 'graspmemoedu']] if changes_content else [])
                sqlite.assert_not_called()
                health.assert_called_once()
                self.assertIs(json.loads(output.call_args.args[0])['full_site_backup'], False)
