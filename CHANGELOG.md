# Changelog

All notable changes to PyPath Inspector are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html) with the stricter
pre-1.0 policy described in [`VERSIONING.md`](VERSIONING.md).

Planned (not yet implemented) work is tracked in [`ROADMAP.md`](ROADMAP.md)
and must not be listed here as completed.

## [Unreleased]

### Added

- Project governance documentation: `ROADMAP.md` (development roadmap
  through 1.0.0), `VERSIONING.md` (versioning policy), `RELEASING.md`
  (release procedure) and this changelog. Documentation only; no runtime
  behaviour changed.
- Maintainer review decisions incorporated into the roadmap: support
  bundle deferred beyond 1.0.0; `pypath explain` rejected (diagnostic
  reports already carry full explanations); `--min-severity` moved into
  the 0.6.0 selective-diagnostics milestone; the diagnostic category
  vocabulary (`discovery`, `path`, `resolution`, `pip`, `venv`, `tools`)
  and command-specific `diff` exit codes (`0`/`1`/`3`/`4`, never `2`)
  approved; pre-release policy tightened to exceptional, justified use.
- Maintainer approved the consolidation of the former 0.8.0
  (explainability) and 0.9.0 (freeze) milestones into a single 0.8.0
  stabilization milestone, conditional on an explicit release-
  justification gate: 0.8.0 ships only as a substantial, externally
  verifiable compatibility/reliability improvement (new MINOR criterion
  added to `VERSIONING.md` §3); if the completed hardening does not meet
  that bar, no 0.8.0 is released and the work becomes mandatory 1.0.0
  readiness work.

### Planned for 0.1.1 (not yet implemented — see ROADMAP.md)

- README correction: the package **is** published on PyPI; the current
  install section still says otherwise and leads with source installs.
- Single source of truth for the version, automated version-consistency
  checks, a release asset build script, and a publish-workflow fix so
  PEP 440 pre-release tags (e.g. `v0.2.0a1`) can be published — currently
  impossible: canonical pre-release tags are rejected by the tag
  validation, and separator-form tags fail the asset-name checks
  (release-pipeline corrections).

## [0.1.0] - 2026-10-31

First public release. Tag `v0.1.0` (commit `1d83c24`), published on PyPI
via GitHub Actions Trusted Publishing (OIDC).

### Added

- Python interpreter discovery through PATH (`python`, `python3`,
  `pythonw`, POSIX versioned `python3.x` names), the Windows `py`
  launcher (`py -0p`) and `uv python list --only-installed`, with
  symlink/case-variant deduplication and per-interpreter probing
  (timeouts, `--version` fallback, Microsoft Store alias stub detection).
- Command resolution for `python`, `python3`, `pythonw`, `pip`, `pip3`,
  `py` and `uv` across all PATH entries, with PATHEXT ordering, shadowing
  analysis, duplicate/empty/nonexistent PATH entry detection and
  script-shim detection.
- Pip analysis: comparison of `pip`, `pip3` and `python -m pip` against
  the interpreter the `python` command actually runs; interpreter
  mismatch detection using host-independent, path-flavour-aware
  containment checks (`ntpath`/`posixpath`).
- Virtual environment analysis: venv detection via `sys.prefix` /
  `sys.base_prefix`, `pyvenv.cfg` presence, stale `VIRTUAL_ENV` state and
  conda environment presence (values of environment variables are never
  reported).
- 22 diagnostic findings with INFO/WARNING/ERROR severities, evidence,
  explanations and non-destructive remediation.
- Reporting: human-readable terminal output, JSON and Markdown reports,
  output file selection, and default home-directory redaction for
  exported formats (`--no-redact` to opt out).
- Stable exit codes: 0 clean, 1 warnings, 2 errors, 3 usage error,
  4 internal failure.
- Strictly read-only, offline operation with zero runtime dependencies;
  every subprocess call runs with a hard timeout.
- 139 machine-independent unit tests (fake subprocess runners,
  temporary directories).
- CI matrix: Windows, Linux and macOS across Python 3.11–3.15 (15/15
  jobs green on the release commit).
- PyPI publication workflow with SHA-256 asset verification and Trusted
  Publishing.
