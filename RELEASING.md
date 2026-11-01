# Releasing PyPath Inspector

This is the official release procedure. It describes the process as it
exists in this repository today (verified at commit `06da4c4`): a
**release-asset-driven** flow in which the maintainer builds and verifies
distributions locally, attaches them to a GitHub Release, and a hardened
workflow republishes exactly those bytes to PyPI via Trusted Publishing
(OIDC).

Related documents: [`VERSIONING.md`](VERSIONING.md) (which number to
release), [`ROADMAP.md`](ROADMAP.md) (what belongs in the release),
[`CHANGELOG.md`](CHANGELOG.md) (what shipped).

---

## 1. How publication works today

`.github/workflows/publish.yml`:

- **Triggers:** the `release: published` event, or manual
  `workflow_dispatch` with a `release_tag` input (used for re-running
  publication of an already-verified release).
- **`prepare` job** (ubuntu, `contents: read`):
  1. Validates the tag against
     `^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$`.
  2. Downloads exactly the wheel, the sdist and `SHA256SUMS.txt` from the
     GitHub Release.
  3. Derives the expected asset filenames from the tag and requires
     exactly 3 assets — nothing more.
  4. Parses `SHA256SUMS.txt` (strict `digest␣␣filename` lines, no
     duplicates) and verifies every SHA-256 digest against the downloaded
     bytes.
  5. Uploads the verified distributions as a short-lived artifact.
- **`publish` job** (ubuntu, GitHub environment `pypi`, `id-token:
  write`): downloads the verified artifact and publishes it with
  `pypa/gh-action-pypi-publish` (OIDC Trusted Publishing — no API tokens).

Consequences that shape this procedure:

- **The GitHub Release assets are the source of truth.** The workflow
  never rebuilds; whatever bytes were attached to the release are what
  PyPI receives. Never rebuild different contents after a tag exists and
  assume they are "the same".
- **Build once, publish those bytes.** The distributions are built exactly
  once per release (§4 step 4); the files tested locally are the files
  checksummed, attached to the GitHub Release and published to PyPI.
  Nothing is rebuilt after verification.
- **PyPI versions are immutable.** A version, once published, can never be
  uploaded again. Mistakes in an already-published version consume its
  number and require a new release (asset-only failures before
  publication are recoverable — see §6.6). Re-upload safety must never
  be assumed — see §6 Recovery.
- **Pre-releases cannot be published with the workflow as it stands
  (verified defect).** Canonical PEP 440 tags (`v0.2.0a1`) are rejected by
  the tag regex, and separator-form tags (`v0.2.0.a1`) fail the expected
  asset-name checks because setuptools normalizes the version in
  filenames. The fix is planned as a `0.1.1` release-pipeline correction;
  do not attempt a pre-release release until it has landed (see
  `VERSIONING.md` §5).
- The v0.1.0 assets were built locally by the maintainer (wheel 39,091
  bytes, sdist 55,101 bytes, `SHA256SUMS.txt` 204 bytes). Until the asset
  helper script planned for `0.1.1` exists, §4 steps 4–6 are the manual
  procedure.

## 2. Release gates

Mandatory gates per release type. `1.0.0` (and any `rc` of it) requires
every gate. A gate marked ✱ becomes automated by the `0.1.1` tooling; until
then it is a manual checklist item.

