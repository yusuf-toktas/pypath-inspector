# PyPath Inspector

**A local-first, strictly read-only diagnostic tool for Python environments on Windows, Linux and macOS.**

PyPath Inspector answers the questions that bite Windows Python developers
again and again:

- Which `python` actually runs when I type `python`? And which ones are
  shadowed on `PATH`?
- Why does `pip install` put packages into a *different* Python than the one
  I run?
- Is the Microsoft Store `python`/`python3` alias stub intercepting my
  commands?
- Am I inside a virtual environment, and is it healthy?
- Are there duplicate, empty or dead entries on my `PATH`?

It works entirely offline, uses only the Python standard library, never
modifies anything on your machine and never sends data anywhere.

---

## Features

- **Python discovery** — finds interpreters via `PATH` scanning, the Windows
  `py` launcher (`py -0p`) and `uv python list --only-installed`, deduplicated
  by real path, with versions probed by actually executing each interpreter.
- **Command resolution** — resolves `python`, `python3`, `pythonw`, `pip`,
  `pip3`, `py` and `uv`; reports every match across all `PATH` entries, which
  one wins, duplicate `PATH` entries (case-insensitive on Windows), empty
  entries, dead directories and script-shim resolutions (`.bat`/`.cmd`/...).
- **Pip analysis** — compares `pip --version`, `pip3 --version` and
  `python -m pip --version` against the interpreter the `python` command
  actually runs, detects interpreter mismatches and explains the consequences
  with safe remediation commands.
- **Virtual environment analysis** — detects venvs (`sys.prefix` vs
  `sys.base_prefix`), reports the active and base interpreters, checks
  `pyvenv.cfg`, detects stale `VIRTUAL_ENV` state and notes conda
  environments — all without ever exposing environment variable values.
- **Diagnostics** — actionable findings with `INFO` / `WARNING` / `ERROR`
  severities, each with evidence, an explanation of why it matters and
  non-destructive remediation steps.
- **Reporting** — human-readable terminal output, JSON and Markdown, with
  output file selection and stable exit codes for automation.
- **Safety** — every external command runs with a hard timeout; missing
  executables, permission errors and malformed output are handled gracefully
  and become evidence instead of crashes.

## Installation

Requires Python 3.11 or newer (tested up to 3.15). No runtime dependencies.

The package is not yet published on PyPI; install it from a checkout of this
repository. On Windows, prefer one of the first two options so the `pypath`
command ends up on your `PATH` automatically.

**Recommended — install as an isolated tool** (works offline after the tool
itself is installed):

```console
pipx install path/to/pypath-inspector
uv tool install path/to/pypath-inspector
```

**Inside a virtual environment you already use:**

```console
python -m venv .venv
.venv\Scripts\pip install path/to/pypath-inspector     # Windows
.venv/bin/pip install path/to/pypath-inspector         # Linux / macOS
```

**Plain pip install:**

```console
python -m pip install path/to/pypath-inspector
```

All of the above provide the `pypath` command (and `python -m
pypath_inspector` as an alias that never depends on `PATH`).

### A note on Windows, pip and the user Scripts directory

When you run `pip install` against a Python that lives in `C:\Program Files`
without an administrator console, pip cannot write to the system
site-packages and falls back to a *user* install. The package then lands in
`%APPDATA%\Python\PythonXY\site-packages` and the `pypath.exe` command lands
in:

```text
%APPDATA%\Python\PythonXY\Scripts
```

That directory is **not** added to `PATH` by the python.org installer, so
`pypath` will not be found in a new terminal. This is standard pip/Windows
behaviour, not a packaging bug in this project. Your options:

- use `pipx` or `uv tool install` (their tool directories are managed on
  `PATH` for you),
- use a virtual environment and its `Scripts` directory,
- add `%APPDATA%\Python\PythonXY\Scripts` to your user `PATH` manually
  (System Properties > Environment Variables),
- or install from an administrator console so pip can write to the system
  location whose `Scripts` directory is already on `PATH`.

`python -m pypath_inspector` works regardless of `PATH` as long as the
installing interpreter is the one you run.

## Usage

```console
pypath --version
pypath --help
pypath doctor                          # human-readable report in the terminal
pypath doctor --format json            # machine-readable, redacted by default
pypath doctor --format markdown        # shareable Markdown, redacted by default
pypath doctor --format markdown --output report.md
pypath doctor --no-redact              # full paths in JSON/Markdown output
pypath doctor --timeout 30             # allow more time for slow interpreters
```

`pypath` with no command prints help. `doctor` is the only command in the MVP.

### Exit codes

