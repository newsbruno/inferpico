"""Smoke-check the installed CLI/module/assets outside the source directory."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request


def main():
    executable = shutil.which('inferpico')
    if executable is None:
        raise SystemExit('inferpico command is missing; activate the installation environment.')
    with tempfile.TemporaryDirectory(prefix='inferpico-install-') as directory:
        probe = subprocess.run(
            [sys.executable, '-c',
             "import inferpico; from pathlib import Path; "
             "assert inferpico.VERSION == '0.2.0'; "
             "assert all((inferpico.ROOT / 'web' / name).is_file() "
             "for name in ('index.html', 'app.js', 'style.css')); "
             "print(Path(inferpico.__file__).resolve())"],
            cwd=directory, text=True, capture_output=True, check=True)
        location = Path(probe.stdout.strip())
        source_root = Path(__file__).resolve().parents[1]
        if source_root in location.parents:
            raise SystemExit('Expected an installed wheel; this resolves to the source checkout.')
        for command in ([executable, 'demo'], [sys.executable, '-m', 'inferpico', 'demo']):
            result = subprocess.run(command, cwd=directory, text=True,
                                    capture_output=True, check=True)
            report = json.loads(result.stdout)
            assert report['synthetic'] is True
            assert report['tool_version'] == '0.2.0'
            assert report['summary']['successful'] == 5
        process = subprocess.Popen([executable, 'serve', '--port', '0'], cwd=directory,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding='utf-8')
        try:
            startup = process.stdout.readline().strip()
            if not startup.startswith('Inferpico Check -> http://127.0.0.1:'):
                raise AssertionError('Installed UI did not start correctly.')
            url = startup.split('-> ', 1)[1]
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=5) as response:
                html = response.read().decode('utf-8')
                assert "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
            token = html.split('name="inferpico-token" content="', 1)[1].split('"', 1)[0]
            assert token != '__CSRF__'
            for asset in ('app.js', 'style.css'):
                with opener.open(url + '/' + asset, timeout=5) as response:
                    assert response.status == 200 and response.read()
            request = urllib.request.Request(url + '/api/run',
                data=json.dumps({'mode': 'demo', 'count': 1}).encode(),
                headers={'Origin': url, 'Content-Type': 'application/json', 'X-Inferpico-Token': token})
            with opener.open(request, timeout=5) as response:
                report = json.load(response)
                assert report['synthetic'] is True and report['tool_version'] == '0.2.0'
                assert report['summary']['successful'] == 1
        finally:
            process.terminate()
            process.communicate(timeout=5)
    print('Installed command, module, offline demo, UI assets and loopback HTTP demo: OK')


if __name__ == '__main__':
    main()