| # | Gate | PATCH | MINOR | Pre-release | 1.0.0 |
|---|------|:-----:|:-----:|:-----------:|:-----:|
| 1 | Milestone scope complete (ROADMAP acceptance criteria) | — | ✔ | ✔ | ✔ |
| 2 | Tests cover changed behaviour | ✔ | ✔ | ✔ | ✔ |
| 3 | Full unit test suite passes locally | ✔ | ✔ | ✔ | ✔ |
| 4 | Windows CI passes | ✔ | ✔ | ✔ | ✔ |
| 5 | Linux CI passes | ✔ | ✔ | ✔ | ✔ |
| 6 | macOS CI passes | ✔ | ✔ | ✔ | ✔ |
| 7 | Full supported Python matrix passes | ✔ | ✔ | ✔ | ✔ |
| 8 | Package version consistency verified (§5) ✱ | ✔ | ✔ | ✔ | ✔ |
| 9 | Wheel builds | ✔ | ✔ | ✔ | ✔ |
| 10 | sdist builds | ✔ | ✔ | ✔ | ✔ |
| 11 | `twine check dist/*` passes | ✔ | ✔ | ✔ | ✔ |
| 12 | Clean-environment installation succeeds (fresh venv, wheel **and** sdist) | ✔ | ✔ | ✔ | ✔ |
| 13 | CLI smoke tests succeed (`--version`, `doctor` all formats, JSON validity, exit codes) | ✔ | ✔ | ✔ | ✔ |
| 14 | JSON report schema-valid against the published JSON Schema ¹ | ✔ ¹ | ✔ ¹ | ✔ ¹ | ✔ ¹ |
| 15 | SHA-256 checksums generated and verified | ✔ | ✔ | ✔ | ✔ |
| 16 | Changelog accurate (released section matches shipped scope) | ✔ | ✔ | ✔ | ✔ |
| 17 | Git tag points to the exact release commit | ✔ | ✔ | ✔ | ✔ |
| 18 | GitHub Release contains the verified distributions | ✔ | ✔ | ✔ | ✔ |
| 19 | PyPI publication via Trusted Publishing / OIDC | ✔ | ✔ | ✔ | ✔ |
| 20 | Published PyPI artifacts independently verified (§4 step 9) | ✔ | ✔ | ✔ | ✔ |

¹ Gate 14 applies **only from 0.5.0 onward**, when the JSON Schema is
published; before 0.5.0 the gate does not exist, and plain JSON validity
is already covered by gate 13. From 0.5.0 the gate is mandatory for
**every** release type — PATCH included: a PATCH release that
accidentally changed the JSON report shape must fail here, which is
precisely the gate's purpose. The gate is enforced through the test
suite — golden report fixtures validated against the published schema,
per the ROADMAP 0.5.0 scope — running locally in §4 step 2 and in CI in
§4 step 7; see the gates 13/14 note in §4 step 5.

Additional `1.0.0`-only gates: the readiness checklist in
`ROADMAP.md` §5 is fully green, and every documentation file has been
re-verified against the implementation during the freeze-milestone
hardening pass (released as 0.8.0 if its justification gate is met;
otherwise performed as absorbed 1.0.0 readiness work).

**Never** publish from an unverified or dirty working tree.

## 3. Pre-release checks (all types)

1. `git status` is clean; `HEAD` equals `origin/main`; no unpushed commits.
2. Decide the version number per `VERSIONING.md`; confirm the roadmap
   scope for that version is complete.
3. Confirm no known ERROR-severity defect is open.
4. Confirm the supported Python matrix in CI matches the intended support
   statement (changes to the matrix are release-scope decisions).

## 4. Step-by-step procedure

The distributions are built **exactly once**, in step 4. The bytes tested
in step 5 are the bytes checksummed in step 6, attached to the GitHub
Release in step 8 and published to PyPI. Nothing is rebuilt after
verification, and nothing is pushed until every local gate has passed.

### 1. Update the version and changelog

- Set the new version in **both** places (until the single-source change
  planned for 0.1.1): `pyproject.toml` `version =` and
  `src/pypath_inspector/__init__.py` `__version__ =`. They must be
  character-identical.
- Add a released section to `CHANGELOG.md` (`## [X.Y.Z] - YYYY-MM-DD`)
  describing exactly what ships. Move any items from `[Unreleased]`.
- Create `release-notes.md` in the repository root with the user-facing
  notes for this release, derived from the `CHANGELOG.md` released
  section — the changelog is the complete record; the notes are its
  summary, and the two must not disagree. Keep the file **untracked**
  (do not commit it): untracked files survive the tag checkout in
  step 4, so it is still available to step 8.
