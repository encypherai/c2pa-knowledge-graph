"""Tests for the HTML spec parser against the real C2PA 2.4 rendered page.

The HTML file at /tmp/c2pa_spec_2.4.html is the rendered C2PA 2.4 spec from
spec.c2pa.org. Tests compare the HTML parser output against known KG data
(versions/2.4/metadata.json) to verify accuracy and coverage.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from c2pa_kg.models import RuleSeverity, ValidationPhase
from c2pa_kg.parsers.html_spec import (
    parse_html_spec,
    parse_html_status_codes,
    parse_html_validation_rules,
)

HTML_PATH = Path("/tmp/c2pa_spec_2.4.html")
KG_METADATA = Path("/home/developer/code/c2pa-knowledge-graph/versions/2.4/metadata.json")

pytestmark = pytest.mark.skipif(not HTML_PATH.is_file(), reason="C2PA 2.4 HTML not downloaded")


@pytest.fixture(scope="module")
def html_text() -> str:
    return HTML_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def status_codes(html_text):
    return parse_html_status_codes(html_text)


@pytest.fixture(scope="module")
def validation_rules(html_text):
    return parse_html_validation_rules(html_text)


@pytest.fixture(scope="module")
def kg_data() -> dict:
    if not KG_METADATA.is_file():
        pytest.skip("KG metadata not available")
    return json.loads(KG_METADATA.read_text())


# -----------------------------------------------------------------------
# Status code tests
# -----------------------------------------------------------------------


class TestStatusCodes:
    def test_parses_without_error(self, status_codes) -> None:
        assert isinstance(status_codes, list)

    def test_total_count(self, status_codes) -> None:
        # HTML has 115 status codes: 16 success + 15 informational + 84 failure.
        assert len(status_codes) == 115, f"Expected 115 status codes, got {len(status_codes)}"

    def test_success_count(self, status_codes) -> None:
        success = [c for c in status_codes if c.category == "success"]
        assert len(success) == 16

    def test_informational_count(self, status_codes) -> None:
        info = [c for c in status_codes if c.category == "informational"]
        assert len(info) == 15

    def test_failure_count(self, status_codes) -> None:
        fail = [c for c in status_codes if c.category == "failure"]
        assert len(fail) == 84

    def test_all_categories_present(self, status_codes) -> None:
        categories = {c.category for c in status_codes}
        assert categories == {"success", "informational", "failure"}

    def test_codes_have_required_fields(self, status_codes) -> None:
        for code in status_codes:
            assert code.code, f"StatusCode has empty code: {code}"
            assert code.meaning, f"StatusCode has empty meaning for {code.code}"
            assert code.category, f"StatusCode has empty category for {code.code}"

    def test_no_duplicate_codes(self, status_codes) -> None:
        code_values = [c.code for c in status_codes]
        assert len(code_values) == len(set(code_values)), (
            f"Duplicate codes found: {[c for c in code_values if code_values.count(c) > 1]}"
        )

    def test_finds_asciidoc_missing_codes(self, status_codes) -> None:
        """The AsciiDoc parser misses these 2 codes due to a regex bug."""
        code_set = {c.code for c in status_codes}
        assert "assertion.alternativeContentRepresentation.hashMismatch" in code_set
        assert "assertion.alternativeContentRepresentation.missing" in code_set

    def test_code_format_valid(self, status_codes) -> None:
        """All codes should match the dotted identifier pattern."""
        import re

        pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9._-]+$")
        for code in status_codes:
            assert pattern.match(code.code), f"Invalid code format: {code.code!r}"

    def test_superset_of_kg(self, status_codes, kg_data) -> None:
        """HTML parser should find at least every unique code in the KG."""
        html_codes = {c.code for c in status_codes}
        kg_codes = {c["code"] for c in kg_data["status_codes"]}
        # KG has a duplicate (assertion.cbor.invalid), so deduplicate.
        missing = kg_codes - html_codes
        assert not missing, f"KG codes not found in HTML: {missing}"

    def test_known_codes_present(self, status_codes) -> None:
        """Spot-check representative codes from each category."""
        code_set = {c.code for c in status_codes}
        # Success
        assert "claimSignature.validated" in code_set
        assert "timeStamp.validated" in code_set
        # Informational
        assert "algorithm.deprecated" in code_set
        assert "signingCredential.ocsp.skipped" in code_set
        # Failure
        assert "claim.missing" in code_set
        assert "signingCredential.untrusted" in code_set
        assert "livevideo.segment.invalid" in code_set


# -----------------------------------------------------------------------
# Validation rule tests
# -----------------------------------------------------------------------


class TestValidationRules:
    def test_parses_without_error(self, validation_rules) -> None:
        assert isinstance(validation_rules, list)

    def test_rule_count_reasonable(self, validation_rules) -> None:
        # The AsciiDoc parser produces 237 rules. The HTML parser should
        # be in the same ballpark. Allow a range since extraction from
        # rendered HTML may differ slightly.
        assert 180 <= len(validation_rules) <= 350, (
            f"Expected 180-350 rules, got {len(validation_rules)}"
        )

    def test_rule_ids_unique(self, validation_rules) -> None:
        ids = [r.rule_id for r in validation_rules]
        assert len(ids) == len(set(ids)), "Duplicate rule IDs found"

    def test_rule_id_format(self, validation_rules) -> None:
        import re

        pattern = re.compile(r"^VAL-[A-Z]{4}-\d{4}$")
        for rule in validation_rules:
            assert pattern.match(rule.rule_id), f"Invalid rule ID format: {rule.rule_id!r}"

    def test_rules_have_descriptions(self, validation_rules) -> None:
        for rule in validation_rules:
            assert rule.description, f"Rule {rule.rule_id} has empty description"
            assert len(rule.description) >= 20, (
                f"Rule {rule.rule_id} description too short: {rule.description!r}"
            )

    def test_severity_detection(self, validation_rules) -> None:
        severities = {r.severity for r in validation_rules}
        assert RuleSeverity.SHALL in severities, "No SHALL rules found"

    def test_multiple_severities_present(self, validation_rules) -> None:
        severities = {r.severity for r in validation_rules}
        assert len(severities) >= 3, f"Expected 3+ severities, got {severities}"

    def test_phase_inference_covers_multiple_phases(self, validation_rules) -> None:
        phases = {r.phase for r in validation_rules}
        assert len(phases) >= 4, f"Expected 4+ phases, got {phases}"

    def test_key_phases_present(self, validation_rules) -> None:
        phases = {r.phase for r in validation_rules}
        assert ValidationPhase.ASSERTION in phases
        assert ValidationPhase.CRYPTOGRAPHIC in phases
        assert ValidationPhase.CONTENT in phases

    def test_rules_have_spec_sections(self, validation_rules) -> None:
        with_section = [r for r in validation_rules if r.spec_section]
        assert len(with_section) > len(validation_rules) * 0.8, (
            "Most rules should have a spec_section"
        )

    def test_entity_references_extracted(self, validation_rules) -> None:
        with_entities = [r for r in validation_rules if r.referenced_entities]
        coverage = len(with_entities) / len(validation_rules)
        assert coverage == 1.0, (
            f"Expected 100% entity ref coverage, got {coverage:.1%} "
            f"({len(validation_rules) - len(with_entities)} rules without refs)"
        )

    def test_no_admonition_text_in_rules(self, validation_rules) -> None:
        """Rules should not contain admonition/note text markers."""
        for rule in validation_rules:
            desc_lower = rule.description.lower()
            assert "icon-note" not in desc_lower
            assert "admonitionblock" not in desc_lower


# -----------------------------------------------------------------------
# Integration test
# -----------------------------------------------------------------------


class TestParseHtmlSpec:
    def test_convenience_wrapper(self, html_text) -> None:
        rules, codes = parse_html_spec(html_text)
        assert len(rules) > 100
        assert len(codes) > 100
