"""Shared normative-text analysis for C2PA specification parsers.

Provides RFC 2119 severity detection, validation phase inference, and entity
reference extraction. Used by both the AsciiDoc and HTML parsers.
"""

from __future__ import annotations

import re

from c2pa_kg.models import RuleSeverity, ValidationPhase

# ---------------------------------------------------------------------------
# Severity mapping (RFC 2119 keywords)
# ---------------------------------------------------------------------------

SEVERITY_PATTERNS: list[tuple[re.Pattern[str], RuleSeverity]] = [
    (re.compile(r"\bmust not\b", re.IGNORECASE), RuleSeverity.MUST_NOT),
    (re.compile(r"\bshall not\b", re.IGNORECASE), RuleSeverity.SHALL_NOT),
    (re.compile(r"\bshould not\b", re.IGNORECASE), RuleSeverity.SHOULD_NOT),
    (re.compile(r"\bmust\b", re.IGNORECASE), RuleSeverity.MUST),
    (re.compile(r"\bshall\b", re.IGNORECASE), RuleSeverity.SHALL),
    (re.compile(r"\bshould\b", re.IGNORECASE), RuleSeverity.SHOULD),
    (re.compile(r"\bmay\b", re.IGNORECASE), RuleSeverity.MAY),
]


def detect_severity(text: str) -> RuleSeverity:
    """Return the strongest RFC 2119 keyword found in *text*."""
    for pattern, severity in SEVERITY_PATTERNS:
        if pattern.search(text):
            return severity
    return RuleSeverity.MAY


# ---------------------------------------------------------------------------
# Phase inference
# ---------------------------------------------------------------------------

PHASE_KEYWORDS: list[tuple[re.Pattern[str], ValidationPhase]] = [
    (
        re.compile(r"\bcryptograph|\bsignature\b|\bsigning\b|\bcose\b", re.IGNORECASE),
        ValidationPhase.CRYPTOGRAPHIC,
    ),
    (
        re.compile(r"\btrust\b|\btrust anchor\b|\btrust list\b", re.IGNORECASE),
        ValidationPhase.TRUST,
    ),
    (re.compile(r"\btime.?stamp\b|\btimestamp\b", re.IGNORECASE), ValidationPhase.TIMESTAMP),
    (re.compile(r"\bassertion\b", re.IGNORECASE), ValidationPhase.ASSERTION),
    (re.compile(r"\bingredient\b", re.IGNORECASE), ValidationPhase.INGREDIENT),
    (re.compile(r"\bcontent\b|\bbinding\b|\bhash\b", re.IGNORECASE), ValidationPhase.CONTENT),
    (
        re.compile(r"\bstructure\b|\bwell.formed\b|\bcbor\b|\bmalformed\b", re.IGNORECASE),
        ValidationPhase.STRUCTURAL,
    ),
]


def infer_phase(section: str, text: str) -> ValidationPhase:
    """Infer the validation phase from the section header and sentence text."""
    combined = section + " " + text
    for pattern, phase in PHASE_KEYWORDS:
        if pattern.search(combined):
            return phase
    return ValidationPhase.STRUCTURAL


# ---------------------------------------------------------------------------
# Entity reference extraction
# ---------------------------------------------------------------------------

BACKTICK_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_.\-]*)`")
CAMEL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
KNOWN_ENTITIES = {
    "claim",
    "manifest",
    "assertion",
    "ingredient",
    "signature",
    "timestamp",
    "credential",
    "trust",
    "hash",
    "actions",
    "softBinding",
    "thumbnail",
}


def extract_entities(text: str) -> list[str]:
    """Extract likely entity references from a sentence."""
    refs: list[str] = []
    for m in BACKTICK_RE.finditer(text):
        token = m.group(1)
        if "." in token or "_" in token or token[0].islower():
            refs.append(token)
    for m in CAMEL_RE.finditer(text):
        refs.append(m.group(1))
    return list(dict.fromkeys(refs))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Normative keyword detection
# ---------------------------------------------------------------------------

NORMATIVE_RE = re.compile(r"\b(shall|must|should|may)\b", re.IGNORECASE)


def has_normative_keyword(text: str) -> bool:
    """Return True if *text* contains an RFC 2119 normative keyword."""
    return bool(NORMATIVE_RE.search(text))


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into individual sentences."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]
