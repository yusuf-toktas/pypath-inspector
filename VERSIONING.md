# PyPath Inspector — Versioning Policy

This document defines how version numbers are chosen for PyPath Inspector.
It is normative for every release, including pre-releases, and is referenced
by [`RELEASING.md`](RELEASING.md) and [`ROADMAP.md`](ROADMAP.md).

## 1. Specifications

Two specifications apply **together**:

- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html) — the
  primary model for what a number change *means*.
- [PEP 440](https://packaging.python.org/en/latest/specifications/version-specifiers/)
  — the concrete version syntax used on PyPI and in Python tooling.

For released versions `X.Y.Z` the two are identical. Where they differ
(pre-release spellings), this project uses the **PEP 440 form** because
that is what pip, PyPI and the publish workflow consume: `0.2.0a1`,
`0.2.0b1`, `0.2.0rc1` (never the SemVer hyphen form `0.2.0-a1`).

## 2. MAJOR, MINOR, PATCH after 1.0.0

Once `1.0.0` is published, plain SemVer applies:

- **MAJOR** — any backward-incompatible change to the public contract
  (CLI commands/arguments/semantics, exit codes, finding-code removal or
  semantic change, non-additive JSON schema change, redaction default
  change). Requires migration guidance in the changelog.
- **MINOR** — new, backward-compatible capability (new command, flag,
  finding code, schema field, discovery source).
- **PATCH** — backward-compatible bug fixes, documentation corrections,
  packaging and release-pipeline corrections only.

The public contract itself is defined in
[`ROADMAP.md`](ROADMAP.md) §5. Anything not listed there is internal and
may change in any release.

## 3. Stricter pre-1.0.0 policy

SemVer treats `0.y.z` as "anything may change". PyPath Inspector voluntarily
adopts a **stricter** policy so that every number change has a reason users
can understand:

### PATCH (e.g. 0.1.0 → 0.1.1)

- Backward-compatible bug fixes only.
- Documentation corrections that fix inaccurate or misleading information.
- Packaging and release-pipeline corrections (including security and
  reliability fixes) that introduce **no new functionality**.
- **Never** a new user-facing feature.

### MINOR (e.g. 0.1.1 → 0.2.0)

One or more:

- A coherent, meaningful new user-facing capability.
- A substantial expansion of supported discovery or diagnostic behaviour.
- A new documented CLI capability.
- A meaningful expansion of report functionality.
- A substantial, **externally verifiable** improvement in
  supported-platform compatibility or reliability — for example, a
  compatibility suite enforced in CI across every supported OS and Python
  combination, newly supported platform versions, or fixes for defects
  that demonstrably affected cross-platform behaviour. The improvement
  must be real and observable from outside the project (users,
  automation, CI); internal test infrastructure, refactoring or
  documentation work alone does **not** satisfy this criterion, and
  ordinary bug fixes remain PATCH regardless of how many are bundled.

If a pre-1.0 change must break the public surface (avoid whenever
possible), it may only ride a MINOR release, must be explicitly documented
in the changelog with justification, and must include migration guidance.
This is the only sanctioned pre-1.0 escape hatch, and it exists because
SemVer's 0.y.z licence to break freely is deliberately not being taken.

### MAJOR before 1.0.0

Only `1.0.0` itself. No intermediate major versions exist in the plan.

## 4. Sequential progression rules

- Never choose versions arbitrarily; every published version must have a
  specific, completed scope (see [`ROADMAP.md`](ROADMAP.md)).
- `0.1.0 → 0.1.1`: a justified patch. `0.1.1 → 0.1.2`: another justified
  patch. `0.1.1 → 0.2.0`: a completed feature milestone.
- When MINOR increments, PATCH resets to zero.
- Do not skip a planned minor milestone without a documented reason
  (recorded in `ROADMAP.md`).
- Do not create empty releases to make the sequence look complete.
- Do not bump PATCH for a commit, a refactor, or the passage of time.
- Do not bump MINOR for a trivial bug fix.
- A release is cut only when its roadmap acceptance criteria are met; if a
  milestone's scope proves wrong, amend the roadmap document first.
- A planned milestone whose MINOR justification criteria are **not** met by
  the completed work is not forced into a release: the work is absorbed
  into the next justified release (or into 1.0.0 readiness work), and the
  reason is documented in `ROADMAP.md`. An unfulfilled planned number is
  not a "skipped release" — only published versions count.

## 5. Pre-release policy

PEP 440 pre-release identifiers (`a`, `b`, `rc`) are used **only when
genuinely justified by a need for external testing or compatibility
feedback that cannot be obtained any other way** (maintainer-approved
policy):

- **Default: no pre-release.** Most milestones — and every PATCH release —
  ship directly as their final version. Internal quality is ensured by the
  unit suite, the CI matrix and the release gates in `RELEASING.md`, none
  of which require a published pre-release.
- **`a` (alpha, e.g. `0.2.0a1`)** — exceptional: only when a change's
  correctness depends on real-world machine diversity that fixtures cannot
  reproduce (for example, third-party registry or manager output data),
  **and** a recorded justification exists for why internal testing is
  insufficient. Never issued routinely or "to be safe".
- **`b` (beta, e.g. `0.4.0b1`)** — exceptional: same bar as alpha,
  typically for new analysis that executes additional external commands on
  user machines.
- **`rc` (e.g. `1.0.0rc1`)** — only for `1.0.0`, and only if meaningful
  external validation of the contract freeze is needed before declaring
  the stable release. This is the only pre-release currently contemplated
  by the roadmap, and it remains conditional (`ROADMAP.md`, 0.8.0).

Rules:

- A pre-release requires a written justification (what external feedback
  is sought, why it cannot be obtained otherwise) recorded in the release
  notes; without one, the final version ships directly.
- Pre-releases are published to PyPI (so testers can `pip install
  --pre`), marked as pre-releases on GitHub, and never announced as
  stable.
- Pre-releases do not reset or consume the final version number;
  `0.2.0a1` precedes `0.2.0`.
- Tag format: `v` + PEP 440 version, e.g. `v1.0.0rc1`.

**Release-engineering defect (verified at `06da4c4`):** the publish
workflow **cannot currently publish any pre-release version**. Its tag
regex `^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$` requires the
optional suffix to begin with a `.` or `-` separator, so canonical PEP 440
pre-release tags (`v0.2.0a1`, `v0.2.0b1`, `v0.2.0rc1`, `v1.0.0rc1`) are
**rejected**. Separator-form tags (`v0.2.0.a1`) pass the regex, but
setuptools normalizes version `0.2.0.a1` to `0.2.0a1` in wheel and sdist
filenames, so the workflow's expected asset names never match the actual
builds (verified by building `0.2.0.a1`: output is
`pypath_inspector-0.2.0a1-py3-none-any.whl`). The same regex is also
permissive toward malformed suffixes such as `v0.2.0..`. Fixing both
sides — accept canonical PEP 440 tags and derive asset names from the
normalized version, plus cross-checking the wheel's METADATA version
against the tag — is a release-pipeline correction planned for `0.1.1`,
before any pre-release could be needed (see `ROADMAP.md`). Given the
exceptional nature of pre-releases under this policy, the fix is
prophylactic release hygiene, not a blocker for any currently planned
release.

## 6. Single source of truth for the version

**Current state (verified):** the version exists in two places that must
be kept in sync manually:

- `pyproject.toml` → `version = "0.1.0"`
- `src/pypath_inspector/__init__.py` → `__version__ = "0.1.0"`

**Recommended approach (to be introduced in `0.1.1`, not in this
document):** make `pyproject.toml` derive the version dynamically so
`__init__.py` becomes the only constant:

```toml
[project]
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {attr = "pypath_inspector.__version__"}
```

This is compatible with the existing setuptools build configuration and
build isolation, requires no runtime dependency, and keeps `--version`
and `importlib.metadata` reading the same constant. The change is
PATCH-eligible (packaging correction, no functionality).

Until (and after) that change, the following must agree for **every**
release:

1. Package metadata version (`pyproject.toml`, then the built wheel's
   `METADATA`).
2. Runtime `pypath_inspector.__version__`.
3. CLI `pypath --version` output.
4. Git tag (`v` + version).
5. GitHub Release title and attached assets.
6. PyPI version.

## 7. Automated consistency checks

To prevent version drift (planned in `0.1.1`, recorded here as policy):

1. **Unit gate** — a test asserting
   `importlib.metadata.version("pypath-inspector") ==
   pypath_inspector.__version__` in any environment where the package is
   installed (CI installs it; the test skips gracefully if metadata is
   absent, e.g. raw source trees without installation).
2. **Asset gate** — the publish workflow already derives expected asset
   filenames from the tag; it will additionally verify the wheel's
   internal METADATA version equals the tag version.
3. **Release checklist** — `RELEASING.md` requires the maintainer to
   confirm tag, changelog heading, release title and PyPI page show the
   identical version before declaring a release done.

## 8. Examples of release decisions

**Valid:**

- *0.1.1 (PATCH)* — README still claims the package is not on PyPI;
  fixing that inaccurate documentation plus a version-source packaging
  correction. No features. ✔ PATCH.
- *0.1.2 (PATCH)* — a fix for a crash in `doctor` on machines where
  `PATHEXT` is unset. Behaviour-preserving bug fix. ✔ PATCH.
- *0.2.0 (MINOR)* — PEP 514 registry discovery shipped and tested;
  interpreters invisible before are now reported. ✔ substantial discovery
  expansion.
- *0.5.0 (MINOR)* — versioned JSON schema and finding-code registry
  published. ✔ meaningful report-functionality expansion.
- *0.8.0 (MINOR)* — the freeze milestone ships a CI-enforced
  compatibility suite validating the public contract on every supported
  OS and Python combination, and adds support for a newly released Python
  version. ✔ substantial, externally verifiable compatibility and
  reliability improvement (fifth MINOR criterion).

**Invalid:**

- *0.1.2 for "PIP_INTERPRETER_MISMATCH now also detects X"* — that is new
  diagnostic functionality → must be a MINOR. ✘.
- *0.2.1 with a new `--only` flag* — a new CLI capability is not a patch. ✘.
- *0.3.0 "because it has been a while since 0.2.0"* — time is not a
  release reason. ✘.
- *0.2.0 → 0.2.5 to "fill the sequence"* — empty releases are
  forbidden. ✘.
- *0.4.0 → 0.4.1 with an exit-code change* — exit codes are public
  contract; even pre-1.0 this must be a documented MINOR-level change with
  migration notes, or post-1.0 a MAJOR. ✘ as PATCH.
- *0.8.0 consisting only of internal test infrastructure, refactoring and
  documentation polish, with no externally verifiable compatibility or
  reliability improvement* — the MINOR criteria are not met; the work is
  absorbed into 1.0.0 readiness instead of being released under a
  forced number. ✘.
