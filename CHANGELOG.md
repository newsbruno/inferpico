# Changelog

## 0.1.0 — 2026-10-18

Initial open-source release: dependency-free local CLI and single-page UI; synthetic offline demo; bounded, explicitly authorized OpenAI-compatible non-streaming requests; latency percentiles, reported usage and user-rate cost estimates; sanitized JSON exports; local Host/Origin/CSRF guards; 16 unit and local fake-provider integration tests.

Tested on Python 3.12. The code targets Python 3.10+. No paid provider calls were made during verification. Browser runtime/visual checks were not completed in the build environment because Chromium could not start under its sandbox; JavaScript syntax and local HTTP/security behavior were checked. No professional security audit is claimed.
