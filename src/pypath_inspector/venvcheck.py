"""Virtual environment analysis.

Detects whether the primary interpreter runs inside a virtual environment
and whether the surrounding shell state is consistent with it.

Privacy: environment variables are only checked for *presence* and
*consistency*; their values are never included in any report.
"""

from __future__ import annotations

import os
from typing import Mapping

from .models import InterpreterProbe, VenvAnalysis


def analyze_venv(probe: InterpreterProbe | None, env: Mapping[str, str]) -> VenvAnalysis:
    """Analyse the virtual environment state of the primary interpreter.

    Args:
        probe: Probe result of the primary ``python`` command, if any.
        env: Environment mapping (values are read but never exposed).

    Returns:
        A :class:`VenvAnalysis`.
    """
    probed = probe is not None
    probe_ok = bool(probe and probe.ok)

    in_venv = probe.is_venv if probe_ok and probe is not None else None
    prefix = probe.prefix if probe_ok and probe is not None else None
    base_prefix = probe.base_prefix if probe_ok and probe is not None else None
    base_executable = probe.base_executable if probe_ok and probe is not None else None

    pyvenv_cfg_present: bool | None = None
    if in_venv and prefix:
        pyvenv_cfg_present = os.path.isfile(os.path.join(prefix, "pyvenv.cfg"))

    virtual_env_set = "VIRTUAL_ENV" in env
    virtual_env_consistent: bool | None = None
    if virtual_env_set and probe_ok and probe is not None:
        if in_venv and prefix:
            virtual_env_consistent = _same_path(env["VIRTUAL_ENV"], prefix)
        else:
            virtual_env_consistent = False

    return VenvAnalysis(
        probed=probed,
        probe_ok=probe_ok,
        in_venv=in_venv,
        prefix=prefix,
        base_prefix=base_prefix,
        base_executable=base_executable,
        pyvenv_cfg_present=pyvenv_cfg_present,
        virtual_env_set=virtual_env_set,
        virtual_env_consistent=virtual_env_consistent,
        conda_prefix_set="CONDA_PREFIX" in env,
    )


def _same_path(left: str, right: str) -> bool:
    """Compare two paths after normalisation, ignoring case and separators."""
    return _normalize(left) == _normalize(right)


def _normalize(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))