- Commit: `Bump version to X.Y.Z` (conventional, scoped to the release).
  This is the **release commit**.

### 2. Run the unit tests

On the release commit (the working tree is already at it):

```powershell
python -m unittest discover -s tests -t .
```

The full suite must pass before anything is tagged (gate 3).

### 3. Tag the release commit locally

```powershell
git tag -a vX.Y.Z -m "PyPath Inspector X.Y.Z" <release-commit-sha>
```

Create the annotated tag now, but **do not push anything yet** — `main`
and the tag are pushed only after every local gate has passed (step 7).
Pre-release tags follow PEP 440 (`v0.2.0a1`). The tag must point at the
exact release commit.

### 4. Check out the tag and build the distributions once

From the repository root, on a clean tree of the tag, with `dist/`
removed first so no stale artifact can survive:

```powershell
git checkout vX.Y.Z
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
python -m pip install --quiet --upgrade build twine
python -m build --outdir dist .
```

(POSIX equivalent: `rm -rf dist && python -m build --outdir dist .`)

This is the **only** build of the release. The files produced here are
the release assets, byte-for-byte; do not rebuild them later.

### 5. Verify exactly these artifacts

Metadata check (works in PowerShell exactly as written — twine expands
the pattern itself, no shell globbing is required; verified against the
v0.1.0 assets):

```powershell
python -m twine check dist/*
```

Then test the built files themselves, each in its own fresh virtual
environment:

```powershell
python -m venv "$env:TEMP\pypath-rel-wheel"
& "$env:TEMP\pypath-rel-wheel\Scripts\python.exe" -m pip install --quiet dist\pypath_inspector-X.Y.Z-py3-none-any.whl

python -m venv "$env:TEMP\pypath-rel-sdist"
& "$env:TEMP\pypath-rel-sdist\Scripts\python.exe" -m pip install --quiet dist\pypath_inspector-X.Y.Z.tar.gz
```

In **each** of the two environments run:

```powershell
$s = "$env:TEMP\pypath-rel-wheel\Scripts"     # then repeat with pypath-rel-sdist
& "$s\pypath.exe" --version                    # must print X.Y.Z
& "$s\pypath.exe" doctor --format json         # must be valid JSON
& "$s\pypath.exe" doctor --format markdown --output "$env:TEMP\report.md"
& "$s\python.exe" -m pypath_inspector --version
```

`doctor` exit code 0–2 is expected depending on the machine; 3 or 4 is a
release blocker. (From 0.7.0 onward, also smoke-test `pypath diff` with a
report pair: exit 0 on identical inputs, 1 on differences, 3 on invalid
input — and confirm the `doctor` vs `diff` exit-code distinction holds.)

This step is also where the runtime portion of the version-consistency
gate (§5, gate 8) is completed: `pypath --version` and
`python -m pypath_inspector --version` in **both** environments must
print exactly `X.Y.Z`, and — once the single-source change of 0.1.1 has
landed — the built-wheel metadata assertion from §5 runs in the wheel
environment, **before** the cleanup below:

```powershell
& "$env:TEMP\pypath-rel-wheel\Scripts\python.exe" -c "import importlib.metadata as md, pypath_inspector; assert md.version('pypath-inspector') == pypath_inspector.__version__ == 'X.Y.Z'; print('version consistent')"
```

Gate 8 must be green before step 7 pushes the tag.

Note the distinction between gates 13 and 14: this step checks that the
JSON output is *valid JSON* (gate 13). Schema validity against the
published JSON Schema (gate 14, from 0.5.0) is deliberately **not** an
ad-hoc release command here — per the ROADMAP 0.5.0 scope it is enforced
by the test suite, which validates golden report fixtures against the
schema and runs in step 2 locally and in CI in step 7.

Clean up afterwards:

```powershell
Remove-Item -Recurse -Force "$env:TEMP\pypath-rel-wheel", "$env:TEMP\pypath-rel-sdist"
```

