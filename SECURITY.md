# Security and privacy

Inferpico Check runs locally and binds only to `127.0.0.1`. Do not expose it through a tunnel, reverse proxy, port forward, or public host. It is a developer utility, not a multi-user service. Anyone able to execute code as your local user can access process memory/environment and local files.

The local UI checks the exact Host header, exact browser Origin and a per-start random CSRF token for runs. CSP disallows external assets and framing. Responses are not cached; request access logs are disabled. Do not weaken these guards for remote hosting. Python's standard HTTP server is not hardened against local denial-of-service; use on a trusted workstation only.

API credentials come only from `INFERPICO_API_KEY` in the local server/CLI environment. They are not accepted in URLs, rendered in HTML, or stored in browser storage. The selected endpoint receives the key and prompt. Choose it carefully; an environment key applies to every live run. Use dedicated, least-privilege, budget-limited provider keys where supported. Unset the environment variable when finished. Environment variables are not a secure secrets vault.

HTTPS is mandatory except for exact loopback hostnames (`localhost`, `127.0.0.1`, `::1`). TLS certificate verification stays enabled. Embedded URL credentials, query strings and fragments are rejected. HTTP redirects and environment proxy settings are disabled, preventing inadvertent credential forwarding through those mechanisms. Other HTTPS hostnames, including private services, are allowed when explicitly selected; this is not an SSRF sandbox. DNS is resolved normally by the operating system.

Reports omit endpoint/model identifiers, prompts, response text, credentials and raw provider errors. User-selected token rates and aggregate measurements remain in exports. Consider whether that operational data is appropriate to share. No telemetry or background network checks. No backend operated by Inferpico receives your data.

Limits reduce accidental load, but are **not a dollar cap**. Providers can bill failures; socket timeouts and closing a browser tab do not guarantee a provider stops generation. The socket timeout does not impose a strict wall-clock deadline. Do not put confidential data in an experimental prompt.

CLI interruption cancels queued work and waits for active socket operations to finish. It cannot revoke requests already accepted by a provider. An interrupted CLI run does not produce a partial report. Output files are created exclusively before requests start, so existing files and symlinks are not overwritten. New reports request owner-only mode `0600` on POSIX; Windows uses inherited ACLs without additional hardening. Report paths should still be in a directory you trust; this does not defend against another process with your user's filesystem permissions.

The offline demo uses fixed synthetic measurements and makes no API calls. The included fake provider binds to loopback and returns synthetic responses; it is only a development fixture. Build/install steps can fetch Python packaging tools, and installing from Git contacts GitHub. Runtime demo/UI assets do not need a network connection beyond local loopback traffic.

## Reporting and supported versions

Security fixes target the latest release. Update to the latest version before reproducing a report; older releases may not receive backports.

Use the repository's **Security → Report a vulnerability** option if enabled. If private reporting is unavailable and you do not have a private maintainer contact, open a minimal issue requesting one without disclosure details. Do not post exploit instructions, API keys, private prompts or provider response bodies publicly. Rotate exposed keys at their provider immediately. This project has automated tests but has not undergone an independent professional security audit.
