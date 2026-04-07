"""Validation rules JSON emitter for the C2PA knowledge graph.

Serializes all ValidationRule and StatusCode objects from a KnowledgeGraph
into a structured JSON document grouped by phase and status code category.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from c2pa_kg.models import (
    KnowledgeGraph,
    RuleSeverity,
    StatusCode,
    ValidationPhase,
    ValidationRule,
)

# ---------------------------------------------------------------------------
# Severity ordering for display (most restrictive first)
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[RuleSeverity, int] = {
    RuleSeverity.MUST: 0,
    RuleSeverity.SHALL: 1,
    RuleSeverity.MUST_NOT: 2,
    RuleSeverity.SHALL_NOT: 3,
    RuleSeverity.SHOULD: 4,
    RuleSeverity.SHOULD_NOT: 5,
    RuleSeverity.MAY: 6,
}

# Status code categories emitted in the output
_STATUS_CATEGORIES = ("success", "failure", "informational", "unknown")


# ---------------------------------------------------------------------------
# Rule serialisation helpers
# ---------------------------------------------------------------------------

def _rule_to_dict(rule: ValidationRule) -> dict[str, Any]:
    """Serialise a ValidationRule to a plain dict for JSON output."""
    d: dict[str, Any] = {
        "rule_id": rule.rule_id,
        "description": rule.description,
        "severity": rule.severity.value,
        "phase": rule.phase.value,
        "spec_section": rule.spec_section,
    }
    if rule.condition:
        d["condition"] = rule.condition
    if rule.action:
        d["action"] = rule.action
    if rule.referenced_entities:
        d["referenced_entities"] = rule.referenced_entities
    if rule.source_text and rule.source_text != rule.description:
        d["source_text"] = rule.source_text
    return d


def _status_code_to_dict(code: StatusCode) -> dict[str, Any]:
    """Serialise a StatusCode to a plain dict for JSON output."""
    d: dict[str, Any] = {
        "code": code.code,
        "meaning": code.meaning,
    }
    if code.url_usage and code.url_usage not in ("(multiple)", "(not applicable)"):
        d["url_usage"] = code.url_usage
    return d


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------

def _group_rules_by_phase(
    rules: list[ValidationRule],
) -> dict[str, list[dict[str, Any]]]:
    """Group rules by ValidationPhase, sorted by severity within each phase."""
    phases: dict[str, list[ValidationRule]] = {}
    for rule in rules:
        key = rule.phase.value
        phases.setdefault(key, []).append(rule)

    result: dict[str, list[dict[str, Any]]] = {}
    # Emit phases in a consistent order matching ValidationPhase enum definition
    for phase in ValidationPhase:
        phase_rules = phases.get(phase.value, [])
        if not phase_rules:
            continue
        sorted_rules = sorted(phase_rules, key=lambda r: _SEVERITY_ORDER.get(r.severity, 99))
        result[phase.value] = [_rule_to_dict(r) for r in sorted_rules]

    return result


def _group_status_codes(
    codes: list[StatusCode],
) -> dict[str, list[dict[str, Any]]]:
    """Group status codes by category."""
    grouped: dict[str, list[StatusCode]] = {cat: [] for cat in _STATUS_CATEGORIES}
    for code in codes:
        cat = code.category if code.category in grouped else "unknown"
        grouped[cat].append(code)

    result: dict[str, list[dict[str, Any]]] = {}
    for cat in _STATUS_CATEGORIES:
        cat_codes = grouped[cat]
        if not cat_codes:
            continue
        # Sort alphabetically by code value for deterministic output
        sorted_codes = sorted(cat_codes, key=lambda c: c.code)
        result[cat] = [_status_code_to_dict(c) for c in sorted_codes]

    return result


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------

def _build_summary(rules: list[ValidationRule]) -> dict[str, Any]:
    """Build a summary dict of rule counts by phase and severity."""
    by_phase: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for rule in rules:
        by_phase[rule.phase.value] = by_phase.get(rule.phase.value, 0) + 1
        by_severity[rule.severity.value] = by_severity.get(rule.severity.value, 0) + 1
    return {
        "total": len(rules),
        "by_phase": by_phase,
        "by_severity": by_severity,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit_rules_json(kg: KnowledgeGraph, output_path: Path) -> None:
    """Serialize all validation rules and status codes to a JSON file.

    Output structure:
    {
      "version": "2.4",
      "rule_count": N,
      "summary": { "total": N, "by_phase": {...}, "by_severity": {...} },
      "phases": {
        "structural": [ ...rules... ],
        "cryptographic": [ ...rules... ],
        ...
      },
      "status_codes": {
        "success": [ ...codes... ],
        "failure": [ ...codes... ],
        "informational": [ ...codes... ]
      }
    }

    Args:
        kg: The knowledge graph containing rules and status codes.
        output_path: Destination .json file path.
    """
    phases = _group_rules_by_phase(kg.validation_rules)
    status_codes = _group_status_codes(kg.status_codes)
    summary = _build_summary(kg.validation_rules)

    document: dict[str, Any] = {
        "version": kg.version.version,
        "rule_count": kg.rule_count,
        "summary": summary,
        "phases": phases,
        "status_codes": status_codes,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(document, f, indent=2, ensure_ascii=False)
        f.write("\n")
