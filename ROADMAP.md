# PyPath Inspector — Development Roadmap

This document is the project's development roadmap from the released `0.1.0`
through `1.0.0`. It is grounded in the actual repository state at commit
`06da4c4` (branch `main`, tag `v0.1.0` → `1d83c24`, 139 unit tests, CI green
on Windows/Linux/macOS × Python 3.11–3.15, PyPI publication via Trusted
Publishing verified).

The roadmap is a plan, not a promise. Versions are sequenced by dependency
and value, not by calendar. No dates or deadlines are attached to any
milestone.

Companion documents:

- [`VERSIONING.md`](VERSIONING.md) — how version numbers are chosen.
- [`RELEASING.md`](RELEASING.md) — how a release is produced and verified.
- [`CHANGELOG.md`](CHANGELOG.md) — what actually shipped.

---

## 1. Product direction

PyPath Inspector is a **local-first, offline, strictly read-only diagnostic
CLI** for Python environments. It answers "which Python actually runs, and
why do my tools disagree?" — and it does nothing else.

Non-negotiable identity constraints (violating any of these is an
architectural decision requiring its own document, never a roadmap line
item):

- No telemetry, no automatic network communication, no cloud dependency.
- No automatic repair; no installation, uninstallation or updating of
  anything by the application itself.
- No modification of `PATH` or environment variables.
- No exposure of environment variable values; home-directory redaction in
  exported reports by default.
- No runtime dependencies beyond the Python standard library.
- Windows, Linux and macOS support.
- Stable exit codes and machine-readable reports suitable for automation.

Every roadmap item below was checked against these constraints. Anything
that conflicted with them was rejected or deferred (see §6).

## 2. Current state (verified against `06da4c4`)

**Fully implemented and tested:**

- Interpreter discovery: PATH scan (`python`/`python3`/`pythonw`, POSIX
  versioned names), `py -0p`, `uv python list --only-installed`, symlink and
  case-variant deduplication, per-interpreter probing with timeouts and
  `--version` fallback.
- Command resolution for `python`, `python3`, `pythonw`, `pip`, `pip3`,
  `py`, `uv`, with PATHEXT ordering, shadowing, duplicate/empty/nonexistent
  PATH entry analysis, script-shim detection.
- Microsoft Store alias stub detection (message- and path-based).
- Pip analysis: `pip`/`pip3`/`python -m pip` comparison, interpreter
  mismatch detection with flavour-aware (`ntpath`/`posixpath`) containment
  checks that are host-independent.
- Virtual environment analysis: venv detection, `pyvenv.cfg` check, stale
  `VIRTUAL_ENV`, conda presence note.
- 22 finding codes with INFO/WARNING/ERROR severities, evidence,
  explanation and non-destructive remediation.
- Terminal, JSON and Markdown reporting; default home-directory redaction
  for exported formats; stable exit codes 0–4.
- 139 machine-independent unit tests (fake subprocess runners, temp
  directories); CI matrix Windows/Linux/macOS × Python 3.11–3.15 (15/15
  green on the release commit); Trusted Publishing workflow with SHA-256
  asset verification.

**Partially supported / known limitations (from README and release audits):**

- Windows Python Install Manager ("pymanager") output is parsed via a
  tolerant fallback, verified only against synthetic fixtures — never
  against the real tool.
- Conda awareness is a `CONDA_PREFIX` presence check only.
- `pythonw` executables are never executed; version inferred from siblings.
- Quoted PATH entries are dead for resolution (matching Windows) but get no
  dedicated finding.
- pip mismatch detection is heuristic (versions + install-path containment).
- No PEP 514 registry discovery; interpreters registered there but absent
  from PATH/py/uv are invisible.
- Terminal output redirected to a file keeps full paths (documented).

**Structural observations (maintenance risk):**

- Version string lives in two places (`pyproject.toml` and
  `src/pypath_inspector/__init__.py`) with no automated consistency check.
- The JSON report has no schema version; automation consumers have no
  formal contract to code against.
- Finding codes are documented in a README table but have no registry
  document or stability policy.
- Release assets (wheel, sdist, `SHA256SUMS.txt`) are produced manually;
  the publish workflow verifies them but nothing generates them.
- `diagnostics.py` concentrates finding construction; it will need
  splitting by the time finding categories grow (deferred until 0.5.0).

## 3. Version sequence overview

| Version | Type | Title | Effort |
|---------|------|-------|--------|
| 0.1.0 | released | Initial public release | — |
| 0.1.1 | PATCH | Release hygiene and documentation accuracy | S |
| 0.2.0 | MINOR | Interpreter discovery expansion (PEP 514, pymanager) | M |
| 0.3.0 | MINOR | Environment manager awareness | M |
| 0.4.0 | MINOR | Installation and executable consistency | M |
| 0.5.0 | MINOR | Structured reporting contract (JSON schema) | M |
| 0.6.0 | MINOR | Selective diagnostics and severity filtering | S–M |
| 0.7.0 | MINOR | Report comparison (`pypath diff`) | M |
| 0.8.0 | MINOR* | Feature freeze, hardening, contract finalization | M |
| 1.0.0 | MAJOR | Stable public release | S |

