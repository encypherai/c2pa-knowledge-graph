"""Tests for the conformance predicates artifact (predicates.json).

Validates structural integrity, cross-reference consistency, and
completeness of the predicate definitions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

PREDICATES_PATH = Path(__file__).parent.parent / "versions" / "2.4" / "predicates.json"


@pytest.fixture(scope="module")
def predicates() -> dict:
    """Load the v2.4 predicates.json."""
    assert PREDICATES_PATH.exists(), f"predicates.json not found: {PREDICATES_PATH}"
    return json.loads(PREDICATES_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def all_predicates(predicates: dict) -> list[dict]:
    """Collect every predicate from all format families and cross-cutting."""
    preds: list[dict] = []
    for family in predicates["format_families"].values():
        preds.extend(family["predicates"])
    preds.extend(predicates["cross_cutting"]["predicates"])
    return preds


@pytest.fixture(scope="module")
def all_predicate_ids(all_predicates: list[dict]) -> set[str]:
    """Set of all predicate IDs."""
    return {p["predicate_id"] for p in all_predicates}


# ---------------------------------------------------------------------------
# Schema-level tests
# ---------------------------------------------------------------------------


class TestPredicateSchema:
    def test_required_top_level_fields(self, predicates: dict) -> None:
        for field in ["spec_version", "predicate_schema_version",
                      "format_families", "cross_cutting", "coverage_summary"]:
            assert field in predicates, f"missing top-level field: {field}"

    def test_spec_version_matches(self, predicates: dict) -> None:
        assert predicates["spec_version"] == "2.4"

    def test_format_families_not_empty(self, predicates: dict) -> None:
        assert len(predicates["format_families"]) >= 5

    def test_each_family_has_required_fields(self, predicates: dict) -> None:
        for name, family in predicates["format_families"].items():
            for field in ["description", "mime_types", "binding_mechanism", "predicates"]:
                assert field in family, f"{name} missing field: {field}"
            assert len(family["mime_types"]) > 0, f"{name} has no MIME types"
            assert len(family["predicates"]) > 0, f"{name} has no predicates"


# ---------------------------------------------------------------------------
# Predicate structure tests
# ---------------------------------------------------------------------------


class TestPredicateStructure:
    def test_all_predicates_have_required_fields(self, all_predicates: list[dict]) -> None:
        required = {"predicate_id", "source_rules", "severity", "title", "description"}
        for pred in all_predicates:
            missing = required - set(pred.keys())
            assert not missing, f"{pred['predicate_id']} missing: {missing}"

    def test_predicate_ids_unique(self, all_predicates: list[dict]) -> None:
        ids = [p["predicate_id"] for p in all_predicates]
        duplicates = [i for i in ids if ids.count(i) > 1]
        assert len(ids) == len(set(ids)), f"duplicate predicate IDs: {duplicates}"

    def test_predicate_id_format(self, all_predicates: list[dict]) -> None:
        import re
        pattern = re.compile(r"^PRED-[A-Z]+-\d{3}$")
        for pred in all_predicates:
            assert pattern.match(pred["predicate_id"]), \
                f"bad predicate ID format: {pred['predicate_id']}"

    def test_source_rules_non_empty(self, all_predicates: list[dict]) -> None:
        for pred in all_predicates:
            assert len(pred["source_rules"]) > 0, \
                f"{pred['predicate_id']} has no source rules"

    def test_source_rule_id_format(self, all_predicates: list[dict]) -> None:
        import re
        pattern = re.compile(r"^VAL-[A-Z]+-\d{4}$")
        for pred in all_predicates:
            for rule_id in pred["source_rules"]:
                assert pattern.match(rule_id), \
                    f"{pred['predicate_id']} has bad rule ID: {rule_id}"

    def test_severity_values(self, all_predicates: list[dict]) -> None:
        allowed = {"shall", "must", "should", "may"}
        for pred in all_predicates:
            assert pred["severity"] in allowed, \
                f"{pred['predicate_id']} has bad severity: {pred['severity']}"

    def test_condition_present(self, all_predicates: list[dict]) -> None:
        for pred in all_predicates:
            assert "condition" in pred, \
                f"{pred['predicate_id']} missing condition"

    def test_condition_has_op(self, all_predicates: list[dict]) -> None:
        for pred in all_predicates:
            cond = pred["condition"]
            assert "op" in cond, \
                f"{pred['predicate_id']} condition missing 'op' field"


# ---------------------------------------------------------------------------
# Test vector tests
# ---------------------------------------------------------------------------


class TestTestVectors:
    def test_most_predicates_have_vectors(self, all_predicates: list[dict]) -> None:
        with_vectors = [p for p in all_predicates if "test_vectors" in p]
        # At least 80% should have test vectors
        ratio = len(with_vectors) / len(all_predicates)
        assert ratio >= 0.8, \
            f"only {len(with_vectors)}/{len(all_predicates)} predicates have test vectors"

    def test_vectors_have_passing_case(self, all_predicates: list[dict]) -> None:
        for pred in all_predicates:
            if "test_vectors" not in pred:
                continue
            vectors = pred["test_vectors"]
            has_passing = any(
                "passing" in key or "expected_result" in vectors.get(key, {})
                for key in vectors
            )
            assert has_passing, \
                f"{pred['predicate_id']} test vectors have no passing case"

    def test_vectors_have_failing_case(self, all_predicates: list[dict]) -> None:
        for pred in all_predicates:
            if "test_vectors" not in pred:
                continue
            vectors = pred["test_vectors"]
            has_failing = any(
                "fail" in key or "expected_status" in vectors.get(key, {})
                for key in vectors
            )
            assert has_failing, \
                f"{pred['predicate_id']} test vectors have no failing case"


# ---------------------------------------------------------------------------
# Cross-reference tests
# ---------------------------------------------------------------------------


class TestCrossReferences:
    def test_source_rules_exist_in_kg(self, predicates: dict) -> None:
        """Verify all referenced rule IDs exist in the v2.4 metadata."""
        metadata_path = PREDICATES_PATH.parent / "metadata.json"
        if not metadata_path.exists():
            pytest.skip("metadata.json not available")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        kg_rule_ids = {r["rule_id"] for r in metadata["validation_rules"]}

        all_preds: list[dict] = []
        for family in predicates["format_families"].values():
            all_preds.extend(family["predicates"])
        all_preds.extend(predicates["cross_cutting"]["predicates"])

        missing = set()
        for pred in all_preds:
            for rule_id in pred["source_rules"]:
                if rule_id not in kg_rule_ids:
                    missing.add((pred["predicate_id"], rule_id))

        assert not missing, f"rules not found in KG: {missing}"

    def test_delegate_targets_exist(self, all_predicates: list[dict],
                                     all_predicate_ids: set[str]) -> None:
        """Verify that delegate predicates reference existing predicate IDs."""
        for pred in all_predicates:
            cond = pred["condition"]
            if cond.get("op") == "delegate":
                for target in cond.get("to_predicates", []):
                    assert target in all_predicate_ids, \
                        f"{pred['predicate_id']} delegates to unknown: {target}"

    def test_status_codes_exist_in_kg(self, predicates: dict) -> None:
        """Verify all status codes referenced in predicates exist in the KG."""
        metadata_path = PREDICATES_PATH.parent / "metadata.json"
        if not metadata_path.exists():
            pytest.skip("metadata.json not available")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        kg_status_codes = {sc["code"] for sc in metadata.get("status_codes", [])}

        if not kg_status_codes:
            pytest.skip("no status codes in metadata")

        # Extract all status codes from predicates
        status_refs: set[str] = set()
        raw = json.dumps(predicates)
        import re
        for match in re.finditer(r'"status":\s*"([^"]+)"', raw):
            status_refs.add(match.group(1))

        # Also check expected_status in test vectors
        for match in re.finditer(r'"expected_status":\s*"([^"]+)"', raw):
            status_refs.add(match.group(1))

        missing = status_refs - kg_status_codes
        if missing:
            # Some status codes are from assertion labels, not status code table
            # Filter to only those that look like proper status codes
            proper_missing = {s for s in missing if "." in s and not s.startswith("c2pa.")}
            assert not proper_missing, \
                f"status codes not in KG: {proper_missing}"


# ---------------------------------------------------------------------------
# Coverage summary tests
# ---------------------------------------------------------------------------


class TestCoverageSummary:
    def test_total_predicate_count_matches(self, predicates: dict,
                                            all_predicates: list[dict]) -> None:
        declared = predicates["coverage_summary"]["total_predicates"]
        actual = len(all_predicates)
        assert declared == actual, \
            f"declared {declared} predicates but found {actual}"

    def test_rules_formalized_count(self, predicates: dict,
                                     all_predicates: list[dict]) -> None:
        declared = predicates["coverage_summary"]["rules_formalized"]
        actual_rules: set[str] = set()
        for pred in all_predicates:
            actual_rules.update(pred["source_rules"])
        # Declared count should match unique rules referenced
        # (allow for delegate predicates that share rules)
        assert declared >= len(actual_rules), \
            f"declared {declared} rules formalized but found {len(actual_rules)} unique"

    def test_format_coverage_keys_match(self, predicates: dict) -> None:
        family_keys = set(predicates["format_families"].keys())
        coverage_keys = set(predicates["coverage_summary"]["format_coverage"].keys())
        # cross_cutting is in coverage but not in format_families
        coverage_keys.discard("cross_cutting")
        assert family_keys == coverage_keys, \
            f"mismatch: families={family_keys}, coverage={coverage_keys}"

    def test_format_predicate_counts_match(self, predicates: dict) -> None:
        for name, family in predicates["format_families"].items():
            actual = len(family["predicates"])
            declared = predicates["coverage_summary"]["format_coverage"][name]["predicates"]
            assert actual == declared, \
                f"{name}: declared {declared} predicates but has {actual}"
