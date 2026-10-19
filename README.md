# Inferpico Check

Check an OpenAI-compatible endpoint's **full-response latency, reported token usage and estimated cost** from your own computer. A small Python CLI and local browser UI, with no runtime dependencies, account, telemetry or hosted key collection. MIT licensed.

**Provider calls can cost money.** Start with the offline demo or included fake provider. Inferpico does not evaluate answer quality, measure time to first token (TTFT), or rank models.

## Install and try the demo

Requires **Python 3.10 or newer**. Clone the repository and install into a virtual environment:

```sh
git clone https://github.com/newsbruno/inferpico.git
cd inferpico
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
inferpico demo
inferpico serve
```

Open **http://127.0.0.1:8765** and choose **Run the demo**. Use the exact `127.0.0.1` address printed in the terminal. Stop the server with Ctrl+C.

On Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
inferpico serve
```

If activation is unavailable, use `.venv\Scripts\python.exe -m pip install .` and `.venv\Scripts\inferpico.exe serve` directly. On macOS/Linux, `python3` can replace `python` outside an activated environment.

You can also install a tagged release directly with Git (Git must be installed):

```sh
python -m pip install "git+https://github.com/newsbruno/inferpico.git@v0.2.0"
```

Or download a release wheel and run `python -m pip install /path/to/inferpico_check-0.2.0-py3-none-any.whl`. The distribution is named `inferpico-check`; the command is `inferpico`. No PyPI publication is assumed. Installing from source may download setuptools as a build dependency; installed Inferpico has no third-party runtime dependencies. To run a checkout without installing, use `python3 inferpico.py demo` or `python3 inferpico.py serve`.

The demo is entirely offline and uses fixed synthetic measurements. It does not benchmark a model or simulate your prompt. Demo rates are illustrative **$0.50 input / $2.00 output per million tokens** when left blank in the UI.

```sh
inferpico demo --output my-demo.json
```

Reports are JSON. The output path must not already exist; Inferpico checks it before starting requests. `python -m inferpico` supports the same commands. To see all options, run `inferpico --help` or `inferpico run --help`.

## Exercise real HTTP locally, without a provider account

In a source checkout, start the included fake provider. Use a terminal without `INFERPICO_API_KEY` set for this exercise:

```sh
python examples/fake_provider.py
```

In another terminal with your environment activated:

```sh
inferpico run \
  --endpoint http://127.0.0.1:8001/v1/chat/completions \
  --model fake-model --prompt 'A non-sensitive test prompt.' \
  --count 3 --input-rate 0.50 --output-rate 2.00 \
  --confirm-paid-run
```

No API key or paid service is required. The fake provider returns fixed synthetic usage. Its measured HTTP timings describe only this local exercise. In the browser, choose the live endpoint mode and use the same endpoint/model. See [examples/README.md](examples/README.md) for details.

## Check your own endpoint

1. Review your provider's current pricing and configure provider-side spending limits where available.
2. If authentication is needed, set `INFERPICO_API_KEY` in the terminal **before** starting Inferpico. For Bash, read it without placing the value in shell history:

   ```bash
   read -rsp 'API key: ' INFERPICO_API_KEY; echo
   export INFERPICO_API_KEY
   inferpico serve
   unset INFERPICO_API_KEY
   ```

3. In the browser, choose your own endpoint, enter the **full chat completions URL**, exact model ID and a non-sensitive prompt.
4. Enter your **USD per 1M input/output token rates**. Blank live rates mean unknown cost; no provider prices are built in.
5. Review the destination and request/output limits, check the authorization box and run.

The key stays in the local process until a live request sends it as an Authorization header to your chosen endpoint. The endpoint also receives your prompt and model ID. **An environment key is sent to any endpoint you choose.** Unset it before testing an untrusted endpoint or the fake provider. Never enter keys in URLs, prompts, reports or browser storage. Keyless local models work without the variable.

CLI equivalent (replace the placeholder endpoint/model and illustrative rates):

```sh
inferpico run \
  --endpoint https://api.example.com/v1/chat/completions \
  --model your-model-id \
  --prompt 'Explain what an API is in two short sentences.' \
  --count 5 --concurrency 1 --max-tokens 128 --timeout 30 \
  --input-rate 0.50 --output-rate 2.00 \
  --confirm-paid-run --output check.json
