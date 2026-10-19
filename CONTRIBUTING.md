# Contributing

Inferpico is a small local utility for checking one OpenAI-compatible endpoint at a time. Help with measurement accuracy, clear failure handling, accessibility, provider compatibility examples and documentation is welcome. Please discuss larger features in an issue before building them.

## Development

Python 3.10 or newer is required. Runtime code uses the standard library; packaging uses setuptools. No JavaScript build step is needed.

```sh
git clone https://github.com/newsbruno/inferpico.git
cd inferpico
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
inferpico demo
inferpico serve
```

On Windows, create the environment with `py -m venv .venv` and activate it with `.venv\Scripts\Activate.ps1` in PowerShell. If activation is unavailable, invoke `.venv\Scripts\python.exe` and `.venv\Scripts\inferpico.exe` directly.

Use [the fake provider](examples/README.md) for integration work. Never require a paid API or credentials in tests. To check packaging, install a built wheel into a fresh environment and run `python scripts/check_install.py` from the source checkout with that environment active. CI performs an installation check on Linux, macOS and Windows.

## Changes and review

- Keep changes focused, with a clear problem statement and verification steps.
- Add regression coverage when fixing behavior; exercise malformed responses and failures, not only successful requests.
- Test the local UI in a real browser when changing it: demo, validation, fake-provider run, unknown usage/errors and JSON export. Check keyboard operation and a narrow viewport.
- Keep the runtime dependency-free and the UI free of third-party assets or remote network requests.
- Preserve explicit authorization, loopback binding, request limits, report redaction and unknown usage/cost semantics.
- Do not introduce provider price tables, benchmark rankings or quality claims without evidence and an agreed maintenance plan.

Never commit keys, `.env` files, private prompts or real provider response bodies. See [SECURITY.md](SECURITY.md) for responsible reporting. By submitting a contribution, you agree that it can be distributed under the project's [MIT license](LICENSE).