### 6. Generate and verify the checksum manifest

Generate `SHA256SUMS.txt` in the exact format the workflow verifies
(`<64 lowercase hex digits><space><space><bare filename>`, one line per
artifact; both LF and CRLF line endings are accepted by the workflow's
parser). From the repository root — do **not** `cd` into `dist`; the
release step below references `dist/...` paths:

```powershell
$dist = Join-Path (Get-Location) "dist"
$lines = Get-ChildItem $dist -File |
  Where-Object { $_.Name -like "*.whl" -or $_.Name -like "*.tar.gz" } |
  Sort-Object Name |
  ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
[System.IO.File]::WriteAllLines((Join-Path $dist "SHA256SUMS.txt"), $lines)
```

`[System.IO.File]::WriteAllLines` writes each checksum as its own line
(UTF-8 without BOM by default). Two pitfalls are deliberately avoided:
`Set-Content -NoNewline` with pipeline input concatenates the entries
without any separator, and filtering on `$_.Extension` would silently
drop the sdist, because PowerShell reports `.tar.gz` files as having
extension `.gz`.

(On POSIX, from the repository root:
`(cd dist && sha256sum *.whl *.tar.gz) > dist/SHA256SUMS.txt` — the
subshell keeps the filenames bare while leaving the working directory
untouched.)

`dist/` must contain exactly three files: the wheel, the sdist,
`SHA256SUMS.txt`. When the `0.1.1` helper script exists, it replaces
this step.

### 7. Push `main` and the tag; wait for CI

Only now that every local gate has passed:

```powershell
git push origin main
git push origin vX.Y.Z
gh run watch
```

The CI run triggered by the push must be green on the full matrix
(gates 4–7) before the release is created.

### 8. Create the GitHub Release with the same files

```powershell
gh release create vX.Y.Z `
  --title "PyPath Inspector X.Y.Z" `
  --notes-file release-notes.md `
  --target <release-commit-sha> `
  dist/pypath_inspector-X.Y.Z-py3-none-any.whl `
  dist/pypath_inspector-X.Y.Z.tar.gz `
  dist/SHA256SUMS.txt
```

Mark pre-releases with `--prerelease`. Attach **only** the three files
built in step 4 — never rebuild; the workflow rejects any extra assets.
`release-notes.md` was created in step 1; being untracked, it is still in
the working tree after the step 4 tag checkout (the working directory has
remained the repository root throughout).

### 9. Let the publish workflow run and verify PyPI independently

The `release: published` event triggers *Publish to PyPI* automatically.
Monitor:

```powershell
gh run watch
```

The `prepare` job must pass all checksum and filename checks; the
`publish` job must succeed in the `pypi` environment. If it fails, see
§6 Recovery — **verify the actual PyPI state before re-running anything**.

Then, from a clean machine or venv (not the build tree):

```powershell
python -m pip index versions pypath-inspector      # shows X.Y.Z
python -m pip install pypath-inspector==X.Y.Z
pypath --version                                    # X.Y.Z
```

And verify **both** published artifacts independently — one download per
artifact type, so the wheel and the sdist are each checked against
`SHA256SUMS.txt` from the release:

```powershell
python -m pip download pypath-inspector==X.Y.Z --no-deps --only-binary :all: -d verify-wheel
python -m pip download pypath-inspector==X.Y.Z --no-deps --no-binary :all: -d verify-sdist
Get-FileHash verify-wheel\*.whl -Algorithm SHA256      # compare against SHA256SUMS.txt
Get-FileHash verify-sdist\*.tar.gz -Algorithm SHA256   # compare against SHA256SUMS.txt
```

`--only-binary :all:` downloads only the wheel; `--no-binary :all:`
downloads only the sdist. Both digests must match the corresponding
entries in `SHA256SUMS.txt`; a mismatch on either artifact is a release
defect (see §6 Recovery).

### 10. Post-release

- Confirm the GitHub Release page lists the three assets with the expected
  digests (GitHub displays `sha256:` digests per asset).