| Code | Meaning                                            |
|------|----------------------------------------------------|
| 0    | Diagnostics completed; no findings above INFO      |
| 1    | Diagnostics completed; WARNING findings present    |
| 2    | Diagnostics completed; ERROR findings present      |
| 3    | Usage error (unknown command or option)            |
| 4    | Internal failure (please report a bug)             |

The codes are stable and suitable for automation and CI.

### Example output

Abbreviated real output from a Windows 11 machine (full paths shown because
terminal output is not redacted):

```text
pypath-inspector 0.1.0 - Python environment doctor
==============================================================================
Generated: 2026-10-31T03:22:22+00:00 | Platform: Windows 11 (AMD64)
Running under Python 3.15.2 (pypath itself: C:\Program Files\Python\Python315\python.exe)

PYTHON INTERPRETERS (11 discovered)
------------------------------------------------------------------------------
  1. C:\Program Files\Python\Python313\python.exe
      3.13.17 [PATH, uv] | aliases: python
  ...
  10. C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python.exe
      version unknown [PATH] | aliases: python

COMMAND RESOLUTION
------------------------------------------------------------------------------
  python    -> C:\Program Files\Python\Python315\python.exe (4 matches)
  python3   -> C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python3.exe
  pip       -> C:\Program Files\Python\Python315\Scripts\pip.exe (3 matches)
  py        -> C:\Windows\py.exe
  uv        -> C:\Users\<user>\.local\bin\uv.exe

FINDINGS (6: 1 error, 1 warning, 4 info)
==============================================================================
  [ERROR] WINDOWS_STORE_ALIAS_STUB: Microsoft Store alias stubs are intercepting python commands
      - the python3 command resolves to C:\Users\<user>\AppData\Local\Microsoft\WindowsApps\python3.exe
      -   output: Python was not found; run without arguments to install from the Microsoft Store...
      - working interpreters discovered elsewhere: C:\Program Files\Python\Python315\python.exe (3.15.2); ...
      why: Windows ships zero-byte 'app execution aliases' for python and python3...
      fix: Turn the aliases off in Settings > Apps > Advanced app settings > App execution aliases, ...

Exit code: 2
```

### Finding codes

Finding codes are stable identifiers (see the JSON report):

| Code | Severity | Meaning |
|------|----------|---------|
| `PATH_MISSING` | ERROR | PATH is empty or unset |
| `PATH_DUPLICATE_ENTRIES` | WARNING | PATH contains duplicate entries |
| `PATH_EMPTY_ENTRY` | WARNING | Empty PATH entries (current directory is searched) |
| `PATH_NONEXISTENT_ENTRIES` | INFO | PATH references directories that do not exist |
| `PYTHON_NOT_FOUND` | ERROR | No Python interpreter could be discovered |
| `WINDOWS_STORE_ALIAS_STUB` | ERROR | Store alias stubs intercept python/python3 |
| `PYTHON_PROBE_FAILED` | WARNING | The resolved python could not be executed successfully |
| `MULTIPLE_PYTHON_INSTALLATIONS` | INFO | Several installations were discovered |
| `COMMAND_SHADOWED` | INFO | A command name matches multiple PATH entries |
| `SCRIPT_SHIM_RESOLUTION` | WARNING | A core command resolves to a script shim |
| `PIP_NOT_ON_PATH` | WARNING | No working pip command on PATH |
| `PIP_MODULE_MISSING` | WARNING | pip is not available inside the active interpreter |
| `PIP_INTERPRETER_MISMATCH` | ERROR | pip installs into a different Python |
| `PIP_VERSION_DISAGREEMENT` | WARNING | pip and `python -m pip` are different installations |
| `VENV_ACTIVE` | INFO | Running inside a virtual environment |
| `VENV_MISSING_CONFIG` | WARNING | venv detected but `pyvenv.cfg` is missing |
| `VENV_STALE_ENV_VAR` | WARNING | `VIRTUAL_ENV` does not match reality |
| `CONDA_ENV_ACTIVE` | INFO | A conda environment appears active |
| `UV_MANAGED_PYTHONS` | INFO | uv manages one or more installations |
| `MANAGER_LISTS_MISSING_INTERPRETER` | INFO | py/uv lists an interpreter that is gone |
| `MANAGER_QUERY_FAILED` | WARNING | py/uv could not be queried |
| `PROBE_TIMEOUT` | WARNING | An executable timed out instead of answering |

## Privacy and security design

PyPath Inspector is strictly read-only and local-first:

- **Never modifies** `PATH`, environment variables, Python installations or
  any file outside the report file you explicitly ask for.