\* Conditional on the justification gate defined in the 0.8.0 milestone:
it ships as 0.8.0 **only if** the hardening produces a substantial,
externally verifiable compatibility or reliability improvement; otherwise
the completed work becomes mandatory 1.0.0 readiness work and no 0.8.0 is
released (see `VERSIONING.md` §4).

Deviations from the original working hypothesis, all resolved by maintainer
review (recorded here so the sequence stays auditable):

- **Support bundle (hypothesized at 0.8.0): deferred beyond 1.0.0** —
  maintainer-approved; the additional privacy and security review it
  requires is not justified by its diagnostic value (see §6).
- **`pypath explain` (originally in 0.8.0): rejected.** Every diagnostic
  report already prints each finding's title, evidence, explanation and
  remediation (verified in all three formats), so an explain command would
  duplicate a second explanatory corpus with a permanent synchronization
  cost. The finding-code registry document (0.5.0) is the canonical
  offline reference. See §6.
- **`--min-severity` moved from 0.8.0 to 0.6.0** — maintainer-approved; it
  belongs with selective diagnostics (one coherent "control what runs and
  what you see" milestone) instead of artificially expanding 0.8.0.
- **The former 0.8.0 (explainability) and 0.9.0 (freeze) milestones are
  merged into a single 0.8.0 — maintainer-approved.** Reasoning: with the
  support bundle deferred and `pypath explain` rejected, no coherent
  feature scope remained for the old 0.8.0, and the remaining
  stabilization, compatibility-validation and release-readiness work
  belongs together; keeping two milestones would have meant inventing
  work to justify a release. Merging avoids both an empty release and a
  skipped number; neither version had been published, and amending the
  roadmap before release is the sanctioned mechanism (`VERSIONING.md`
  §4). The merged milestone's MINOR classification is itself conditional
  — see its justification gate.

---

## 4. Release-by-release scope

### 0.1.0 — Initial Public Release (already released, 2026-10-31)

Tag `v0.1.0` → commit `1d83c24`, published on PyPI via Trusted Publishing,
139 unit tests, CI 15/15. Content is recorded in
[`CHANGELOG.md`](CHANGELOG.md). No further action; listed only as the
baseline.

---

### 0.1.1 — Release Hygiene and Documentation Accuracy (PATCH)

- **Type:** PATCH.
- **Objective:** make everything that is already true *verifiably* true:
  accurate docs, one version source, automated release checks.
- **User problem solved:** the README currently tells users the package is
  "not yet published on PyPI" and gives only source-install instructions —
  actively misleading for a package that is on PyPI. Release tooling has
  manual, unrecorded steps.
- **Scope:**
  1. README corrections: remove the "not yet published" claim; make
     `pip install pypath-inspector` the primary instruction; keep pipx /
     `uv tool install` / source-install variants; re-check every factual
     claim (test counts, finding table, limitations).
  2. Single source of truth for the version: switch `pyproject.toml` to
     `dynamic = ["version"]` with
     `[tool.setuptools.dynamic] version = {attr = "pypath_inspector.__version__"}`
     so `__init__.py` becomes the only version constant. (Recommendation
     detailed in `VERSIONING.md` §6.)
  3. Automated version-consistency gate: a unit test asserting the
     installed distribution metadata version equals
     `pypath_inspector.__version__`, plus a release-check step comparing
     the git tag with the built wheel's METADATA version.
  4. Publish-workflow pre-release fix (release engineering only; verified
     defect): the current tag validation **rejects canonical PEP 440
     pre-release tags** (`v0.2.0a1`, `v1.0.0rc1`, …) because its optional
     suffix group requires a leading `.` or `-`, and separator-form tags
     (`v0.2.0.a1`) fail asset-name checks because setuptools normalizes
     the version in filenames (`0.2.0.a1` → `0.2.0a1`) — so **no
     pre-release can be published today**. Fix: accept canonical PEP 440
     tags, derive expected asset names from the normalized version, and
     cross-check the wheel's internal METADATA version against the tag
     (also closing the regex's permissiveness toward malformed suffixes
     such as `v0.2.0..`).
  5. A small, documented asset-build script (e.g.
     `scripts/make-release-assets.py`) that builds wheel + sdist and emits
     `SHA256SUMS.txt` in the exact format `publish.yml` verifies.
  6. Any genuine bug fixes that accumulate before the release (none known
     at planning time).
- **Non-goals:** any new diagnostic capability, discovery source, CLI flag
  or finding code; refactoring beyond the version-source change.
- **Dependencies:** none (first release after 0.1.0).
- **Architectural impact:** none at runtime; build metadata derivation
  changes only.
- **Public API impact:** none.
- **Privacy / read-only implications:** none.
- **Required tests:** version-consistency test; existing 139 tests stay
  green; asset script tested on Windows and Linux CI.
- **Cross-platform validation:** full CI matrix.
- **Documentation changes:** README (above); RELEASING.md updated to
  reference the asset script.
- **Acceptance criteria:** README contains no false statements; exactly one
  version constant exists; the consistency gate fails demonstrably when
  versions disagree (test provokes it); CI green.
- **Definition of done:** all PATCH gates in `RELEASING.md` pass; release
  published and verified on PyPI.
- **Risks / unresolved decisions:** none material. The dynamic-version
  change is the only build-config risk; it is covered by the consistency
  gate.
- **Why 0.1.1:** every item is a backward-compatible correction of
  inaccurate documentation or release-pipeline weakness — the exact
  definition of PATCH. No new user-facing functionality.

---

### 0.2.0 — Interpreter Discovery Expansion (MINOR)

- **Type:** MINOR.
- **Objective:** substantially expand which Pythons can be *found* on
  Windows, and make discovery claims honest about coverage.
- **User problem solved:** interpreters registered with the PEP 514
  registry but not on PATH (and not known to py/uv) are invisible today;
  users get "not found" style confusion for Pythons that are genuinely
  installed. The modern Python Install Manager is parsed via an unverified
  fallback.
- **Scope:**
  1. PEP 514 registry discovery on Windows (stdlib `winreg`, read-only):
     enumerate `HKCU\Software\Python\PythonCore` and
     `HKLM\...` (both 64-bit and 32-bit views), extract
     `InstallPath`, `SysVersion`, `DisplayName`.
  2. Verified Python Install Manager compatibility: capture real
     `pymanager` output formats, add structured parsers and fixture tests;
     keep the generic path-extraction fallback.
  3. New INFO finding for registry-known interpreters that are not
     reachable through PATH (e.g. `MANAGED_BUT_NOT_ON_PATH`), turning
     silent invisibility into an actionable observation.
  4. Discovery coverage statement in reports: the report already lists
     sources per interpreter; formalize a short "discovered via PATH,
     py-launcher, uv, PEP 514 registry" coverage line so completeness
     claims stay falsifiable.
- **Non-goals:** executing registry-discovered interpreters beyond the
  existing probe (probe only the resolved `python.exe` paths, same as
  today); Linux/macOS discovery changes; modifying the registry (read-only
  guaranteed).
- **Dependencies:** 0.1.1 (version gate and asset tooling not strictly
  required, but release hygiene should land first).
- **Architectural impact:** `discovery.py` gains a Windows-only source
  behind the existing `DiscoveryResult` accumulator; no model changes
  beyond a new source label `"pep514-registry"`.
- **Public API impact:** new finding code(s); new discovery source label in
  JSON (additive).
- **Privacy / read-only implications:** registry reads are local and
  read-only; no values beyond install paths and display names are read;
  redaction applies to paths as usual.
- **Required tests:** fixture-based registry parsing (canned `winreg`
  doubles — no live registry in unit tests); finding construction for
  off-PATH registry interpreters; pymanager fixture tests; existing suite
  green.
- **Cross-platform validation:** registry code must be inert on POSIX
  (import-guarded, exercised only on Windows CI); pymanager parsing tested
  on all OSes.
- **Documentation changes:** README discovery section; finding-code table
  (and, from this release on, the registry document that 0.5.0 will
  formalize can begin as a section).
- **Acceptance criteria:** on a machine with an off-PATH python.org install,
  `pypath doctor` reports it with its registry source; POSIX behaviour
  unchanged; all parsers have fixture tests.
- **Definition of done:** all MINOR gates pass; release notes describe the
  new discovery coverage.
- **Risks / unresolved decisions:** PEP 514 has loosely validated
  third-party data (store interpreters, odd `SysVersion` values) — parsing
  must be defensive; pymanager output format may still be moving — the
  fallback plus fixtures mitigates. Decision needed at implementation time:
  whether freethreaded (`3.15t`) registry entries get distinct interpreter
  entries (they resolve to distinct executables, so: yes).
- **Why 0.2.0:** a substantial expansion of supported discovery behaviour —
  the canonical MINOR trigger. Nothing here is a bug fix.

---

### 0.3.0 — Environment Manager Awareness (MINOR)

- **Type:** MINOR.
- **Objective:** understand *who manages* each interpreter and whether the
  active shell state matches it.
- **User problem solved:** users with pyenv, conda or uv-managed
  environments cannot tell from a `pypath doctor` report which installation
  belongs to which manager, or whether the activated state is consistent
  (e.g. pyenv shims vs `PYENV_VERSION`).
- **Scope:**
  1. Manager attribution: label interpreters discovered under known manager
     roots — pyenv (`PYENV_ROOT` or `~/.pyenv/versions`, presence-only env
     reads), conda (`CONDA_PREFIX`/known envs roots), uv (already labelled
     via `uv` source; extend to uv-managed venvs), python.org defaults,
     Microsoft Store.
  2. Shell-state consistency checks (presence-only, values never reported):
     `PYENV_VERSION` set but shim resolution disagrees; `CONDA_PREFIX` set
     while `python` resolves outside any conda root; uv-managed venv active
     without its Scripts/bin directory on PATH.
  3. New findings for the above (severity WARNING for inconsistent
     activation state, INFO for attribution-only observations).
- **Non-goals:** modifying or creating environments; parsing manager config
  files beyond what is needed for attribution; network lookups.
- **Dependencies:** 0.2.0 (attribution builds on the expanded interpreter
  list).
- **Architectural impact:** small; a manager-attribution step between
  discovery and finding construction, feeding `Interpreter.sources`.
- **Public API impact:** new finding codes; enriched `sources` labels
  (additive).
- **Privacy / read-only implications:** home-relative roots are reported as
  paths (redacted in exports by default, as today); env vars checked for
  presence/consistency only.
- **Required tests:** attribution with temp-dir "manager roots"; presence
  checks with injected environments; no unit test may depend on real
  manager installations.
- **Cross-platform validation:** pyenv and conda paths differ per OS;
  fixtures for both layouts; Windows conda layouts included.
- **Documentation changes:** README manager-awareness section; finding
  codes.
- **Acceptance criteria:** a report on a machine with pyenv+conda
  attributes each interpreter to its manager and flags inconsistent
  activation state; machines without managers produce byte-identical
  reports to 0.2.0 (minus version fields).
- **Definition of done:** MINOR gates pass.
- **Risks / unresolved decisions:** manager root layouts are conventions,
  not specifications — detection must be heuristic and tolerant; decision:
  treat unknown `~/.pyenv` layouts as absent rather than guessing.
- **Why 0.3.0:** a meaningful expansion of diagnostic behaviour (manager
  attribution and activation consistency), cohesive and independently
  testable — MINOR, and it must follow discovery expansion.

---

### 0.4.0 — Installation and Executable Consistency (MINOR)

- **Type:** MINOR.
- **Objective:** diagnose the *tooling layer* on top of interpreters: entry
  points on PATH, tool installations, shim health.
- **User problem solved:** "I installed a package but the command isn't
  found" and "this shim points at a Python I deleted" — today only pip and
  basic script shims are analysed.
- **Scope:**
  1. Scripts/bin directory diagnostics for the active interpreter: is the
     directory that should carry `pip.exe`/entry points actually on PATH,
     and in which position relative to competing ones?
  2. pipx and uv tool awareness (read-only): list tool environments
     (`pipx list --json`, `uv tool list`), report which interpreter each
     tool environment uses, flag tool environments whose base interpreter
     is missing.
  3. Text-shim target analysis: for `.bat`/`.cmd`/`.sh` shims resolved for
     core commands, read the target line and verify the referenced
     executable exists (extends the existing SCRIPT_SHIM_RESOLUTION
     finding with concrete evidence).
  4. Broken-shortcut evidence: extend probe-failure findings to cite the
     missing target when detectable.
- **Non-goals:** installing/repairing tools or shims; binary `.exe`
     trampoline parsing (Windows shim internals are out of scope);
     scanning arbitrary directories for orphans.
- **Dependencies:** 0.3.0 (manager attribution identifies tool env roots).
- **Architectural impact:** new analysis module alongside `pipcheck.py`
  (e.g. `toolcheck.py`), same finding-construction pattern.
- **Public API impact:** new finding codes; new report section (additive).
- **Privacy / read-only implications:** subprocess calls remain read-only
  version/list queries with timeouts; no tool state is modified.
- **Required tests:** shim-target parser unit tests; pipx/uv list parsers
  against fixtures; findings for missing base interpreters.
- **Cross-platform validation:** `.bat` analysis is Windows CI; `.sh` shim
  analysis POSIX CI; pipx/uv fixtures run everywhere.
- **Documentation changes:** README section; finding codes.
- **Acceptance criteria:** a machine with a pipx tool whose base interpreter
  was removed gets a WARNING naming the tool and the missing interpreter;
  Scripts-dir position analysis explains shadowed `pip` precisely.
- **Definition of done:** MINOR gates pass.
- **Risks / unresolved decisions:** pipx/uv CLI output formats evolve;
  parsers must be fixture-driven. Decision: cap subprocess probes to a
  fixed budget per run to keep `doctor` fast.
- **Why 0.4.0:** a new, cohesive diagnostic capability (installation and
  tool consistency) beyond bug fixing — MINOR. Deferred after managers
  because attribution makes tool-environment analysis far more precise.

---

### 0.5.0 — Structured Reporting Contract (MINOR)

- **Type:** MINOR.
- **Objective:** give automation consumers a formal, versioned contract.
- **User problem solved:** anyone scripting against the JSON report today
  codes against an undocumented shape; report consumers cannot detect
  breaking changes.
- **Scope:**
  1. `schema_version` field in the JSON report.
  2. A published JSON Schema (`docs/schema/report.schema.json`, JSON
     Schema draft 2020-12) describing the report of this version.
  3. CI validation: golden report fixtures validated against the schema in
     every matrix leg.
  4. Finding-code registry: `docs/finding-codes.md` listing every code,
     severity, meaning and stability policy (codes are additive-only;
     removal or renumbering requires a major version).
  5. Markdown contract statement: heading structure and section order are
     stable; prose may evolve.
  6. If needed for maintainability, split finding construction in
     `diagnostics.py` into per-category modules behind the same public
     behaviour (internal only; covered by unchanged golden outputs).
- **Non-goals:** changing existing JSON field names or semantics (this
  release *documents* the current shape, then versions it); a plugin or
  extension system.
- **Dependencies:** 0.2.0–0.4.0 findings must be included so the first
  schema covers the near-final surface.
- **Architectural impact:** reporting layer gains schema-awareness
  (`schema_version` emission); tests gain schema validation.
- **Public API impact:** the JSON report becomes a documented, versioned
  interface — the most significant pre-1.0 commitment. Additive only.
- **Privacy / read-only implications:** schema must mark fields that carry
  paths as redaction-subject; canary tests keep proving env values never
  appear.
- **Required tests:** schema validation of golden fixtures; canary
  redaction tests; round-trip tests per format.
- **Cross-platform validation:** golden fixtures generated on all three OS
  families (path shapes differ); schema validation everywhere.
- **Documentation changes:** schema doc, finding-code registry, README
  automation section.
- **Acceptance criteria:** a third party can consume the JSON report using
  only the published schema; CI fails if report and schema drift apart.
- **Definition of done:** MINOR gates pass, including schema validation in
  CI.
- **Risks / unresolved decisions:** freezing the schema too early.
  Mitigation: `schema_version` starts at 1 with additive-only evolution
  until 1.0.0; any non-additive change before 1.0.0 requires a documented
  pre-1.0 break note per `VERSIONING.md` §3.
- **Why 0.5.0:** a meaningful expansion of report functionality and the
  formalization of a public contract — MINOR. It must precede comparison
  (0.7.0), which consumes the contract.

---

### 0.6.0 — Selective Diagnostics and Severity Filtering (MINOR)

- **Type:** MINOR.
- **Objective:** let users control which diagnostics run and which findings
  are displayed.
- **User problem solved:** full `doctor` probes every discovered
  interpreter and manager; CI scripts and quick checks want a subset (e.g.
  PATH analysis only) to run fast and exit predictably, and humans reading
  noisy machines want to hide INFO-level noise without losing exit-code
  fidelity.
- **Scope:**
  1. `pypath doctor --only <category>[,<category>]` and
     `--skip <category>` using the fixed category vocabulary below
     (maintainer-approved).
  2. `pypath doctor --min-severity <info|warning|error>` — a
     **display-only** filter: exit codes continue to reflect *all*
     findings of the executed selection, documented explicitly.
  3. Report headers state the executed selection and display filter (all
     formats).
  4. Exit-code semantics for selections: exit codes reflect the findings
     of the executed selection.
- **Category vocabulary and boundaries (each check belongs to exactly one
  category; new findings are assigned at design time using these rules):**

  | Category | Owns | Boundary rule |
  |---|---|---|
  | `discovery` | Which Pythons exist: PATH interpreter scan, `py`/`uv`/registry inventory queries, probing, deduplication, manager attribution of interpreters. Findings: `MULTIPLE_PYTHON_INSTALLATIONS`, `PYTHON_NOT_FOUND`, `UV_MANAGED_PYTHONS`, `MANAGER_LISTS_MISSING_INTERPRETER`, `MANAGER_QUERY_FAILED`. | Manager queries used to *inventory interpreters* are discovery; manager *tool-environment* analysis is `tools`. |
  | `path` | The PATH variable's structure only: entry list, duplicates, empty entries, nonexistent directories. Findings: `PATH_MISSING`, `PATH_DUPLICATE_ENTRIES`, `PATH_EMPTY_ENTRY`, `PATH_NONEXISTENT_ENTRIES`. | Structure only — looking up a command inside those entries is `resolution`. |
  | `resolution` | Command-name → executable mapping: precedence, shadowing, PATHEXT, script shims, Store alias stubs, probe failures of resolved commands. Findings: `COMMAND_SHADOWED`, `SCRIPT_SHIM_RESOLUTION`, `WINDOWS_STORE_ALIAS_STUB`, `PYTHON_PROBE_FAILED`. | Owns the *winning executable* of each command name; interpreter inventory is `discovery`. |
  | `pip` | pip ↔ interpreter consistency: `pip`/`pip3`/`python -m pip` comparison and mismatches. Findings: `PIP_NOT_ON_PATH`, `PIP_MODULE_MISSING`, `PIP_INTERPRETER_MISMATCH`, `PIP_VERSION_DISAGREEMENT`. | pip only; other tools' entry points are `tools`. |
  | `venv` | Virtual environment and activation state: venv detection, `pyvenv.cfg`, stale `VIRTUAL_ENV`, conda activation. Findings: `VENV_ACTIVE`, `VENV_MISSING_CONFIG`, `VENV_STALE_ENV_VAR`, `CONDA_ENV_ACTIVE`. | Activation-state consistency even for conda; conda *inventory* attribution is `discovery`. |
  | `tools` | Environment and tool managers as tool layers: pipx/uv tool environments, Scripts/bin entry-point directory diagnostics, broken tool environments (from 0.4.0). | Everything that analyses *tool installations* rather than interpreters or the PATH variable itself. |

  Cross-cutting findings that can originate from several checks (e.g.
  `PROBE_TIMEOUT`) are attributed to the category of the check that
  triggered the probe.
- **Non-goals:** custom user-defined checks; changing default behaviour
  (no flags = full run, display unfiltered, identical to 0.5.0); hiding
  findings from machine-readable output (`--min-severity` applies to
  display formats only, never to exit codes).
- **Dependencies:** 0.5.0 (categories must map cleanly onto the documented
  report structure).
- **Architectural impact:** `run_diagnostics` gains category filtering
  before finding construction; per-category modules from 0.5.0 make this
  mechanical.
- **Public API impact:** new CLI flags, the closed category vocabulary and
  their documented semantics (additive).
- **Privacy / read-only implications:** none beyond existing.
- **Required tests:** category filtering unit tests; exit-code semantics
  per selection; `--min-severity` display-only behaviour (filtered run
  still exits non-zero for hidden findings); full-run equivalence test (no
  flags == previous behaviour); invalid category or severity → exit 3.
- **Cross-platform validation:** full matrix; timing assertion that
  `--only path` completes without interpreter subprocess probes.
- **Documentation changes:** README usage; category vocabulary table;
  RELEASING notes exit-code semantics.
- **Acceptance criteria:** `pypath doctor --only path` performs zero
  interpreter subprocess probes; `--only discovery,path` and
  `--skip resolution,pip,venv,tools` produce identical reports (equivalent
  complements); `--min-severity warning`
  on a report with hidden INFO findings still exits as if they were
  displayed; every existing finding code maps to exactly one category
  (asserted by a unit test).
- **Definition of done:** MINOR gates pass.
- **Risks / unresolved decisions:** category naming is now fixed
  (maintainer-approved); additions are MINOR, renames are breaking.
- **Why 0.6.0:** a new documented CLI capability — MINOR. Placed after the
  schema so selection semantics are contract-adjacent, and before diff so
  partial reports are available to compare. `--min-severity` belongs here
  by the same theme (controlling what runs and what is shown).

---

### 0.7.0 — Report Comparison (`pypath diff`) (MINOR)

- **Type:** MINOR.
- **Objective:** stateless comparison of two report files.
- **User problem solved:** "what changed between my environment last week
  and now?" — the recurring question behind environment drift.
- **Scope:**
  1. `pypath diff <old.json> <new.json>` — compares two JSON reports
     produced by any compatible `pypath` version (schema-aware; rejects
     incompatible schema versions with a clear message).
  2. Deltas reported: findings added/removed/severity-changed, interpreters
     added/removed, command resolution changes, PATH entry changes.
  3. Output formats: terminal and JSON (markdown optional); strict
     read-only handling of user-supplied files; no state is stored by
     pypath anywhere.
  4. Exit codes for `diff` (maintainer-approved, command-specific):
     `0` comparison completed, no differences; `1` comparison completed,
     differences found; `3` invalid usage or invalid input; `4` internal
     failure. **`2` is never returned by `diff`.** These semantics are
     deliberately distinct from `doctor`'s severity-based codes (where `1`
     = warnings and `2` = errors): the distinction must be documented in
     `--help` output and enforced by tests (see acceptance criteria).