- Confirm `CHANGELOG.md`, tag, release title and PyPI all show the same
  version (the six-way consistency list in `VERSIONING.md` §6).
- Return the working tree to `main` (`git checkout main`).
- Update the roadmap: mark the milestone released.

## 5. Version consistency verification (gate 8)

These checks are performed **after the local tag has been created (§4
step 3) and the distributions built (step 4), and must all be green
before the tag is pushed (step 7) and the release created (step 8)**.
Each check lands in a specific step of §4; the procedure itself changes
with the single-source transition planned in `0.1.1` (`VERSIONING.md`
§6):

**Until 0.1.1 (current state — two static version fields):**

1. `pyproject.toml` `version =` and
   `src/pypath_inspector/__init__.py` `__version__ =` are
   **character-identical** — both edited together in §4 step 1.
2. `python -c "import pypath_inspector; print(pypath_inspector.__version__)"`
   — run on the release commit; the step 4 tag checkout does not change
   the tree (the tag points at the release commit).
3. `pypath --version` (from an installed copy) — completed in §4 step 5,
   in **both** fresh environments.
4. The wheel/sdist filenames produced by `python -m build` — §4 step 4.
5. The intended git tag (`v` + the same string) — created in §4 step 3.
6. The `CHANGELOG.md` released-section heading — written in §4 step 1.

**From 0.1.1 (dynamic version — `__init__.py` is the only constant):**

1. `src/pypath_inspector/__init__.py` `__version__ =` is the single
   source of truth; `pyproject.toml` declares `dynamic = ["version"]` and
   carries no literal version that could drift.
2. The built distribution's metadata must match — the assertion runs in
   the wheel environment created in §4 step 5 (see the command there,
   before the environment cleanup):

   ```powershell
   & "$env:TEMP\pypath-rel-wheel\Scripts\python.exe" -c "import importlib.metadata as md, pypath_inspector; assert md.version('pypath-inspector') == pypath_inspector.__version__ == 'X.Y.Z'; print('version consistent')"
   ```

3. Checks 2–6 of the pre-0.1.1 list continue to apply, in the same
   steps.

Both automations above are **planned** for `0.1.1` (see the 0.1.1 scope
in `ROADMAP.md`): a unit check asserting the installed distribution
metadata equals `__version__`, and a publish-workflow step cross-checking
the wheel's METADATA version against the tag. The workflow as it exists
today (commit `06da4c4`) performs **no** METADATA–tag cross-check — it
validates the tag format, the expected asset filenames and the SHA-256
manifest only. Until the planned change lands, the manual list above is
the only defence against version drift.

## 6. Recovery procedures

Two rules govern every recovery, without exception:

- **A pushed tag is final.** Never delete, move or rewrite a tag that has
  been pushed — regardless of whether anything reached PyPI. "Nothing
  reached PyPI" never licenses touching a pushed tag. (A tag that was
  never pushed may still be deleted locally and recreated.)
- **PyPI files are immutable, and re-upload safety must never be
  assumed.** Before any recovery action, determine what is actually on
  PyPI and whether its digests match the release manifest.

### 6.1 First step: determine the actual PyPI state

Run the per-artifact verification from §4 step 9 and record which of the
two downloads succeed:

```powershell
python -m pip download pypath-inspector==X.Y.Z --no-deps --only-binary :all: -d verify-wheel
python -m pip download pypath-inspector==X.Y.Z --no-deps --no-binary :all: -d verify-sdist
Get-FileHash verify-wheel\*.whl -Algorithm SHA256      # compare against SHA256SUMS.txt
Get-FileHash verify-sdist\*.tar.gz -Algorithm SHA256   # compare against SHA256SUMS.txt
```

A failed download (or a "cannot find path" error from `Get-FileHash`)
means that artifact type is absent from PyPI. Compare every digest that
*was* retrieved against the corresponding entry in `SHA256SUMS.txt`,
then follow the case that matches.

### 6.2 Case A — nothing reached PyPI

