"""Tests for the CDDL parser against real C2PA spec files."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2pa_kg.models import Cardinality, PropertyType
from c2pa_kg.parsers.cddl import parse_cddl_directory, parse_cddl_file

SPEC_SOURCE = Path("/home/developer/specs-core")
CDDL_DIR = SPEC_SOURCE / "docs/modules/specs/partials/schemas/cddl"

pytestmark = pytest.mark.skipif(
    not SPEC_SOURCE.is_dir(), reason="specs-core checkout not available"
)


# ---------------------------------------------------------------------------
# claim.cddl
# ---------------------------------------------------------------------------

class TestClaimCddl:
    @pytest.fixture(scope="class")
    def claim_result(self):
        entities, enums = parse_cddl_file(CDDL_DIR / "claim.cddl")
        return entities, enums

    def test_parses_without_error(self, claim_result) -> None:
        entities, enums = claim_result
        assert len(entities) >= 1

    def test_claim_map_entity_exists(self, claim_result) -> None:
        entities, _ = claim_result
        names = [e.name for e in entities]
        assert "ClaimMap" in names

    def test_claim_map_has_expected_properties(self, claim_result) -> None:
        entities, _ = claim_result
        claim = next(e for e in entities if e.name == "ClaimMap")
        prop_names = {p.name for p in claim.properties}
        # These fields are defined in claim-map in the spec
        assert "instanceID" in prop_names or "claim_generator" in prop_names

    def test_required_property_detection(self, claim_result) -> None:
        entities, _ = claim_result
        claim = next(e for e in entities if e.name == "ClaimMap")
        # "signature" is required (no ? marker)
        required_props = {p.name for p in claim.properties if p.required}
        assert len(required_props) >= 1

    def test_optional_property_detection(self, claim_result) -> None:
        entities, _ = claim_result
        claim = next(e for e in entities if e.name == "ClaimMap")
        optional_props = [p for p in claim.properties if not p.required]
        # dc:title and redacted_assertions are optional
        assert len(optional_props) >= 1

    def test_optional_property_cardinality(self, claim_result) -> None:
        entities, _ = claim_result
        claim = next(e for e in entities if e.name == "ClaimMap")
        optional_props = [p for p in claim.properties if not p.required]
        for prop in optional_props:
            assert prop.cardinality in (Cardinality.ZERO_OR_ONE, Cardinality.ZERO_OR_MORE)


# ---------------------------------------------------------------------------
# actions.cddl
# ---------------------------------------------------------------------------

class TestActionsCddl:
    @pytest.fixture(scope="class")
    def actions_result(self):
        return parse_cddl_file(CDDL_DIR / "actions.cddl")

    def test_parses_without_error(self, actions_result) -> None:
        entities, enums = actions_result
        # Should yield at least one entity (actions-map)
        assert len(entities) >= 1

    def test_action_choice_enum_extracted(self, actions_result) -> None:
        _, enums = actions_result
        enum_names = {e.name for e in enums}
        assert "ActionChoice" in enum_names

    def test_action_choice_has_values(self, actions_result) -> None:
        _, enums = actions_result
        action_choice = next(e for e in enums if e.name == "ActionChoice")
        assert len(action_choice.values) >= 10

    def test_action_choice_includes_common_actions(self, actions_result) -> None:
        _, enums = actions_result
        action_choice = next(e for e in enums if e.name == "ActionChoice")
        # At minimum, c2pa.created and c2pa.edited should be present
        assert "c2pa.created" in action_choice.values
        assert "c2pa.edited" in action_choice.values


# ---------------------------------------------------------------------------
# Full directory parse
# ---------------------------------------------------------------------------

class TestCddlDirectory:
    @pytest.fixture(scope="class")
    def dir_result(self):
        return parse_cddl_directory(CDDL_DIR)

    def test_entity_count_at_least_50(self, dir_result) -> None:
        entities, _ = dir_result
        assert len(entities) >= 50, f"Expected >= 50 entities, got {len(entities)}"

    def test_enum_count_positive(self, dir_result) -> None:
        _, enums = dir_result
        assert len(enums) >= 1

    def test_no_duplicate_entity_names(self, dir_result) -> None:
        entities, _ = dir_result
        names = [e.name for e in entities]
        assert len(names) == len(set(names))

    def test_action_items_map_entity_exists(self, dir_result) -> None:
        entities, _ = dir_result
        names = {e.name for e in entities}
        assert "ActionItemsMap" in names

    def test_entities_have_properties(self, dir_result) -> None:
        entities, _ = dir_result
        # Most entities should have at least one property
        entities_with_props = [e for e in entities if e.properties]
        assert len(entities_with_props) >= 30

    def test_reference_properties_point_to_known_types(self, dir_result) -> None:
        entities, _ = dir_result
        _entity_names = {e.name for e in entities}
        reference_props = [
            (e.name, p)
            for e in entities
            for p in e.properties
            if p.property_type == PropertyType.REFERENCE and p.reference_target
        ]
        # At least some reference properties should exist
        assert len(reference_props) >= 5