- **Non-goals:** background monitoring, scheduling, or storing reports
  automatically (violates the read-only, stateless identity); drift
  "repair".
- **Dependencies:** 0.5.0 schema (mandatory); benefits from 0.6.0
  selections but does not require them.
- **Architectural impact:** new `diff` command reusing reporting layer;
  comparison logic in its own module.
- **Public API impact:** new subcommand, new flag surface, new exit-code
  contract for that subcommand (additive; documented).
- **Privacy / read-only implications:** input files are user-supplied;
  diff output inherits their redaction state; pypath itself never writes
  them.
- **Required tests:** fixture-pair comparison tests (added/removed/changed
  findings); schema-mismatch rejection; exit codes; **an explicit
  distinction test asserting that `doctor` may return `2` while `diff`
  never does, and that `diff`'s `1` (differences found) is independent of
  `doctor`'s `1` (warnings present)**.
- **Cross-platform validation:** fixtures with Windows- and POSIX-style
  paths; matrix run.
- **Documentation changes:** README usage (including a side-by-side exit
  code table for `doctor` vs `diff`); schema doc for the diff output
  shape.
- **Acceptance criteria:** comparing a report against itself yields exit 0
  and "no changes"; hand-crafted fixture pairs produce the exact documented
  deltas; the exit-code distinction test passes; `pypath diff` with a
  missing file or an incompatible schema exits `3` with a clear message.
