from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.release_academy_production import wait_for_health


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
