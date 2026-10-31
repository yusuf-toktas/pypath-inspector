"""PyPath Inspector: a local-first, read-only Python environment doctor.

PyPath Inspector diagnoses Python installations, command resolution, PATH
configuration and pip/interpreter mismatches. It is strictly read-only,
uses only the Python standard library and never contacts the network.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