- **Definition of done:** MINOR gates pass.
- **Risks / unresolved decisions:** none blocking. Decision recorded:
  diff never interprets severity ordering beyond added/removed/changed.
- **Why 0.7.0:** a new user-facing capability with a coherent purpose —
  MINOR. It depends on the reporting contract, hence its position.

---

### 0.8.0 — Feature Freeze, Hardening, Contract Finalization (MINOR)

- **Type:** MINOR.
- **Objective:** no new capabilities; make everything that exists provably
  stable and formally document the contract that 1.0.0 will declare
  stable. (Merges the originally separate explainability and freeze
  milestones — see §3.)
- **User problem solved:** users need confidence that behaviour will not
  shift under them as 1.0.0 approaches, and a single place that states
  exactly what is being promised.
- **Scope:**
  1. Compatibility and regression infrastructure: golden report snapshots
     per OS family; compatibility tests pinning CLI surface, exit-code
     semantics (including the `doctor` vs `diff` distinction), and JSON
     shape; probe-budget performance assertions.
  2. Documentation completion: the public contract section (§5 below)
     reviewed end to end; every documented claim re-verified against the
     implementation (the discipline used for this roadmap, applied
     mechanically); README exit-code table covering both commands;
     category vocabulary documented as part of the contract.
  3. Dependency and platform review: confirm supported Python versions
     (drop EOL, add newly released); confirm OS matrix.
  4. Bug-fix-only window: any defect found during hardening is fixed here.
  5. Optional `1.0.0rc1`: cut **only if** meaningful external validation of
     the contract freeze is needed (maintainer decision at that time; no
     other pre-releases are planned for this milestone).
