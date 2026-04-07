"""Shared pytest fixtures for the C2PA knowledge graph test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2pa_kg.builders.ir_builder import build_knowledge_graph
from c2pa_kg.models import KnowledgeGraph, SpecVersion

SPEC_SOURCE = Path("/home/developer/specs-core")


@pytest.fixture(scope="session")
def spec_source() -> Path:
    """Return the path to the specs-core repository checkout."""
    if not SPEC_SOURCE.is_dir():
        pytest.skip(f"spec source not found: {SPEC_SOURCE}")
    return SPEC_SOURCE


@pytest.fixture(scope="module")
def sample_kg(spec_source: Path) -> KnowledgeGraph:
    """Build and return a KnowledgeGraph from the v2.4 spec.

    Module-scoped so the expensive parse runs once per test module.
    """
    version = SpecVersion(version="2.4", date="2026-04-01", tag="2.4")
    return build_knowledge_graph(spec_source, version)


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Return a temporary output directory for emitter tests."""
    return tmp_path
