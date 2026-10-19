#!/usr/bin/env python3
"""Inferpico Check: local-first, dependency-free LLM latency and cost checks."""
import argparse
import concurrent.futures
import json
import math
import os
from pathlib import Path
import secrets
import statistics
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = '0.1.0'
ROOT = Path(__file__).resolve().parent
MAX_RESPONSE = 2 * 1024 * 1024


def number(value, name, low, high, integer=False):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a number.')
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError(f'{name} must be a number.') from None
    if not math.isfinite(result) or not low <= result <= high or (integer and result != int(result)):
        raise ValueError(f'{name} must be between {low} and {high}' + (' (whole numbers).' if integer else '.'))
    return int(result) if integer else result


def endpoint_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise ValueError('Enter a valid full chat completions URL.')
    try:
        url = urllib.parse.urlsplit(value)
        port = url.port
    except ValueError:
        raise ValueError('Invalid endpoint URL.') from None
    if not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment:
        raise ValueError('Endpoint must have a hostname and no credentials, query, or fragment.')
    if url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise ValueError('Use HTTPS, or HTTP on localhost for a local model.')
    if not url.path or url.path == '/':
        raise ValueError('Enter the full endpoint path, usually /v1/chat/completions.')
    return value


def config(raw):
    if not isinstance(raw, dict):
        raise ValueError('Settings must be an object.')
    mode = raw.get('mode', 'demo')
    if mode not in ('demo', 'live'):
        raise ValueError('Choose demo or live mode.')
    model = raw.get('model', 'synthetic-model')
    prompt = raw.get('prompt', 'Explain what an API is in two short sentences.')
    if not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError('Enter a model ID (up to 200 characters).')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 8000:
        raise ValueError('Enter a prompt (up to 8,000 characters).')
    result = dict(mode=mode, model=model.strip(), prompt=prompt,
                  count=number(raw.get('count', 5), 'Requests', 1, 20, True),
                  concurrency=number(raw.get('concurrency', 1), 'Concurrency', 1, 4, True),
                  timeout=number(raw.get('timeout', 30), 'Timeout', 1, 120),
                  max_tokens=number(raw.get('max_tokens', 128), 'Output token limit', 1, 4096, True))
    result['concurrency'] = min(result['concurrency'], result['count'])
    for field in ('input_rate', 'output_rate'):
        value = raw.get(field)
        result[field] = None if value in (None, '') else number(value, field, 0, 100000)
    result['token_parameter'] = raw.get('token_parameter', 'max_completion_tokens')
    if result['token_parameter'] not in ('max_completion_tokens', 'max_tokens'):
        raise ValueError('Unsupported output limit parameter.')
    if mode == 'live':
        if raw.get('confirmed') is not True:
            raise ValueError('Confirm that this run sends your prompt to the endpoint and may incur charges. There is no hard dollar cap.')
        result['endpoint'] = endpoint_url(raw.get('endpoint', ''))
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def tokens(usage, field):
    value = usage.get(field) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 1_000_000_000_000 else None