- **Non-goals:** features of any kind — anything proposed here is either
  rejected or deferred post-1.0.
- **Dependencies:** all previous milestones (0.1.1–0.7.0) complete.
- **Architectural impact:** test infrastructure only.
- **Public API impact:** none beyond documentation of the final contract.
- **Privacy / read-only implications:** canary and redaction tests extended
  to every command, including `diff`.
- **Required tests:** the new compatibility suite; full suite green.
- **Cross-platform validation:** exhaustive matrix, including any newly
  supported Python versions.
- **Documentation changes:** contract finalized (README + docs).
- **Acceptance criteria (this milestone is not an arbitrary number — it is
  the release-readiness gate):** every item of the 1.0.0 readiness
  checklist (§5) is demonstrably green; the compatibility suite runs in CI
  on all three OS families; a documentation-claim audit (documented
  procedure, executed and recorded) finds zero false statements.
- **Release-justification gate (maintainer-directed):** the completed work
  ships as `0.8.0` **only if** it constitutes a substantial, externally
  verifiable improvement in supported-platform compatibility or
  reliability — concretely, a CI-enforced compatibility suite validating
  the public contract (CLI surface, `doctor`/`diff` exit codes, JSON
  shape) on every supported OS and Python combination, plus, where
  applicable, newly supported platform versions or fixes for defects that
  demonstrably affected cross-platform behaviour. **If the completed work
  amounts to internal test infrastructure and documentation only, the
  MINOR criteria (`VERSIONING.md` §3) are not met: no 0.8.0 is released,
  the work is folded into 1.0.0 as mandatory readiness work, the sequence
  ends `0.7.0 → 1.0.0`, and the absorption is recorded here as the
  documented reason.** No user-facing functionality may be invented to
  force the number.
