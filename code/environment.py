"""Pinned-environment contract + verifier for the benchmark analytics stack.

This module is the single source of truth for the EXACT third-party versions the
named baselines and metric/bootstrap harness are validated against. The stage
validator and the smoke test both call :func:`verify_environment`, which FAILS
CLOSED on any version mismatch so that a silently upgraded dependency cannot
change reported numbers without being caught.

Licences are recorded here (all OSI-approved, permissive) and mirrored into
``env_lock.json`` for a machine-auditable record.
"""
from __future__ import annotations

import importlib
import importlib.metadata as ilm
import json
import platform
import sys
from typing import Dict, List

# Exact, load-bearing pins. Keep in lockstep with requirements.lock.txt.
EXPECTED_VERSIONS: Dict[str, str] = {
    "numpy": "1.26.4",
    "scipy": "1.13.1",
    "scikit-learn": "1.5.2",
    "xgboost": "2.1.4",
    "joblib": "1.5.3",
    "threadpoolctl": "3.6.0",
}

# Import name -> distribution name (they differ for scikit-learn).
_IMPORT_NAME: Dict[str, str] = {
    "numpy": "numpy",
    "scipy": "scipy",
    "scikit-learn": "sklearn",
    "xgboost": "xgboost",
    "joblib": "joblib",
    "threadpoolctl": "threadpoolctl",
}

# Verified licence record (OSI-approved permissive only). Sources: each package's
# PyPI metadata Trove classifier / LICENSE, confirmed in the pinned environment.
LICENCES: Dict[str, str] = {
    "numpy": "BSD-3-Clause",
    "scipy": "BSD-3-Clause",
    "scikit-learn": "BSD-3-Clause",
    "xgboost": "Apache-2.0",
    "joblib": "BSD-3-Clause",
    "threadpoolctl": "BSD-3-Clause",
}

EXPECTED_PYTHON = (3, 11)


def installed_version(dist: str) -> str:
    try:
        return ilm.version(dist)
    except ilm.PackageNotFoundError:
        return "MISSING"


def verify_environment(strict: bool = True) -> Dict[str, object]:
    """Check that every pinned dependency is importable at its exact version.

    Returns a report dict. If ``strict`` and any dependency is missing or at the
    wrong version (or the interpreter minor version differs), raises RuntimeError.
    """
    mismatches: List[Dict[str, str]] = []
    resolved: Dict[str, str] = {}
    for dist, want in EXPECTED_VERSIONS.items():
        got = installed_version(dist)
        resolved[dist] = got
        if got != want:
            mismatches.append({"package": dist, "expected": want, "found": got})

    py = sys.version_info[:2]
    python_ok = py == EXPECTED_PYTHON
    if not python_ok:
        mismatches.append(
            {
                "package": "python",
                "expected": ".".join(map(str, EXPECTED_PYTHON)),
                "found": ".".join(map(str, py)),
            }
        )

    report: Dict[str, object] = {
        "python_version": platform.python_version(),
        "python_ok": python_ok,
        "platform": platform.platform(),
        "resolved_versions": resolved,
        "expected_versions": dict(EXPECTED_VERSIONS),
        "licences": dict(LICENCES),
        "mismatches": mismatches,
        "passed": len(mismatches) == 0,
    }
    if strict and mismatches:
        raise RuntimeError(f"environment verification failed: {mismatches}")
    return report


def smoke_import() -> Dict[str, str]:
    """Import each pinned package and return the version reported by the module."""
    out: Dict[str, str] = {}
    for dist, mod_name in _IMPORT_NAME.items():
        mod = importlib.import_module(mod_name)
        out[dist] = getattr(mod, "__version__", "unknown")
    return out


def lock_record() -> Dict[str, object]:
    """Full machine-readable environment lock (for env_lock.json)."""
    rep = verify_environment(strict=False)
    packages = [
        {
            "package": dist,
            "version": EXPECTED_VERSIONS[dist],
            "resolved": rep["resolved_versions"][dist],  # type: ignore[index]
            "licence": LICENCES[dist],
            "role": (
                "named-baseline engine"
                if dist in ("scikit-learn", "xgboost")
                else "numeric/serialisation dependency"
            ),
        }
        for dist in EXPECTED_VERSIONS
    ]
    return {
        "resource_id": "DYFI_USGS_SINGLE_SOURCE_SEVERE_FELT_INTENSITY_V1",
        "interpreter": {
            "implementation": sys.implementation.name,
            "python_version": platform.python_version(),
            "expected_minor": ".".join(map(str, EXPECTED_PYTHON)),
        },
        "platform": platform.platform(),
        "resolver": "uv 0.12.3",
        "index_url": "https://pypi-proxy.dev.databricks.com/simple",
        "licence_policy": "OSI-approved permissive only (BSD-3-Clause / Apache-2.0)",
        "packages": packages,
        "environment_verified": rep["passed"],
    }


if __name__ == "__main__":
    print(json.dumps(verify_environment(strict=False), indent=2, sort_keys=True))
