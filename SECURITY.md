# Security and privacy

Inferpico Check runs locally and binds only to `127.0.0.1`. Do not expose it through a tunnel, reverse proxy, port forward, or public host. It is a developer utility, not a multi-user service. Anyone able to execute code as your local user can access process memory/environment and local files.

The local UI checks the exact Host header, exact browser Origin and a per-start random CSRF token for runs. CSP disallows external assets and framing. Responses are not cached; request access logs are disabled. Do not weaken these guards for remote hosting. Python's standard HTTP server is not hardened against local denial-of-service; use on a trusted workstation only.

API credentials come only from `INFERPICO_API_KEY` in the local server/CLI environment. They are not accepted in URLs, rendered in HTML, or stored in browser storage. The selected endpoint receives the key and prompt. Choose it carefully; an environment key applies to every live run. Use dedicated, least-privilege, budget-limited provider keys where supported. Unset the environment variable when finished. Environment variables are not a secure secrets vault.

HTTPS is mandatory except for exact loopback hostnames (`localhost`, `127.0.0.1`, `::1`). TLS certificate verification stays enabled. Embedded URL credentials, query strings and fragments are rejected. HTTP redirects and environment proxy settings are disabled, preventing inadvertent credential forwarding through those mechanisms. Other HTTPS hostnames, including private services, are allowed when explicitly selected; this is not an SSRF sandbox. DNS is resolved normally by the operating system.

Reports omit endpoint/model identifiers, prompts, response text, credentials and raw provider errors. User-selected token rates and aggregate measurements remain in exports. Consider whether that operational data is appropriate to share. No telemetry or background network checks. No backend operated by Inferpico receives your data.

Limits reduce accidental load, but are **not a dollar cap**. Providers can bill failures; socket timeouts and closing a browser tab do not guarantee a provider stops generation. The socket timeout does not impose a strict wall-clock deadline. Do not put confidential data in an experimental prompt.

To report a vulnerability, contact the project maintainer through the project's publication channel privately first. Do not post API keys or private prompts in an issue. Rotate exposed keys at their provider immediately. This release has automated tests but has not undergone an independent professional security audit.