def request_one(settings, index, key):
    start = time.perf_counter()
    row = dict(request=index + 1, ok=False, latency_ms=None, input_tokens=None, output_tokens=None, error=None)
    try:
        body = json.dumps({'model': settings['model'], 'messages': [{'role': 'user', 'content': settings['prompt']}],
                           'stream': False, settings['token_parameter']: settings['max_tokens']}).encode()
        headers = {'Content-Type': 'application/json', 'User-Agent': f'Inferpico-Check/{VERSION}'}
        if key:
            headers['Authorization'] = 'Bearer ' + key
        req = urllib.request.Request(settings['endpoint'], data=body, headers=headers, method='POST')
        # No environment proxy or redirect: credentials go only to the chosen URL.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(req, timeout=settings['timeout']) as response:
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise ValueError('response_too_large')
            parsed = json.loads(data)
        if (not isinstance(parsed, dict) or not isinstance(parsed.get('choices'), list) or not parsed['choices']
                or not isinstance(parsed['choices'][0], dict) or not isinstance(parsed['choices'][0].get('message'), dict)):
            raise ValueError('invalid_response')
        row.update(ok=True, input_tokens=tokens(parsed.get('usage'), 'prompt_tokens'),
                   output_tokens=tokens(parsed.get('usage'), 'completion_tokens'))
    except urllib.error.HTTPError as exc:
        row['error'] = 'http_' + str(exc.code)
        exc.close()
    except (TimeoutError,):
        row['error'] = 'timeout'
    except urllib.error.URLError as exc:
        row['error'] = 'timeout' if isinstance(exc.reason, TimeoutError) else 'connection_or_tls_error'
    except (json.JSONDecodeError, UnicodeError):
        row['error'] = 'invalid_json'
    except ValueError as exc:
        row['error'] = str(exc) if str(exc) in ('response_too_large', 'invalid_response') else 'invalid_response'
    except Exception:
        # Never echo provider errors, which may contain prompts, keys, or URLs.
        row['error'] = 'request_failed'
    row['latency_ms'] = round((time.perf_counter() - start) * 1000, 2)
    return row


def summarize(settings, rows, elapsed):
    successful = [r for r in rows if r['ok']]
    latencies = sorted(r['latency_ms'] for r in successful)
    complete = [r for r in successful if r['input_tokens'] is not None and r['output_tokens'] is not None]
    rates = settings['input_rate'], settings['output_rate']
    subtotal = None
    if None not in rates and complete:
        subtotal = sum(r['input_tokens'] * rates[0] + r['output_tokens'] * rates[1] for r in complete) / 1_000_000
    all_known = len(complete) == len(rows) and bool(rows)
    return {'schema_version': 1, 'tool_version': VERSION, 'mode': settings['mode'],
            'synthetic': settings['mode'] == 'demo',
            'settings': {k: settings[k] for k in ('count', 'concurrency', 'timeout', 'max_tokens', 'token_parameter', 'input_rate', 'output_rate')},
            'summary': {'attempted': len(rows), 'successful': len(successful), 'failed': len(rows) - len(successful),
                        'p50_ms': round(statistics.median(latencies), 2) if latencies else None,
                        'p95_ms': latencies[max(0, math.ceil(len(latencies) * .95) - 1)] if latencies else None,
                        'usage_known_requests': len(complete), 'elapsed_seconds': round(elapsed, 3),
                        'input_tokens': sum(r['input_tokens'] for r in complete) if all_known else None,
                        'output_tokens': sum(r['output_tokens'] for r in complete) if all_known else None,
                        'known_usage_cost_usd': subtotal,
                        'estimated_total_cost_usd': subtotal if all_known else None},
            'notes': [
                'Synthetic demo; no API requests were made. Numbers are illustrative, not benchmark results.' if settings['mode'] == 'demo' else 'Real non-streaming requests. Latency includes connection setup and full response transfer; not time to first token.',
                'p50 is median; p95 is nearest rank, successful requests only. Small samples are noisy; at fewer than 20 successes p95 is the maximum.',
                'Cost uses only reported prompt/completion usage and your USD per-million rates. Missing usage is unknown, never zero. Failed requests may still be billed.',
                'Estimate excludes cache discounts, provider-specific token categories, tools, taxes and minimum charges. Verify the provider invoice. No hard dollar cap.',
                'No output-quality evaluation is performed. Prompt, key, model ID, endpoint and generated text are excluded from this report.'],
            'requests': rows}


def run(raw, key=None):
    settings = config(raw)
    start = time.perf_counter()
    if settings['mode'] == 'demo':
        rows = [dict(request=i + 1, ok=True, latency_ms=[362, 518, 441, 694, 407, 560, 480][i % 7],
                     input_tokens=24, output_tokens=48 + i % 5, error=None) for i in range(settings['count'])]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings['concurrency']) as pool:
            rows = list(pool.map(lambda i: request_one(settings, i, key or ''), range(settings['count'])))
    return summarize(settings, rows, time.perf_counter() - start)


