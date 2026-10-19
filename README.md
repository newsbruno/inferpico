# Inferpico Check

A tiny local-first LLM cost and full-response latency checker. A calm single-page interface, a scriptable CLI, and inspectable JSON reports. Free, open source, and dependency-free. **Provider API calls can cost money.**

## Start in 30 seconds

Requires Python **3.10 or newer**. No installation or account required.

```sh
python3 inferpico.py serve
```

Open **http://127.0.0.1:8765**. Select **Run the demo**. The demo is entirely offline and uses fixed synthetic measurements. It does not benchmark any model or simulate your prompt. Demo rates default to illustrative $0.50 input / $2.00 output per million tokens when left blank.

Prefer the terminal?

```sh
python3 inferpico.py demo
python3 inferpico.py demo --output my-demo.json
```

The output file must not already exist. On Windows, `py` may replace `python3`.

## Check a real endpoint

1. Review your provider's pricing and configure provider-side spending limits where available.
2. If authentication is needed, set `INFERPICO_API_KEY` locally before starting the app. Do not put a key in a URL, prompt, report, or browser storage. For Bash, avoid placing its value in shell history:

   ```sh
   read -rsp 'API key: ' INFERPICO_API_KEY; echo
   export INFERPICO_API_KEY
   python3 inferpico.py serve
   unset INFERPICO_API_KEY
   ```

3. Choose **Use my endpoint**, enter the exact chat completions URL and model ID, then write a non-sensitive test prompt.
4. Set your current **USD per 1M input and output token rates** under request settings. Blank live rates mean unknown cost. No baked-in provider prices.
5. Review endpoint, request count and limits. Check the authorization box and run.

The key remains in the local server process and is sent in the Authorization header only to your selected endpoint. Your prompt and model ID go to that endpoint. Inferpico operates no API proxy and receives none of this data. Only use providers/endpoints you trust. A localhost model requiring no authentication works without a key. An environment key is sent to *any* endpoint you explicitly choose; unset it before testing an untrusted endpoint.

CLI equivalent (substitute your actual endpoint and model; example URL is intentionally a placeholder):

```sh
python3 inferpico.py run \
  --endpoint https://api.example.com/v1/chat/completions \
  --model your-model-id \
  --prompt 'Explain what an API is in two short sentences.' \
  --count 5 --concurrency 1 --max-tokens 128 --timeout 30 \
  --input-rate 0.50 --output-rate 2.00 \
  --confirm-paid-run --output check.json
```

`--confirm-paid-run` authorizes prompt transmission and possible provider charges. **There is no hard dollar spending cap.** The checker bounds requests (1–20), concurrency (1–4), output token parameter (1–4096), socket timeout (1–120 seconds), input length (8,000 characters) and response body (2 MiB). The provider must honor the output limit; billing and tokenization are provider-specific. Failed requests may be billed. Timeouts do not cancel generation at the provider.

The timeout is per network operation, **not a strict wall-clock deadline**; DNS and a slow-dripping response can take longer. Closing the browser tab does not cancel an active run. Wait for completion or stop the local process with Ctrl+C; already submitted requests may complete and be billed. No automatic retries, redirects, streaming, or environment HTTP proxies are used. The app accepts one run at a time.

Some compatible providers need `--token-parameter max_tokens` (or the matching UI setting) rather than the default `max_completion_tokens`. Compatibility means non-streaming chat completions JSON with `choices` and optional `usage.prompt_tokens` / `usage.completion_tokens`; this is not support for every provider or API feature. OpenAI's Responses API is not implemented.

## Read the numbers honestly

- **Latency:** wall time around each individual HTTP request through the complete response body. Includes connection setup; each request uses a new connection. Concurrent run measurements reflect that workload. No warm-up or connection pooling. This is not TTFT, server-only inference time, or a load test.
- **p50 / p95:** successful requests only. p50 is median; p95 uses nearest rank. At fewer than 20 successes, p95 is the largest successful latency. Even 20 requests is a very small sample. Compare repeat checks under matching conditions, not tiny differences.
- **Tokens:** only from reported API usage. Missing or invalid usage is unknown, never zero. No tokenizer guesses.
- **Estimated cost:** reported input/output tokens × your per-million rates. A total is only shown if every attempt succeeded with complete usage and both rates are supplied. Partial results can show a known-usage subtotal, not a total. Cache discounts, provider-specific billing categories, tools, taxes and minimum charges are excluded. Check the actual invoice.
- **Quality:** no correctness or output-quality evaluation is performed. A successful HTTP response is not a good answer.

Reports deliberately exclude endpoint, model ID, prompts, API keys, generated text and provider error bodies. This limits context leakage, but means you must label comparisons separately. No telemetry, accounts, database, persistent history, third-party scripts, fonts or assets. The browser holds only the current report until reload; export is explicit.

## Errors

`http_401` / `http_403`: check your key and endpoint permissions. `http_429`: provider rate limit or quota; inspect your provider account. Other `http_*`: provider status (redirects are rejected). `timeout`: a network operation exceeded the selected timeout. `connection_or_tls_error`: endpoint unavailable or TLS verification failed. `invalid_json` / `invalid_response`: incompatible response. `response_too_large`: response exceeded 2 MiB. `request_failed`: other transport error. Error bodies are never copied into reports. Review the issue before manually starting another run; another run can incur another charge.

## Test locally, without paid calls

```sh
python3 -m unittest discover -s tests -v
```

Tests use only synthetic data and a fake HTTP server bound to 127.0.0.1. They cover validation, missing usage, partial costs, errors/timeouts, redirects, request limits, report redaction and local UI origin/CSRF/Host guards. No real provider credentials or paid APIs are required.

## Project

- `inferpico.py`: CLI, measurement engine, loopback HTTP server
- `web/`: no-build, no-dependency local UI
- `demo-report.json`: synthetic example report
- `tests/`: unit and fake-provider integration tests
- [SECURITY.md](SECURITY.md): trust boundary and limitations
- [REFERENCES.md](REFERENCES.md): protocol, measurement and interaction references
- [LICENSE](LICENSE): MIT

This is a small initial release, not an audited security product or production benchmarking platform. One endpoint/model per run; no side-by-side comparison, streaming TTFT, cancellation API, or quality evaluator yet. It does not provision or deploy inference servers. It runs on your own computer, with results you can inspect and share deliberately.
