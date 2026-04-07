"""Manage C2PA spec version checkout and registry.

Provides the hardcoded registry of all known C2PA specification versions and
helpers to checkout a local spec repo clone to a specific version tag.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from c2pa_kg.models import SpecVersion

# Hardcoded registry of all known C2PA specification versions.
# Tags in c2pa-org/specs-core use bare numbers (no 'v' prefix).
# v2.3 uses a commit hash because the upstream repo is missing the tag
# (the antora-2.3 branch was merged but never tagged; see
# https://github.com/c2pa-org/specs-core/issues/2115).
SPEC_VERSIONS: list[SpecVersion] = [
    SpecVersion(version="2.4", date="2026-04-01", tag="2.4"),
    SpecVersion(
        version="2.3", date="2025-12-01", tag="38e492b0",
        commit_hash="38e492b037ccabd48bff9f2b9bd1169371c2b057",
    ),
    SpecVersion(version="2.2", date="2025-09-22", tag="2.2"),
    SpecVersion(version="2.1", date="2024-09-26", tag="2.1"),
    SpecVersion(version="2.0", date="2024-01-24", tag="2.0"),
    SpecVersion(version="1.4", date="2023-11-06", tag="1.4"),
    SpecVersion(version="1.3", date="2023-03-30", tag="1.3"),
    SpecVersion(version="1.2", date="2022-11-15", tag="1.2"),
    SpecVersion(version="1.1", date="2022-09-12", tag="1.1"),
    SpecVersion(version="1.0", date="2021-12-24", tag="1.0"),
    SpecVersion(version="0.8", date="2021-11-11", tag="0.8"),
    SpecVersion(version="0.7", date="2021-09-12", tag="0.7"),
]

_VERSION_INDEX: dict[str, SpecVersion] = {sv.version: sv for sv in SPEC_VERSIONS}


def checkout_spec_version(spec_repo: Path, version: str) -> None:
    """Git checkout the spec repo to a specific version tag.

    Args:
        spec_repo: Path to the local clone of the c2pa-org/specs-core repo.
        version: Version string (e.g. "2.4"). Must exist in SPEC_VERSIONS.

    Raises:
        ValueError: If the version is not in the known registry.
        subprocess.CalledProcessError: If the git checkout fails.
    """
    if version not in _VERSION_INDEX:
        known = ", ".join(sv.version for sv in SPEC_VERSIONS)
        raise ValueError(
            f"Unknown spec version '{version}'. Known versions: {known}"
        )
    spec_version = _VERSION_INDEX[version]
    tag = spec_version.tag
    subprocess.run(
        ["git", "checkout", tag],
        cwd=spec_repo,
        check=True,
        capture_output=True,
        text=True,
    )


def get_current_version(spec_repo: Path) -> str:
    """Get the current checked-out version tag from the spec repo.

    Runs `git describe --tags --exact-match` to resolve the HEAD tag.

    Args:
        spec_repo: Path to the local clone of the spec repo.

    Returns:
        The tag string at HEAD (e.g. "2.4").

    Raises:
        subprocess.CalledProcessError: If HEAD is not at a known tag.
    """
    result = subprocess.run(
        ["git", "describe", "--tags", "--exact-match"],
        cwd=spec_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def list_versions() -> list[SpecVersion]:
    """Return all known spec versions in descending order (newest first).

    Returns:
        A copy of the SPEC_VERSIONS registry list.
    """
    return list(SPEC_VERSIONS)


def get_version(version: str) -> SpecVersion:
    """Get metadata for a specific spec version.

    Args:
        version: Version string (e.g. "2.4").

    Returns:
        The corresponding SpecVersion dataclass.

    Raises:
        KeyError: If the version is not in the registry.
    """
    if version not in _VERSION_INDEX:
        known = ", ".join(sv.version for sv in SPEC_VERSIONS)
        raise KeyError(
            f"Unknown spec version '{version}'. Known versions: {known}"
        )
    return _VERSION_INDEX[version]
