import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inferpico as app


class FakeProvider(BaseHTTPRequestHandler):
    seen = []
    def log_message(self, *args): pass
    def do_POST(self):
        body = self.rfile.read(int(self.headers['Content-Length']))
        self.seen.append((self.path, self.headers.get('Authorization'), json.loads(body)))
        if self.path == '/redirect':
            self.send_response(307); self.send_header('Location', '/ok'); self.end_headers(); return
        if self.path == '/error':
            self.send_response(429); self.end_headers(); self.wfile.write(b'private prompt secret-key'); return
        if self.path == '/slow': time.sleep(1.2)
        self.send_response(200); self.end_headers()
        payload = {'choices': [{'message': {'role': 'assistant', 'content': 'secret generated text'}}],
                   'usage': {'prompt_tokens': 20, 'completion_tokens': 10}}
        if self.path == '/missing': payload.pop('usage')
        if self.path == '/invalidusage': payload['usage'] = {'prompt_tokens': -2, 'completion_tokens': True}
        if self.path == '/badshape': payload = {'error': 'private error'}
        if self.path == '/nullchoice': payload['choices'] = [None]
        if self.path == '/emptymessage': payload['choices'][0]['message'] = {}
        if self.path == '/wrongrole': payload['choices'][0]['message']['role'] = 'user'
        if self.path == '/badcontent': payload['choices'][0]['message']['content'] = {'private': 'secret-key'}
        if self.path == '/nullcontent': payload['choices'][0]['message']['content'] = None
        if self.path == '/refusal': payload['choices'][0]['message'].update(content=None, refusal='No.')
        if self.path == '/tool': payload['choices'][0]['message'].update(content=None, tool_calls=[{'type': 'function', 'function': {'name': 'test', 'arguments': '{}'}}])
        if self.path == '/mixederror': payload['error'] = 'private prompt secret-key'
        if self.path == '/hugeusage': payload['usage'] = {'prompt_tokens': 10**400, 'completion_tokens': 10**400}
        content = b'not json' if self.path == '/badjson' else json.dumps(payload).encode()
        if self.path == '/big': content = b'x' * (app.MAX_RESPONSE + 1)
        if self.path == '/nan': content = b'{"choices": [], "usage": NaN}'
        if self.path == '/deep': content = b'[' * 2000 + b'0' + b']' * 2000
        try: self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError): pass


class CoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), FakeProvider)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
    def live(self, path='/ok', **kwargs):
        return dict(mode='live', endpoint=self.url + path, model='private-model', prompt='private prompt', confirmed=True, **kwargs)
    def test_demo_offline_deterministic(self):
        result = app.run({'mode':'demo', 'count':5, 'input_rate':.5, 'output_rate':2})
        self.assertTrue(result['synthetic']); self.assertEqual(result['summary']['successful'],5)
        self.assertEqual(result['summary']['p50_ms'],441)
        self.assertEqual(result['summary']['p95_ms'],694)
        self.assertAlmostEqual(result['summary']['estimated_total_cost_usd'],.00056)
    def test_bounds(self):
        for field, value in [('count',10**400),('count',21),('count',0),('count',1.2),('count',True),('concurrency',5),('timeout',121),('max_tokens',0),('input_rate',-1),('output_rate',float('nan'))]:
            with self.subTest(field=field,value=value), self.assertRaises(ValueError): app.config({field:value})
    def test_validation(self):
        for raw in [[], {'mode':'other'}, {'prompt':''}, {'model':''}, {'prompt':'x'*8001}, {'token_parameter':'bad'}, {'mode':'live','endpoint':self.url+'/ok'}]:
            with self.subTest(raw=str(raw)[:30]), self.assertRaises(ValueError): app.config(raw)
    def test_endpoint_validation(self):
        for url in ['http://example.com/v1', 'https://user:password@example.com/v1', 'https://example.com/v1?key=secret', 'file:///etc/passwd', 'https://example.com', 'https://example.com/v1#fragment', 'https://example.com:bad/v1', 'https://example.com/\nfoo']:
            with self.subTest(url=url),self.assertRaises(ValueError): app.endpoint_url(url)
        self.assertEqual(app.endpoint_url(self.url+'/ok'), self.url+'/ok')
    def test_real_local_protocol_and_redaction(self):
        result=app.run(self.live(count=3, concurrency=2, input_rate=1, output_rate=2), 'secret-key')
        self.assertEqual(result['summary']['successful'],3)
        self.assertAlmostEqual(result['summary']['estimated_total_cost_usd'],.00012)
        path, auth, body=FakeProvider.seen[-1]
        self.assertEqual(auth,'Bearer secret-key'); self.assertFalse(body['stream'])
        self.assertEqual(body['max_completion_tokens'],128)
        for value in ['private prompt','secret-key','secret generated text','private-model', self.url]: self.assertNotIn(value,json.dumps(result))
    def test_no_retry_or_redirect(self):
        for path, error in [('/error','http_429'),('/redirect','http_307')]:
            before=len(FakeProvider.seen); result=app.run(self.live(path,count=1),'secret-key')
            self.assertEqual(len(FakeProvider.seen), before+1)
            self.assertEqual(result['requests'][0]['error'],error)
            self.assertEqual(result['summary']['failed'],1)
            self.assertIsNone(result['summary']['p50_ms'])
            self.assertNotIn('secret-key', json.dumps(result))
    def test_invalid_response_errors(self):
        for path,error in [('/badjson','invalid_json'),('/badshape','invalid_response'),('/nullchoice','invalid_response'),('/emptymessage','invalid_response'),('/wrongrole','invalid_response'),('/badcontent','invalid_response'),('/nullcontent','invalid_response'),('/mixederror','invalid_response'),('/nan','invalid_json'),('/deep','invalid_json'),('/big','response_too_large'),('/slow','timeout')]:
            result=app.run(self.live(path,count=1,timeout=1))
            self.assertEqual(result['requests'][0]['error'],error)
            self.assertIsInstance(result['requests'][0]['latency_ms'], (int, float))
            self.assertNotIn('secret-key', json.dumps(result))
    def test_textless_valid_completions(self):
        for path in ['/refusal', '/tool']:
            with self.subTest(path=path):
                self.assertEqual(app.run(self.live(path,count=1))['summary']['successful'], 1)
    def test_invalid_key_rejected_before_requests(self):
        before = len(FakeProvider.seen)
        for key in ['secret\nkey', 'secret key', 'private\u00e9', 'x' * 8193, 12]:
            with self.subTest(key_type=type(key)), self.assertRaises(ValueError) as error:
                app.run(self.live(count=2), key)
            self.assertNotIn('secret', str(error.exception))
        self.assertEqual(len(FakeProvider.seen), before)
    def test_http_error_body_is_closed_without_reading(self):
        body = io.BytesIO(b'private prompt secret-key')
        error = urllib.error.HTTPError(self.url, 401, 'secret-key', {}, body)
        with mock.patch.object(urllib.request.OpenerDirector, 'open', side_effect=error):
            row = app.request_one(app.config(self.live(count=1)), 0, 'secret-key')
        self.assertTrue(body.closed)
        self.assertEqual(row['error'], 'http_401')
        self.assertNotIn('secret-key', json.dumps(row))
    def test_unknown_usage_not_zero(self):
        for path in ['/missing','/invalidusage','/hugeusage']:
            result=app.run(self.live(path,count=1,input_rate=1,output_rate=2))
            self.assertEqual(result['summary']['successful'],1)
            self.assertIsNone(result['summary']['input_tokens'])
            self.assertIsNone(result['summary']['estimated_total_cost_usd'])
    def test_missing_and_zero_rates(self):
        self.assertIsNone(app.run({'mode':'demo'})['summary']['estimated_total_cost_usd'])
        self.assertEqual(app.run({'mode':'demo','input_rate':0,'output_rate':0})['summary']['estimated_total_cost_usd'],0)
    def test_partial_cost_is_not_total(self):
        settings=app.config({'input_rate':1,'output_rate':2})
        rows=[dict(ok=True,latency_ms=100,input_tokens=20,output_tokens=10), dict(ok=False,latency_ms=50,input_tokens=None,output_tokens=None)]
        summary=app.summarize(settings,rows,1)['summary']
        self.assertAlmostEqual(summary['known_usage_cost_usd'],.00004)
        self.assertIsNone(summary['estimated_total_cost_usd'])
    def test_legacy_token_parameter(self):
        app.run(self.live(count=1, token_parameter='max_tokens'))
        self.assertIn('max_tokens', FakeProvider.seen[-1][2])


class CliTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(app.ROOT / 'inferpico.py'), *args], capture_output=True, text=True)
    def test_output_existing_and_symlink_preserved_before_run(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            destination.write_text('keep this')
            link = Path(directory) / 'link.json'
            paths = [destination, Path(directory) / 'missing' / 'report.json']
            try:
                link.symlink_to(destination)
            except OSError:
                if os.name != 'nt':
                    raise
            else:
                paths.append(link)
            for path in paths:
                with self.subTest(path=path), mock.patch.object(app, 'run') as run:
                    with mock.patch.object(sys, 'argv', ['inferpico', 'demo', '--output', str(path)]), contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as error:
                            app.main()
                    self.assertEqual(error.exception.code, 2)
                    run.assert_not_called()
            self.assertEqual(destination.read_text(), 'keep this')
            if link in paths:
                self.assertTrue(link.is_symlink())
    def test_output_report_private_and_parseable(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            result = self.cli('demo', '--output', str(destination))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(destination.read_text())['synthetic'])
            if os.name != 'nt':
                self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
    def test_interrupted_output_removed_and_exit_130(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            with mock.patch.object(sys, 'argv', ['inferpico', 'demo', '--output', str(destination)]), mock.patch.object(app, 'run', side_effect=KeyboardInterrupt), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(app.main(), 130)
            self.assertFalse(destination.exists())
            self.assertIn('active requests may still be billed', err.getvalue())
    def test_invalid_settings_do_not_reserve_output(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            with mock.patch.object(sys, 'argv', ['inferpico', 'run', '--endpoint', 'http://localhost/fake', '--model', 'fake', '--output', str(destination)]), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    app.main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(destination.exists())
    def test_report_write_failure_cleans_file_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'report.json'
            output = mock.Mock()
            output.write.side_effect = OSError(28, 'No space left on device')
            output.close.side_effect = OSError(28, 'No space left on device')
            real_fdopen = os.fdopen
            def fake_fdopen(fd, *args, **kwargs):
                real_fdopen(fd, *args, **kwargs).close()
                return output
            with mock.patch.object(sys, 'argv', ['inferpico', 'demo', '--output', str(destination)]), mock.patch.object(os, 'fdopen', side_effect=fake_fdopen), contextlib.redirect_stderr(io.StringIO()) as err:
                with self.assertRaises(SystemExit) as error:
                    app.main()
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(destination.exists())
            self.assertIn('No space left on device', err.getvalue())
    def test_interrupt_cancels_queued_work(self):
        executor = mock.Mock()
        future = mock.Mock()
        future.result.side_effect = KeyboardInterrupt
        executor.submit.return_value = future
        with mock.patch.object(app.concurrent.futures, 'ThreadPoolExecutor', return_value=executor):
            with self.assertRaises(KeyboardInterrupt):
                app.run(dict(mode='live', endpoint='http://localhost/fake', model='fake', confirmed=True, count=4))
        self.assertEqual(future.cancel.call_count, 4)
        executor.shutdown.assert_called_once_with(wait=True, cancel_futures=True)


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.proc=subprocess.Popen([sys.executable,str(app.ROOT/'inferpico.py'),'serve','--port','0'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        line=cls.proc.stdout.readline(); cls.url=line.strip().split('-> ')[1]
        with urllib.request.urlopen(cls.url) as response:
            cls.html=response.read().decode(); cls.csp=response.headers['Content-Security-Policy']
        cls.token=cls.html.split('name="inferpico-token" content="')[1].split('"')[0]
    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate(); cls.proc.communicate(timeout=5)
    def post(self, body, **headers):
        base={'Origin':self.url,'Content-Type':'application/json','X-Inferpico-Token':self.token}
        base.update(headers)
        return urllib.request.urlopen(urllib.request.Request(self.url+'/api/run', data=json.dumps(body).encode(), headers=base))
    def test_assets(self):
        for path in ['/app.js','/style.css']:
            with urllib.request.urlopen(self.url+path) as r: self.assertEqual(r.status,200)
        self.assertIn("frame-ancestors 'none'", self.csp)
        self.assertNotIn('__CSRF__',self.html)
    def test_demo(self):
        with self.post({'mode':'demo'}) as r: self.assertTrue(json.load(r)['synthetic'])
    def test_cross_origin_and_csrf(self):
        for headers in [{'Origin':'https://evil.example'}, {'X-Inferpico-Token':'wrong'}]:
            with self.assertRaises(urllib.error.HTTPError) as err: self.post({'mode':'demo'},**headers)
            self.assertEqual(err.exception.code,403)
    def test_host_rebinding(self):
        req=urllib.request.Request(self.url,headers={'Host':'evil.example'})
        with self.assertRaises(urllib.error.HTTPError) as err: urllib.request.urlopen(req)
        self.assertEqual(err.exception.code,403)
    def test_live_requires_confirmation(self):
        with self.assertRaises(urllib.error.HTTPError) as err: self.post({'mode':'live'})
        self.assertEqual(err.exception.code,400)
    def test_malformed_json_is_rejected_and_server_survives(self):
        for body in [b'{"mode": NaN}', b'[' * 2000 + b'0' + b']' * 2000, b'\xff']:
            request = urllib.request.Request(self.url + '/api/run', data=body, headers={'Origin': self.url, 'Content-Type': 'application/json', 'X-Inferpico-Token': self.token})
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            with error.exception as response:
                self.assertEqual(response.code, 400)
                self.assertLess(len(response.read()), 200)
        with self.post({'mode': 'demo'}) as response:
            self.assertEqual(response.status, 200)

if __name__=='__main__': unittest.main()
