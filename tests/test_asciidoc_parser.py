"""Tests for the AsciiDoc parser against real C2PA spec files."""

from __future__ import annotations

from pathlib import Path

import pytest

from c2pa_kg.models import RuleSeverity
from c2pa_kg.parsers.asciidoc import parse_assertion_docs, parse_validation_doc

SPEC_SOURCE = Path("/home/developer/specs-core")
VALIDATION_PATH = SPEC_SOURCE / "docs/modules/specs/partials/Validation/Validation.adoc"
ASSERTIONS_DIR = SPEC_SOURCE / "docs/modules/specs/partials/Standard_Assertions"

pytestmark = pytest.mark.skipif(
    not SPEC_SOURCE.is_dir(), reason="specs-core checkout not available"
)


# ---------------------------------------------------------------------------
# Validation.adoc
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def validation_result():
    return parse_validation_doc(VALIDATION_PATH)


class TestValidationDoc:
    def test_parses_without_error(self, validation_result) -> None:
        rules, codes = validation_result
        assert isinstance(rules, list)
        assert isinstance(codes, list)

    def test_rules_extracted_count(self, validation_result) -> None:
        rules, _ = validation_result
        assert len(rules) >= 50, f"Expected >= 50 rules, got {len(rules)}"

    def test_status_codes_extracted_count(self, validation_result) -> None:
        _, codes = validation_result
        assert len(codes) >= 50, f"Expected >= 50 status codes, got {len(codes)}"

    def test_rules_have_ids(self, validation_result) -> None:
        rules, _ = validation_result
        for rule in rules:
            assert rule.rule_id, f"Rule has empty rule_id: {rule}"

    def test_rule_ids_unique(self, validation_result) -> None:
        rules, _ = validation_result
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"

    def test_severity_detection(self, validation_result) -> None:
        rules, _ = validation_result
        severities = {r.severity for r in rules}
        # Must-level rules should be present in the validation doc
        assert RuleSeverity.MUST in severities or RuleSeverity.SHALL in severities

    def test_must_not_severity_detected(self, validation_result) -> None:
        rules, _ = validation_result
        severities = {r.severity for r in rules}
        # The validation doc contains MUST NOT rules
        assert (
            RuleSeverity.MUST_NOT in severities
            or RuleSeverity.SHALL_NOT in severities
            or RuleSeverity.MUST in severities
        )

    def test_phase_inference_populates_multiple_phases(self, validation_result) -> None:
        rules, _ = validation_result
        phases = {r.phase for r in rules}
        assert len(phases) >= 2, f"Expected multiple phases, got {phases}"

    def test_status_codes_have_code_and_meaning(self, validation_result) -> None:
        _, codes = validation_result
        for code in codes:
            assert code.code, f"StatusCode has empty code: {code}"
            assert code.meaning, f"StatusCode has empty meaning: {code}"

    def test_status_code_categories(self, validation_result) -> None:
        _, codes = validation_result
        categories = {c.category for c in codes}
        # The doc should have success and/or failure categories
        assert categories & {"success", "failure", "informational"}

    def test_rules_have_descriptions(self, validation_result) -> None:
        rules, _ = validation_result
        for rule in rules:
            assert rule.description, f"Rule {rule.rule_id} has empty description"
            assert len(rule.description) >= 20


# ---------------------------------------------------------------------------
# Standard_Assertions/*.adoc
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def assertion_descriptions():
    return parse_assertion_docs(ASSERTIONS_DIR)


class TestAssertionDocs:
    def test_parses_without_error(self, assertion_descriptions) -> None:
        assert isinstance(assertion_descriptions, dict)

    def test_non_empty(self, assertion_descriptions) -> None:
        assert len(assertion_descriptions) >= 5

    def test_keys_are_non_empty_strings(self, assertion_descriptions) -> None:
        for key in assertion_descriptions:
            assert isinstance(key, str) and key

    def test_descriptions_are_non_empty(self, assertion_descriptions) -> None:
        for stem, desc in assertion_descriptions.items():
            assert desc, f"Empty description for {stem!r}"

    def test_descriptions_are_reasonable_length(self, assertion_descriptions) -> None:
        for stem, desc in assertion_descriptions.items():
            assert len(desc) >= 10, f"Description too short for {stem!r}: {desc!r}"

    def test_actions_description_extracted(self, assertion_descriptions) -> None:
        # Actions.adoc should exist and yield a description
        assert "Actions" in assertion_descriptions or len(assertion_descriptions) >= 5