Re-publication is safe. Two sub-cases:

- **`prepare` job failed** (checksums, filenames, asset count): the
  release exists on GitHub but the workflow never touched PyPI. Fix the
  assets **under the same tag**: delete the *release* (never the tag),
  re-prepare the assets **from the same tagged commit** (steps 4–6 of
  §4, including a clean `dist/`), recreate the release, and let the
  workflow run again.
- **`publish` job failed after `prepare` succeeded**: re-run the workflow
  via `workflow_dispatch` with `release_tag: vX.Y.Z` — the verified
  assets are re-downloaded from the release and republished.

### 6.3 Case B — exactly one artifact type reached PyPI (partial upload)

The publishing action (`pypa/gh-action-pypi-publish`, pinned at v1.14.3)
runs **without** `skip-existing`, whose default is `false`. A plain
re-run would therefore attempt to re-upload the file that already
reached PyPI and be **rejected by PyPI's immutability rule**. Do **not**
blindly re-run the workflow in this case. The options are:

1. **Accept the partial release** (default): one artifact type is missing
   on PyPI for this version. Ship the correction in the next justified
   release and record the incident in `CHANGELOG.md`.
2. **Complete the missing artifact as an explicit, reviewed engineering
   decision** — for example a one-off, documented workflow adjustment
   (such as enabling `skip-existing` for that run). This is a deliberate
   change to release tooling, never a silent re-run.

### 6.4 Case C — both artifacts reached PyPI

The version is fully published; no re-upload is possible. If the content
is wrong: yank the version on PyPI if harmful (PyPI web UI), publish the
correction as the next justified number per `VERSIONING.md`, and record
the incident in `CHANGELOG.md`.

### 6.5 Case D — a reached file's digest does not match `SHA256SUMS.txt`

Treat exactly as Case C: the version is consumed, re-uploading cannot
fix it. Yank if harmful; correct in the next justified release; record
the incident.

### 6.6 Tag and version-number policy for failed releases

- **Asset-only defect, source commit correct:** the assets may be
  re-prepared and re-attached under the **same** pushed tag (Case A).
  The tag is reused exactly as it is, so the version number is **not**
  consumed — the failed attempt costs nothing.
- **Source code or package metadata must change:** the pushed tag cannot
  be moved to another commit and therefore cannot be reused at all. A
  **new, justified version number** is required, chosen per
  `VERSIONING.md` based on what the replacement release actually ships,
  and the old number can never be used again.
- **When is a number actually consumed?** Exactly when its pushed tag can
  no longer be used as-is — either because the release completed on PyPI
  (Cases C/D), or because fixing the release requires changing the
  source or package metadata under the tag. A failed publication alone
  consumes nothing: if the defect is confined to the assets and the
  tagged source is correct, the same tag and number stay in service
  until the release succeeds. No version-skipping rule is invented here:
  the replacement release is numbered per `VERSIONING.md` §3–§4 by what
  it ships, the milestone itself is not "skipped" (its scope ships in
  the replacement), and the failed attempt and its reason are recorded
  in the replacement release's notes.
- **Release published without assets:** publishing the release **does**
  trigger the workflow — the `release: published` event fires regardless
  of whether assets are attached — but the `prepare` job then fails,
  because it cannot download the wheel, the sdist and `SHA256SUMS.txt`.
  Recovery: attach the three assets built in §4 step 4 to the existing
  release, then start the workflow manually via `workflow_dispatch`
  with `release_tag: vX.Y.Z`. Do **not** expect the `published` event to
  fire again — uploading assets to an already-published release does
  not re-emit it.

## 7. Security notes

- All workflow actions are pinned by full commit SHA with version
  comments; keep that practice when updating them.
- Publication uses OIDC Trusted Publishing only — no long-lived PyPI
  tokens in secrets. The `pypi` GitHub environment gates the publishing
  job.
- The workflow's least-privilege permissions (`contents: read`,
  `id-token: write` on the publishing job only) must be preserved.
