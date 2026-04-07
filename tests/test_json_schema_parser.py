"""Tests for the JSON Schema parser against the crJSON schema file."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2pa_kg.models import PropertyType
from c2pa_kg.parsers.json_schema import parse_json_schema

SPEC_SOURCE = Path("/home/developer/specs-core")
CRJSON_PATH = SPEC_SOURCE / "docs/modules/crJSON/partials/crJSON.schema.json"

pytestmark = pytest.mark.skipif(
    not SPEC_SOURCE.is_dir(), reason="specs-core checkout not available"
)


@pytest.fixture(scope="module")
def crjson_entities():
    return parse_json_schema(CRJSON_PATH)


class TestJsonSchemaParser:
    def test_parses_without_error(self, crjson_entities) -> None:
        assert isinstance(crjson_entities, list)

    def test_entity_count_at_least_20(self, crjson_entities) -> None:
        assert len(crjson_entities) >= 20, (
            f"Expected >= 20 entities, got {len(crjson_entities)}"
        )

    def test_manifest_entity_exists(self, crjson_entities) -> None:
        # The schema has a "manifest" or "Manifest" definition
        names = {e.name for e in crjson_entities}
        manifest_candidates = {n for n in names if "manifest" in n.lower()}
        assert manifest_candidates, f"No manifest entity found in {names}"

    def test_manifest_has_properties(self, crjson_entities) -> None:
        names = {e.name for e in crjson_entities}
        manifest_name = next(
            (n for n in names if "manifest" in n.lower()), None
        )
        assert manifest_name is not None
        manifest = next(e for e in crjson_entities if e.name == manifest_name)
        assert len(manifest.properties) >= 1

    def test_entities_have_names(self, crjson_entities) -> None:
        for entity in crjson_entities:
            assert entity.name, "Entity has empty name"

    def test_reference_properties_extracted(self, crjson_entities) -> None:
        ref_props = [
            p
            for e in crjson_entities
            for p in e.properties
            if p.property_type == PropertyType.REFERENCE
        ]
        assert len(ref_props) >= 5, f"Expected >= 5 reference properties, got {len(ref_props)}"

    def test_required_properties_flagged(self, crjson_entities) -> None:
        all_props = [p for e in crjson_entities for p in e.properties]
        required = [p for p in all_props if p.required]
        assert len(required) >= 1, "No required properties found"

    def test_no_duplicate_entity_names(self, crjson_entities) -> None:
        names = [e.name for e in crjson_entities]
        assert len(names) == len(set(names)), "Duplicate entity names found"

    def test_source_set_on_entities(self, crjson_entities) -> None:
        for entity in crjson_entities:
            assert entity.source, f"Entity {entity.name!r} has no source set"
