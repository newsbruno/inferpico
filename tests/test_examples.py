"""Exercise the documented no-key provider through the actual CLI."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('fake_provider_example', ROOT / 'examples' / 'fake_provider.py')
fake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fake)


class ExampleTests(unittest.TestCase):
    def run_scenario(self, scenario):
        server = fake.create_server(0, scenario)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = os.environ.copy()
            environment.pop('INFERPICO_API_KEY', None)
            result = subprocess.run([
                sys.executable, str(ROOT / 'inferpico.py'), 'run',
                '--endpoint', f'http://127.0.0.1:{server.server_port}/v1/chat/completions',
                '--model', 'fake-model', '--count', '2', '--concurrency', '2',
                '--input-rate', '1', '--output-rate', '2', '--confirm-paid-run',
            ], capture_output=True, text=True, timeout=10, env=environment)
            return result, json.loads(result.stdout)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_documented_fake_provider_success(self):
        result, report = self.run_scenario('success')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report['mode'], 'live')
        self.assertEqual(report['summary']['successful'], 2)
        self.assertAlmostEqual(report['summary']['estimated_total_cost_usd'], 0.00008)
        self.assertNotIn('Fixed fake response', result.stdout)

    def test_example_missing_usage_stays_unknown(self):
        result, report = self.run_scenario('missing-usage')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(report['summary']['estimated_total_cost_usd'])
        self.assertEqual(report['summary']['usage_known_requests'], 0)

    def test_example_error_is_redacted_and_sets_exit_code(self):
        result, report = self.run_scenario('rate-limit')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report['summary']['failed'], 2)
        self.assertEqual([row['error'] for row in report['requests']], ['http_429', 'http_429'])
        self.assertNotIn('Simulated rate limit', result.stdout)


if __name__ == '__main__':
    unittest.main()