- **Definition of done:** MINOR gates pass; release notes declare the
  freeze. (If the gate is not met: the readiness checklist is green and
  the absorption is recorded — that is the definition of done for the
  no-release path.)
- **Risks / unresolved decisions:** late bug discoveries could delay 1.0.0 —
  acceptable; the freeze must not be rushed.
- **Why 0.8.0:** if the justification gate is met, the release delivers a
  substantial, externally verifiable compatibility and reliability
  improvement — the fifth MINOR criterion in `VERSIONING.md` §3 — while
  adding no features; it is also the designated place for any
  unavoidable, documented pre-1.0 breaking adjustment with migration
  notes, should one prove necessary. If the gate is not met, no version is
  forced: the work belongs to 1.0.0.

---

### 1.0.0 — Stable Public Release (MAJOR)

- **Type:** MAJOR.
- **Objective:** declare the public contract stable.
- **User problem solved:** users and automation authors need a version
  they can depend on long-term.
- **Scope:** the 1.0.0 release contains no new functionality beyond what
  the freeze milestone froze — 0.8.0 if its justification gate was met,
  otherwise the frozen state of `main` carrying the same hardening work as
  1.0.0 readiness. It is the declaration, executed with the strictest
  release gates: full verification checklist, independently verified PyPI
  artifacts, complete documentation set (README, ROADMAP, VERSIONING,
  RELEASING, CHANGELOG, finding-code registry, JSON schema).
