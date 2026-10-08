# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| v0.3.0-beta | ✅ |
| older betas | ❌ |

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately via GitHub's security advisory feature
(*Security → Report a vulnerability* on the repository), or email the maintainer
through a GitHub issue marked private. We will acknowledge within a few days and
work with you on a coordinated disclosure.

## What we protect by default

- No screenshots or recognition history are saved unless you enable
  *General → Save screenshots and recognition history*.
- API keys are read from environment variables and never written to logs.
- The diagnostics export (ZIP) is a strict allowlist: only sanitized config,
  runtime environment, and recent logs — never screenshots, history, models, or keys.

## Third-party data

Using an online translation provider sends recognized text to that third party.
This is documented in the README and surfaced in the UI. Choose a provider you trust.
