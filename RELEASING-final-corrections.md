# RELEASING.md — Final Corrections

Apply these replacements to the latest 509-line `RELEASING.md` that was pasted in the conversation. These corrections are deliberately limited to the remaining operational issues; they do not change the roadmap, version policy, current workflow, or the agreed default for partial PyPI publication.

## 1. Replace the PyPI immutability bullet in §1

Replace the current `PyPI versions are immutable` bullet with:

> - **PyPI distribution filenames are immutable once used.** PyPI accepts uploads one file at a time. A distribution filename that has already been used cannot be reused or replaced, but a different, previously unused distribution filename may still be added to the same release (for example, an sdist when only the wheel was uploaded). Never assume a retry is safe: inspect the actual files and SHA-256 digests on PyPI first (see §6 Recovery).

## 2. Replace the release-notes bullet in §4 step 1

Use a temporary file outside the repository so the release procedure does not leave an untracked file in the working tree:

> - Create the user-facing release notes outside the repository, for example at `$env:TEMP\pypath-inspector-release-notes-X.Y.Z.md`. Derive the notes from the released section in `CHANGELOG.md`; the changelog is the complete record and the release notes are its summary. They must not disagree. Keep this temporary file available until step 8. Because it is outside the repository, it does not make the Git working tree dirty and is unaffected by the tag checkout in step 4.

Add this PowerShell example immediately after that bullet (replace the sample text with the actual release summary):

```powershell
$releaseNotes = Join-Path $env:TEMP "pypath-inspector-release-notes-X.Y.Z.md"
$releaseNotesText = @'
# PyPath Inspector X.Y.Z

Release summary derived from the `CHANGELOG.md` section for X.Y.Z.
'@
[System.IO.File]::WriteAllText(
    $releaseNotes,
    $releaseNotesText,
    [System.Text.UTF8Encoding]::new($false)
)
```

For POSIX shells, use a path under `${TMPDIR:-/tmp}` and create the file there with a here-document. Do not create it in the repository root.

## 3. Replace the `--notes-file` path in §4 step 8

Define the same path in the step 8 PowerShell block (this also works if the step is run in a new PowerShell session):

```powershell
$releaseNotes = Join-Path $env:TEMP "pypath-inspector-release-notes-X.Y.Z.md"
gh release create vX.Y.Z `
  --title "PyPath Inspector X.Y.Z" `
  --notes-file $releaseNotes `
  --target <release-commit-sha> `
  dist/pypath_inspector-X.Y.Z-py3-none-any.whl `
  dist/pypath_inspector-X.Y.Z.tar.gz `
  dist/SHA256SUMS.txt
```

After the GitHub Release is successfully created, the temporary notes file may be removed:

```powershell
Remove-Item -LiteralPath $releaseNotes -Force
```

## 4. Make the version import check in §4 step 5 / §5 use the built wheel

In §4 step 5, run the following assertion in the wheel venv for **all** releases, not only after 0.1.1. It verifies the version constant imported from the built wheel against the wheel's installed distribution metadata:

```powershell
& "$env:TEMP\pypath-rel-wheel\Scripts\python.exe" -c "import importlib.metadata as md, pypath_inspector; assert md.version('pypath-inspector') == pypath_inspector.__version__ == 'X.Y.Z'; print('version consistent')"
```

Replace the current §5 item 2 (`python -c "import pypath_inspector..."`) with:

> 2. The version imported from the installed wheel and its installed distribution metadata both equal `X.Y.Z` — verified by the assertion in §4 step 5. This deliberately uses the isolated wheel environment, not whichever interpreter or package happens to be importable from the repository root.

In §4 step 5, replace the wording that says the metadata assertion is only run “once the single-source change of 0.1.1 has landed” with wording that says the manual assertion above is run for every release. The 0.1.1 automation remains an additional automated unit check and publish-workflow METADATA-to-tag check; it does not define when the manual check starts.

