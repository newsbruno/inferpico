# Changelog

## 0.2.0 — 2026-10-19

- Installable Python package with an `inferpico` command and bundled browser assets; no third-party runtime dependencies.
- Clearer installation, offline demo, fake-provider and live-endpoint onboarding, with explicit measurement, privacy and provider-cost boundaries.
- Stricter provider response and credential validation, safer output-file handling and documented CLI interruption behavior.
- Local fake-provider examples and expanded regression coverage for failures, limits and redaction.
- Per-submission browser consent, automatic expansion of invalid advanced fields, stale-report labels, actionable failure hints and SVG icons.
- CI for Python 3.10 and 3.14 on Linux, macOS and Windows, including installed-package smoke checks.

Candidate verification: 29 automated tests pass on Python 3.13.3/macOS using synthetic data and loopback fake providers. The installed wheel's CLI, module demo and bundled UI assets pass smoke checks. JavaScript syntax and 16 isolated UI logic assertions pass. Browser runtime/visual QA is blocked and has not passed; the configured cross-platform CI has not run yet. No paid provider calls or model performance/quality claims are part of this candidate.

## 0.1.0 — 2026-10-18

Initial open-source release: dependency-free local CLI and single-page UI; synthetic offline demo; bounded, explicitly authorized OpenAI-compatible non-streaming requests; latency percentiles, reported usage and user-rate cost estimates; sanitized JSON exports; local Host/Origin/CSRF guards; 16 unit and local fake-provider integration tests.

Tested on Python 3.12. The code targets Python 3.10+. No paid provider calls were made during verification. Browser runtime/visual checks were not completed in the build environment because Chromium could not start under its sandbox; JavaScript syntax and local HTTP/security behavior were checked. No professional security audit is claimed.
