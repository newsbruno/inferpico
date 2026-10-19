# Try the real request flow without a paid API

The fake provider binds only to `127.0.0.1`. It never forwards a request, logs
prompts or credentials, or calls a model. Its reply and token counts are fixed
examples. HTTP timings describe this local test, not model performance.

From a source checkout, in a terminal without `INFERPICO_API_KEY` set:

```sh
python3 examples/fake_provider.py
```

In another terminal, run the source CLI:

```sh
python3 inferpico.py run \
  --endpoint http://127.0.0.1:8001/v1/chat/completions \
  --model fake-model --prompt 'A non-sensitive test prompt.' \
  --count 3 --concurrency 1 --input-rate 0.50 --output-rate 2.00 \
  --confirm-paid-run
```

An installed `inferpico` command supports the same arguments. The confirmation
flag is still required because this exercises live HTTP mode. This particular
example uses no paid service. The fake server reports 20 input and 10 output
tokens per request; these values are not tokenization estimates.

To try the browser, start `python3 inferpico.py serve`, open its printed loopback
URL, choose **Use my endpoint**, and use the same endpoint and `fake-model` ID.
Enter illustrative rates, review the destination and authorize each run.
Inspect the results and export JSON. Your environment key, if set, would also
be sent to this server, so leave it unset for this exercise.

Stop the fake server with Ctrl+C and restart it with a failure scenario:

```sh
python3 examples/fake_provider.py --scenario missing-usage
python3 examples/fake_provider.py --scenario rate-limit
```

Run only one server at a time on a given port. `missing-usage` returns a valid
assistant response without usage: success, unknown tokens/cost, CLI exit 0.
`rate-limit` returns HTTP 429: failed requests, unknown total cost, CLI exit 1.
Inferpico does not retry. To use another port, pass `--port 8002` to the fake
server and update the endpoint URL accordingly.
