# References and scope

Reviewed 18 October 2026. These are protocol and design references, not endorsements or affiliations.

- [OpenAI Chat Completions create reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): message shape, non-streaming request, `max_completion_tokens`, and usage fields. The checker uses the compatible Chat Completions surface; it does not implement OpenAI Responses, audio, tools or streaming.
- [vLLM serving benchmark CLI](https://docs.vllm.ai/en/latest/cli/bench/serve/): distinguishes full-request latency, TTFT and inter-token metrics. This checker measures only full-response wall time, and does not claim to replace a load benchmark.
- [promptfoo deterministic assertions](https://www.promptfoo.dev/docs/configuration/expected-outputs/deterministic/): an established option for explicit cost, latency and quality checks when you need a richer evaluation workflow. Inferpico Check does not evaluate answer quality.
- [Inferact](https://inferact.ai/): inspiration for making inference approachable. This project is separate and unaffiliated.
- [The ChatGPT home page](https://help.openai.com/en/articles/9125172-the-chatgpt-home-page): inspiration for beginning with an immediate input rather than a settings dashboard.
- [Anthropic prompt improver](https://www.anthropic.com/news/prompt-improver): inspiration for a focused input-to-feedback workflow and progressive disclosure. No Claude assets, branding, code, or product integration are used.

Percentile definition in this implementation: median for p50; sorted value at `ceil(0.95 × n) - 1` for p95. Calculations use successful requests, report sample counts and warn that samples are small. Cost is arithmetic using user-entered rates, never a claim about current provider pricing.
