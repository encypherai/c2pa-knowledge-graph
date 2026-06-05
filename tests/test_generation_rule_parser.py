"""Focused tests for claim-generator requirement extraction."""

from __future__ import annotations

from c2pa_kg.models import RuleApplicability
from c2pa_kg.parsers.html_spec import _infer_applicability, parse_html_generation_rules


def test_conditional_singular_claim_generator_is_detected() -> None:
    result = _infer_applicability(
        "When a claim generator is performing ingredient validation, it should "
        "add a specVersion key.",
        "5.1. Compatibility",
    )
    assert result == RuleApplicability.CLAIM_GENERATOR


def test_plural_validator_and_claim_generator_sentence_is_both() -> None:
    result = _infer_applicability(
        "Validators should still accept this label, but claim generators "
        "should not produce such a claim.",
        "10.1. Overview",
    )
    assert result == RuleApplicability.BOTH


def test_generic_credential_validation_sentence_is_not_claim_generator() -> None:
    result = _infer_applicability(
        "If present, the private credential store shall only apply to validating "
        "signed C2PA manifests, and shall not apply to validating time-stamps.",
        "14.4.3. Private Credential Storage",
    )
    assert result == RuleApplicability.UNSPECIFIED


def test_possessive_claim_generator_certificate_is_not_generator_actor() -> None:
    result = _infer_applicability(
        "To address the risk of the Claim Generator’s certificate getting "
        "revoked, the validator should check that the certificate is still valid.",
        "19.7.3. Verifiable Segment Info Validation",
    )
    assert result == RuleApplicability.VALIDATOR


def test_passive_requirement_in_construction_section_is_claim_generator() -> None:
    result = _infer_applicability(
        "The created_assertions field shall be present.",
        "10.3.2.1. Adding Assertions and Redactions",
    )
    assert result == RuleApplicability.CLAIM_GENERATOR


def test_generation_rules_have_spec_area_and_skip_generic_false_positive() -> None:
    html = (
        '<html><body>'
        '<h2 id="claims"><a href="#claims"></a>10. Claims</h2>'
        '<h3 id="adding-assertions"><a href="#adding-assertions"></a>'
        '10.3.2.1. Adding Assertions and Redactions</h3>'
        '<div class="paragraph"><p>'
        'The claim shall contain a created_assertions field.'
        '</p></div>'
        '<h2 id="trust"><a href="#trust"></a>14. Trust Model</h2>'
        '<h3 id="private-credential"><a href="#private-credential"></a>'
        '14.4.3. Private Credential Storage</h3>'
        '<div class="paragraph"><p>'
        'If present, the private credential store shall only apply to validating '
        'signed C2PA manifests, and shall not apply to validating time-stamps.'
        '</p></div>'
        '<h2 id="versioning"><a href="#versioning"></a>5. Versioning</h2>'
        '<h3 id="version-history"><a href="#version-history"></a>5.3. Version History</h3>'
        '<h4 id="version-24"><a href="#version-24"></a>5.3.1. 2.4 - April 2026</h4>'
        '<div class="paragraph"><p>'
        'Only allows a single claim generator, which must be the signer.'
        '</p></div>'
        '</body></html>'
    )

    rules = parse_html_generation_rules(html)

    assert len(rules) == 1
    assert rules[0].spec_area == "Claims"
    assert rules[0].spec_section == "10.3.2.1. Adding Assertions and Redactions"
    assert rules[0].applicability == RuleApplicability.CLAIM_GENERATOR