- **Public contract:** see §5.
- **Definition of done:** every gate in `RELEASING.md` marked mandatory for
  1.0.0 passes; published artifacts verified by SHA-256 from a clean
  machine; release notes summarize the journey from 0.1.0.
- **Why a MAJOR number:** reaching the first stable public API commitment
  is precisely what SemVer reserves `1.0.0` for. After this point, any
  backward-incompatible change to the public contract requires a new major
  version and migration guidance.

---

## 5. The 1.0.0 public contract (definition)

**Public — users and automation may rely on these; changes are governed by
SemVer from 1.0.0 onward:**

- The `pypath` command and `python -m pypath_inspector`.
- Subcommands and their arguments: `doctor` (0.1.0) and `diff` (0.7.0);
  every flag documented in README at release time.
- Exit codes, which are **command-specific and must never be conflated**:
  `doctor` — `0` clean, `1` warnings, `2` errors, `3` usage, `4` internal
  (severity-based); `diff` — `0` no differences, `1` differences found,
  `3` invalid usage or input, `4` internal (`2` is never returned by
  `diff`). The distinction is part of the contract and enforced by
  compatibility tests from 0.8.0.
- Finding codes: the registry in `docs/finding-codes.md`; additive-only
  evolution; removal or semantic change requires a major release.