- **Never installs, uninstalls or updates** anything, and never executes
  package installation commands. Remediation steps are suggestions you run
  yourself.
- **Never contacts the network.** No telemetry, no version checks, no AI
  APIs. There are zero runtime dependencies.
- **Never exposes environment variable values.** `VIRTUAL_ENV` and
  `CONDA_PREFIX` are only checked for presence and consistency; their values
  never appear in any report.
- **Redacts your home directory** (`~`) in exported reports by default.
  Redaction applies to the JSON and Markdown formats and to anything written
  with `--output`; plain terminal output keeps full paths so suggested
  commands stay copy-pasteable. Use `--no-redact` to opt out.
- **PATH directory entries are shown** because they are the subject of the
  diagnosis; they are the only environment-derived values that appear, and
  they are redacted in exported reports like every other path.
- **Every subprocess call has a timeout** (default 15 s, configurable) and
  full error handling. Broken or hanging executables become diagnostic
  evidence, never crashes.
- **No destructive fixes.** Suggested remediation is always manual and
  reversible; the MVP deliberately contains no automatic repair.

## Supported platforms

- **Windows 10/11** — primary target, including PATHEXT resolution order,
  the Microsoft Store alias stubs, the `py` launcher and per-user installs.
- **Linux and macOS** — supported where practical: `PATH` scanning with
  POSIX semantics, versioned `python3.x` names, `uv` integration, `python3`
  probing. Windows-specific findings (Store stubs, `py` launcher) simply do
  not fire.
- **Python 3.11 – 3.15** for the tool itself; it inspects *any* Python it
  finds, including interpreters older than 3.11 (version probing falls back
  to `--version` parsing).

## Known limitations

- Discovery can only see what `PATH`, the `py` launcher and `uv` report.
  Interpreters in unlisted directories (for example portable or embedded
  distributions that are not on `PATH` and not registered anywhere) will not
  be found. The report never claims completeness.
- The `py`/`uv` output parsers are tolerant but format-dependent; future
  manager output changes may silently reduce coverage instead of failing.
- `pythonw` executables are never executed (some builds hang without a
  console); their version is inferred from a sibling interpreter.
- Conda detection is a presence check on `CONDA_PREFIX`; conda's layout rules
  are not otherwise understood.
- `pip` mismatch detection compares reported versions and install paths; it
  cannot detect every possible cross-interpreter wiring.
- `PATH` entries wrapped in quotes (`"C:\some\dir"`) are treated as
  unresolvable by command resolution — the same way Windows itself treats
  them — but they are not flagged as duplicates of their unquoted spelling
  and are reported as existing directories.
- Terminal output keeps full paths by design; if you redirect it
  (`pypath doctor > out.txt`), the redirected file also contains full
  paths. Use `--format json` or `--format markdown` when you want
  redacted, shareable output.
- The interpreter probe runs Python code (`-c`) in each discovered
  interpreter to read `sys.prefix` and friends — read-only introspection,
  but it does execute the interpreter once per discovery.
- Terminal output is plain text; there is no colour or interactive mode, and
  no GUI.

## Development

```console
git clone <your-fork>
cd pypath-inspector
python -m pip install -e .
python -m unittest discover -s tests -t . -v
```

The test suite (139 tests) runs against temporary directories and a fake
subprocess runner, so it never depends on — or modifies — the developer
machine.

Project layout:

```text
src/pypath_inspector/
    models.py        # dataclasses shared by all layers
    probing.py       # subprocess runner, timeouts, interpreter/pip probes
    resolution.py    # PATH scanning, command resolution, duplicate detection
    discovery.py     # interpreter discovery (PATH, py launcher, uv)
    pipcheck.py      # pip / interpreter consistency analysis
    venvcheck.py     # virtual environment analysis
    diagnostics.py   # orchestration and finding construction
    reporting.py     # terminal / JSON / Markdown rendering
    redaction.py     # home-directory redaction
    cli.py           # argument parsing and exit codes
tests/               # unittest suite with fakes
```

## Contributing

Contributions are welcome. Please:

1. Open an issue describing the problem or feature before large changes.
2. Keep the project dependency-free (standard library only) and read-only —
   PRs that add network calls, telemetry, automatic repair or runtime
   dependencies will be declined.
3. Add or extend unit tests for any behaviour change; the suite must stay
   machine-independent.
4. Run `python -m unittest discover -s tests -t .` and the CI workflow
   before submitting.
5. Keep finding codes and exit codes stable — they are a public interface.

## License

[MIT](LICENSE) — PyPath Inspector contributors.