Keep the two-static-field comparison (`pyproject.toml` and `__init__.py`) for releases before 0.1.1. From 0.1.1 onward, keep the dynamic-version-source rule already documented in §5.

## 5. Replace §6.1 with an authoritative PyPI-state check

Use PyPI's release JSON endpoint to determine which filenames PyPI currently lists. A successful HTTP 200 response includes the release's files and their SHA-256 digests. A confirmed HTTP 404 means that version is not listed. Network, TLS, timeout, rate-limit, server, or other HTTP errors are **inconclusive** and must never be treated as proof that an artifact is absent.

```powershell
$releaseUri = "https://pypi.org/pypi/pypath-inspector/X.Y.Z/json"
try {
    $release = Invoke-RestMethod -Uri $releaseUri -ErrorAction Stop
    $release.urls |
        Select-Object filename, packagetype,
            @{Name = "sha256"; Expression = { $_.digests.sha256 }} |
        Format-Table -AutoSize
} catch {
    $statusCode = $null
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
        $statusCode = [int]$_.Exception.Response.StatusCode
    }
    if ($statusCode -eq 404) {
        Write-Output "PyPI returned HTTP 404: version X.Y.Z is not listed."
    } else {
        throw "PyPI state is inconclusive; do not classify files as absent. $($_.Exception.Message)"
    }
}
```

Interpretation:

- If the endpoint returns HTTP 200, classify the wheel and sdist separately by checking the returned `filename` / `packagetype` entries. Compare each returned SHA-256 digest with the corresponding entry in the release's `SHA256SUMS.txt`.
- For independent byte verification, download each listed file and calculate its local SHA-256 as described in §4 step 9. Compare the local digest both with PyPI's JSON digest and with the release manifest.
- If HTTP 200 is returned but one expected distribution filename is absent, that distribution is absent from the currently listed release files.
- If the endpoint returns HTTP 404, the version is not listed. Any non-404 request failure is inconclusive; resolve connectivity or PyPI service issues and retry before choosing a recovery case.

A failed `pip download` by itself is **not** proof of absence: it may be caused by network, TLS, timeout, index, rate-limit, or service errors. Use the JSON response to classify presence, and use downloaded bytes for hash verification.

## 6. Replace the `prepare`-failure subcase in §6.2

Use the original, already-tested distribution files. Do not rebuild them during asset-only recovery:

> - **`prepare` job failed** (checksums, filenames, or asset count): the workflow did not publish anything to PyPI. Correct the GitHub Release assets under the same pushed tag, but preserve the exact wheel and sdist files that were built and tested in §4 steps 4–5. If only `SHA256SUMS.txt` is wrong, regenerate the manifest from those preserved distribution files. If an asset in the GitHub Release is wrong or missing, re-attach the preserved original file. The release may be deleted and recreated if needed, but never delete or move the tag. Do not rebuild the wheel or sdist and present the new bytes as the originally tested artifacts. If the original tested files are no longer available, stop: byte-for-byte recovery is no longer possible under the single-build procedure, and a maintainer decision is required before proceeding.

## 7. Clarify the controlled partial-upload completion option in §6.3

Keep “accept the partial release and correct it in the next justified release” as the default. Replace the second option with:

> 2. **Complete the missing artifact as an explicit, reviewed engineering decision.** PyPI permits a different, previously unused distribution filename to be added to the same release; it does not permit reusing a filename that already exists. Before attempting completion, confirm that the already-published file's SHA-256 exactly matches the release manifest. A one-off workflow adjustment using `skip-existing` may then be considered so the existing filename is skipped and only the missing distribution is uploaded. This is a deliberate release-tooling change, never a blind workflow re-run. If the existing file's digest does not match the manifest, do not use `skip-existing`; follow Case D instead.

---

These changes resolve the remaining points without changing the agreed policy: the default for a partial PyPI upload remains to accept the partial release and correct it in the next justified version.