def serve(port):
    csrf = secrets.token_urlsafe(32)
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass

        def reply(self, status, body, mime='application/json'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def do_GET(self):
            if not self.trusted():
                return self.reply(403, {'error': 'Open the exact 127.0.0.1 URL printed in your terminal.'})
            paths = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path not in paths:
                return self.reply(404, {'error': 'Not found.'})
            name, mime = paths[self.path]
            data = (ROOT / 'web' / name).read_bytes().replace(b'__CSRF__', csrf.encode())
            self.reply(200, data, mime)

        def do_POST(self):
            origin = f'http://127.0.0.1:{self.server.server_port}'
            if not self.trusted() or self.headers.get('Origin') != origin or self.headers.get('X-Inferpico-Token') != csrf:
                return self.reply(403, {'error': 'Request blocked. Reload the local app.'})
            if self.path != '/api/run':
                return self.reply(404, {'error': 'Not found.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 20000:
                    return self.reply(413, {'error': 'Request too large or empty.'})
                if self.headers.get('Content-Type') != 'application/json':
                    return self.reply(415, {'error': 'JSON required.'})
                raw = json.loads(self.rfile.read(length))
                config(raw)
            except (ValueError, TypeError, UnicodeError) as exc:
                return self.reply(400, {'error': str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else 'Invalid settings.'})
            if not lock.acquire(blocking=False):
                return self.reply(409, {'error': 'A check is already running. Wait for it to finish.'})
            try:
                result = run(raw, os.environ.get('INFERPICO_API_KEY', ''))
                self.reply(200, result)
            finally:
                lock.release()
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'Inferpico Check → http://127.0.0.1:{server.server_port}\nLocal only. Ctrl+C to stop. No telemetry.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    ui = sub.add_parser('serve', help='Open the local web app (default port 8765)')
    ui.add_argument('--port', type=int, default=8765)
    demo = sub.add_parser('demo', help='Synthetic, offline sample report')
    demo.add_argument('--output', type=Path)
    live = sub.add_parser('run', help='Make explicitly authorized real requests')
    live.add_argument('--endpoint', required=True)
    live.add_argument('--model', required=True)
    live.add_argument('--prompt', default='Explain what an API is in two short sentences.')
    live.add_argument('--count', type=int, default=5)
    live.add_argument('--concurrency', type=int, default=1)
    live.add_argument('--timeout', type=float, default=30)
    live.add_argument('--max-tokens', type=int, default=128)
    live.add_argument('--token-parameter', choices=['max_completion_tokens', 'max_tokens'], default='max_completion_tokens')
    live.add_argument('--input-rate', type=float)
    live.add_argument('--output-rate', type=float)
    live.add_argument('--confirm-paid-run', action='store_true', help='Authorize prompt transmission and possible charges; no hard dollar cap')
    live.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.command == 'serve':
        if not 0 <= args.port <= 65535:
            parser.error('Port must be between 0 and 65535.')
        return serve(args.port)
    raw = vars(args).copy()
    raw['mode'] = 'demo' if args.command == 'demo' else 'live'
    raw['confirmed'] = raw.get('confirm_paid_run', False)
    if raw['mode'] == 'demo':
        raw.update(input_rate=.5, output_rate=2)
    try:
        result = run(raw, os.environ.get('INFERPICO_API_KEY', ''))
    except ValueError as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2) + '\n'
    if args.output:
        # Avoid overwriting an existing file accidentally.
        with args.output.open('x') as output:
            output.write(rendered)
        print(f'Saved report to {args.output}')
    else:
        print(rendered, end='')
    return 1 if result['summary']['failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