```

`--confirm-paid-run` authorizes prompt transmission and possible charges, including for a local or keyless endpoint. **There is no hard dollar spending cap.** Failed requests may be billed. Requests are bounded to 1–20 per run, concurrency 1–4, output limit parameter 1–4096 tokens, prompt length 8,000 characters, response body 2 MiB and socket timeout 1–120 seconds. Providers must honor the output limit; their billing and tokenization rules vary.

The timeout applies to blocking socket operations, **not a strict wall-clock deadline**. DNS lookup and a response that trickles data can take longer. Closing a browser tab does not cancel a run. CLI Ctrl+C cancels queued work and waits for active requests; already submitted requests may complete and be billed. An interrupted CLI run returns exit code 130 and writes no partial report. No automatic retries, redirects, streaming or environment HTTP proxies are used. The UI accepts one run at a time.

Some compatible providers need `--token-parameter max_tokens` (also available in the UI) instead of the default `max_completion_tokens`. Supported responses are non-streaming chat completions JSON with an assistant message and optional `usage.prompt_tokens` / `usage.completion_tokens`. Refusals and valid tool-call messages can count as successful responses; this does not assess their usefulness. This is not universal provider compatibility. The Responses API is not implemented.

## Interpret results

| Field | Meaning and limitation |
| --- | --- |
| Latency | Wall time around each HTTP request through the complete body. Includes connection setup; each request uses a new connection. No warm-up or pooling. Concurrent checks reflect their own workload. Not TTFT, server-only inference time or a load test. |
| p50 / p95 | Successful requests only. p50 is the median; p95 uses nearest rank. Below 20 successes, p95 is the largest successful latency. These are small samples: compare repeat checks under matching conditions. |
| Tokens | Provider-reported usage only. Missing or invalid usage is unknown, never zero. No local tokenizer guesses. |
| Estimated total cost | Reported tokens × your per-million rates, shown only if every attempt succeeded with complete usage and both rates are supplied. |
| Known-usage cost | A subtotal for successful requests with complete usage; it is not the total bill when other usage is unknown or requests failed. |
| Elapsed time | Time for the entire run; it is different from individual request latency, especially with concurrency. |

Cost estimates exclude cache discounts, special token categories, tools, taxes and minimum charges. Check your provider invoice. A successful response is not a quality score. Unknown cost is not free usage.

Reports exclude endpoints, model IDs, prompts, API keys, generated text and provider error bodies. Label comparisons separately if needed. Token rates and aggregate measurements remain in exports. No telemetry, accounts, database, persistent history, third-party scripts, fonts or assets. The browser holds the current report until reload; JSON export is explicit.

## Troubleshooting

| Error | Next step |
| --- | --- |
| `http_401` / `http_403` | Check the key and endpoint permissions. |
| `http_429` | Check the provider's rate limit, quota or billing account. |
| Other `http_*` | Check the provider status. Redirect responses are rejected; use the final endpoint URL directly. |
| `timeout` | A socket operation exceeded its timeout; the provider may still be generating. |
| `connection_or_tls_error` | Check the URL, local server and TLS certificate. Certificate verification remains enabled. |
| `invalid_json` / `invalid_response` | Check that the endpoint supports non-streaming chat completions and returns a valid assistant response. |
| `response_too_large` | The response exceeded 2 MiB. Lower the output limit. |
| `request_failed` | Another transport failure occurred. Inspect the provider locally; raw errors are redacted. |

Review failures before manually running again; another run can incur another charge. CLI exit codes: **0** for a completed run with no request failures, **1** when a run has failed requests, **2** for invalid arguments/settings or an output-file error, **130** for interruption. Unknown usage does not make an otherwise valid response fail. If port 8765 is occupied, use `inferpico serve --port 8766` and open the printed address.

## Development and scope

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use synthetic data and HTTP servers bound to `127.0.0.1`; no paid API or credentials are needed. CI is configured for Python 3.10 and 3.14 on Linux, macOS and Windows, including an installed CLI and bundled UI asset check. To avoid consuming private-repository Actions minutes, jobs run only when the repository is public. This configuration is not evidence that every platform has passed; consult the repository Actions results. See [CONTRIBUTING.md](CONTRIBUTING.md) for the browser checklist and packaging workflow.

- [SECURITY.md](SECURITY.md): trust boundary and responsible reporting
- [CHANGELOG.md](CHANGELOG.md): release changes
- [REFERENCES.md](REFERENCES.md): protocol and measurement references
- [LICENSE](LICENSE): MIT

This is a small developer utility, not a professionally audited security product or production benchmarking platform. One endpoint/model per run; no streaming TTFT, side-by-side comparison, cancellation API or quality evaluator. It does not provision or deploy inference servers. Keep its local server on your own trusted computer.