- JSON report structure with `schema_version`, validated by the published
  JSON Schema.
- Markdown report: heading structure and section order; prose may evolve
  within sections.
- Redaction defaults: JSON and Markdown outputs and anything written via
  `--output` redact the home directory unless `--no-redact` is passed;
  terminal output shows full paths.
- Supported platforms: Windows 10/11, mainstream Linux, macOS; Python
  runtimes per the support policy documented at release (3.11+ at planning
  time; EOL versions dropped only at minor releases).
- Read-only, offline, no-runtime-dependency guarantees.

**Internal — may change without a major version:**

- All Python modules under `src/pypath_inspector/` including their
  dataclasses and function signatures. **Importing `pypath_inspector` as a
  library is not a supported API at 1.0.0.** Consumers should use the CLI
  and the JSON report. A stable library API, if ever provided, is a
  post-1.0 architectural decision with its own compatibility costs
  (rejected for 1.0.0 — see §6).
- Report generation internals, probe strategies, parser heuristics, test
  fakes.

**1.0.0 readiness conditions (all must hold):**

1. Every milestone 0.1.1–0.7.0 released with its acceptance criteria met,
   and the 0.8.0 hardening work completed — either as a released 0.8.0
   (justification gate met) or as absorbed 1.0.0 readiness work (gate not
   met, absorption documented).
2. Zero known ERROR-severity defects; zero open privacy or read-only
   violations.
3. JSON schema published and CI-enforced for at least one full minor
   release (0.5.0 or later).
4. Finding-code registry complete; every code covered by tests and
   documented in the registry.
5. Full CI matrix green including the newest supported Python.
6. Documentation claims re-verified against implementation (freeze-
   milestone gate — performed within 0.8.0 if released, otherwise as part
   of the absorbed 1.0.0 readiness work).
7. Privacy canary tests proving: no env-var values in any output, default
   redaction in all export paths.

## 6. Deferred and rejected features

| Proposal | Decision | Reason |
|---|---|---|
| Privacy-safe support bundle (was hypothesized at 0.8.0) | **Deferred post-1.0.0** (maintainer-approved) | Redacted JSON/Markdown reports already cover sharing; a bundle multiplies the privacy and security review surface (system info, environment inventory) for little diagnostic value. Revisit when users demonstrably need single-file bundles; would be a MINOR with a dedicated privacy review. |
| `pypath explain <finding-code>` (was in the original 0.8.0) | **Rejected** (maintainer-directed evaluation) | Every diagnostic report already prints each finding's title, evidence, explanation and remediation in all three formats (verified), so an explain command duplicates a second explanatory corpus with a permanent synchronization cost. The 0.5.0 finding-code registry document is the canonical offline reference. |
| Stable Python library API | **Rejected for 1.0.0** | Would freeze internal dataclasses and modules that are still evolving; CLI + versioned JSON already serve automation. |
| Automatic repair (`pypath fix`) | **Rejected** | Directly violates the read-only identity. |
| GUI / TUI | **Rejected** | Identity: a scriptable, terminal-first diagnostic tool. |
| Background monitoring / report storage | **Rejected** | Statelessness is part of the read-only, local-first guarantee. |
| Network version checks / update hints | **Rejected** | Offline guarantee. |
| Colored terminal output | Deferred, low value | Cosmetic; risks complicating redirect semantics. |
| Localization (non-English reports) | Deferred post-1.0.0 | Significant content surface; no demonstrated demand yet. |
| Python 2.x interpreter support beyond `--version` probing | Rejected | Out of scope; probe fallback already records the version honestly. |

## 7. Maintenance between milestones

Bug fixes, dependency-free hardening, documentation corrections and test
improvements land on `main` continuously and ship in the next justified
release (PATCH or the next milestone) per `VERSIONING.md`. There are no
calendar releases: a version ships when its scope is complete and its
acceptance criteria are met, and never to "fill" the sequence.
