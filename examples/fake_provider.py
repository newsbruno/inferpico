#!/usr/bin/env python3
"""Loopback-only fake chat API for trying Inferpico without a key or charges.

The reply and token counts are fixed examples, not model measurements.
This server never forwards requests or logs prompts, keys, or request bodies.
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time


def create_server(port=8001, scenario='success'):
    if scenario not in ('success', 'missing-usage', 'rate-limit'):
        raise ValueError('Unknown scenario.')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def reply(self, status, payload):
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != '/v1/chat/completions':
                return self.reply(404, {'error': 'Use /v1/chat/completions.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 128 * 1024:
                    return self.reply(413, {'error': 'Request body too large or empty.'})
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or not isinstance(body.get('messages'), list):
                    raise ValueError()
            except (ValueError, UnicodeError, RecursionError):
                return self.reply(400, {'error': 'Expected chat completions JSON.'})
            if scenario == 'rate-limit':
                return self.reply(429, {'error': 'Simulated rate limit. No charge or retry.'})
            time.sleep(0.05)
            payload = {
                'choices': [{'message': {'role': 'assistant', 'content': 'Fixed fake response; no model was called.'},
                             'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 10},
            }
            if scenario == 'missing-usage':
                payload.pop('usage')
            self.reply(200, payload)

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8001)
    parser.add_argument('--scenario', choices=['success', 'missing-usage', 'rate-limit'], default='success')
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error('Port must be between 0 and 65535.')
    try:
        server = create_server(args.port, args.scenario)
    except OSError:
        parser.error('Could not bind loopback port; choose another --port.')
    print(f'Fake provider: http://127.0.0.1:{server.server_port}/v1/chat/completions', flush=True)
    print(f'Scenario: {args.scenario}. Fixed example tokens. No model, charges, or outbound requests.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
