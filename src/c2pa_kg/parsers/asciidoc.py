"""Parse AsciiDoc files from the C2PA specification.

Two entry points:
- parse_validation_doc: Extract ValidationRule and StatusCode objects from Validation.adoc.
- parse_assertion_docs: Extract entity description strings from Standard_Assertions/*.adoc.

AsciiDoc conventions in C2PA v2.4:
- Section headers use `##` (level 2) through `#####` (level 5).
- Normative keywords appear in lower case (shall, must, should, may) within sentence text.
- Validation status code tables use the AsciiDoc table syntax:
    |`code.value`   |  Meaning text  | url_usage_text
  with the table delimited by `|=======================`.
- Categories are taken from the immediately preceding section header
  (Success/Informational/Failure).
"""

from __future__ import annotations

import re
from pathlib import Path

from c2pa_kg.models import RuleSeverity, StatusCode, ValidationPhase, ValidationRule

# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

_SEVERITY_PATTERNS: list[tuple[re.Pattern[str], RuleSeverity]] = [
    (re.compile(r"\bmust not\b", re.IGNORECASE), RuleSeverity.MUST_NOT),
    (re.compile(r"\bshall not\b", re.IGNORECASE), RuleSeverity.SHALL_NOT),
    (re.compile(r"\bshould not\b", re.IGNORECASE), RuleSeverity.SHOULD_NOT),
    (re.compile(r"\bmust\b", re.IGNORECASE), RuleSeverity.MUST),
    (re.compile(r"\bshall\b", re.IGNORECASE), RuleSeverity.SHALL),
    (re.compile(r"\bshould\b", re.IGNORECASE), RuleSeverity.SHOULD),
    (re.compile(r"\bmay\b", re.IGNORECASE), RuleSeverity.MAY),
]


def _detect_severity(text: str) -> RuleSeverity:
    """Return the strongest RFC 2119 keyword found in text."""
    for pattern, severity in _SEVERITY_PATTERNS:
        if pattern.search(text):
            return severity
    return RuleSeverity.MAY


# ---------------------------------------------------------------------------
# Phase inference
# ---------------------------------------------------------------------------

_PHASE_KEYWORDS: list[tuple[re.Pattern[str], ValidationPhase]] = [
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


def _infer_phase(section: str, text: str) -> ValidationPhase:
    """Infer the validation phase from the section header and sentence text."""
    combined = section + " " + text
    for pattern, phase in _PHASE_KEYWORDS:
        if pattern.search(combined):
            return phase
    return ValidationPhase.STRUCTURAL


# ---------------------------------------------------------------------------
# Entity reference extraction
# ---------------------------------------------------------------------------

# Extract entity-like tokens: backtick-quoted identifiers, CamelCase words
_BACKTICK_RE = re.compile(r"`([A-Za-z][A-Za-z0-9_.\-]*)`")
_CAMEL_RE = re.compile(r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b")
# Known C2PA entity tokens that map to model names
_KNOWN_ENTITIES = {
    "claim", "manifest", "assertion", "ingredient", "signature", "timestamp",
    "credential", "trust", "hash", "actions", "softBinding", "thumbnail",
}


def _extract_entities(text: str) -> list[str]:
    """Extract likely entity references from a sentence."""
    refs: list[str] = []
    for m in _BACKTICK_RE.finditer(text):
        token = m.group(1)
        # Keep tokens that look like field names or status codes
        if "." in token or "_" in token or token[0].islower():
            refs.append(token)
    for m in _CAMEL_RE.finditer(text):
        refs.append(m.group(1))
    return list(dict.fromkeys(refs))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Section header parsing
# ---------------------------------------------------------------------------

_HEADER_RE = re.compile(r"^(#{2,6})\s+(.+)$", re.MULTILINE)


def _parse_section_headers(text: str) -> list[tuple[int, int, str]]:
    """Return list of (line_offset, level, title) for each AsciiDoc section header."""
    headers: list[tuple[int, int, str]] = []
    for m in _HEADER_RE.finditer(text):
        level = len(m.group(1))
        title = m.group(2).strip()
        headers.append((m.start(), level, title))
    return headers


def _section_at(offset: int, headers: list[tuple[int, int, str]]) -> str:
    """Return the nearest preceding section header title for a given text offset."""
    title = ""
    for start, _level, h_title in headers:
        if start <= offset:
            title = h_title
        else:
            break
    return title


# ---------------------------------------------------------------------------
# Status code table parsing
# ---------------------------------------------------------------------------

_TABLE_DELIM_RE = re.compile(r"^\|={3,}", re.MULTILINE)
_TABLE_ROW_RE = re.compile(
    r"^\|`?([A-Za-z][A-Za-z0-9._\-]*)`?\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
# Match the section header that immediately precedes a table
_SUCCESS_RE = re.compile(r"\bsuccess\b", re.IGNORECASE)
_INFO_RE = re.compile(r"\binformational\b", re.IGNORECASE)
_FAILURE_RE = re.compile(r"\bfailure\b", re.IGNORECASE)


def _category_from_context(text_before: str) -> str:
    """Determine status code category from the text preceding a table."""
    # Look at the last ~200 chars before the table for a section header
    snippet = text_before[-300:] if len(text_before) > 300 else text_before
    if _FAILURE_RE.search(snippet):
        return "failure"
    if _INFO_RE.search(snippet):
        return "informational"
    if _SUCCESS_RE.search(snippet):
        return "success"
    return "unknown"


def _parse_status_code_tables(text: str) -> list[StatusCode]:
    """Extract all status code table entries from validation doc text."""
    codes: list[StatusCode] = []
    delimiters = list(_TABLE_DELIM_RE.finditer(text))
    # Tables come in pairs of delimiters
    i = 0
    while i + 1 < len(delimiters):
        start = delimiters[i].end()
        end = delimiters[i + 1].start()
        table_body = text[start:end]
        category = _category_from_context(text[: delimiters[i].start()])

        for row_m in _TABLE_ROW_RE.finditer(table_body):
            code_val = row_m.group(1).strip()
            meaning = row_m.group(2).strip()
            url_usage = row_m.group(3).strip()

            # Skip header row
            if code_val.lower() in ("value", "code"):
                continue

            # Clean AsciiDoc xref syntax from meaning and url_usage
            meaning = re.sub(r"xref:[^\[]+\[([^\]]+)\]", r"\1", meaning)
            url_usage = re.sub(r"xref:[^\[]+\[([^\]]+)\]", r"\1", url_usage)

            codes.append(StatusCode(
                code=code_val,
                meaning=meaning,
                url_usage=url_usage,
                category=category,
            ))
        i += 2
    return codes


# ---------------------------------------------------------------------------
# Normative sentence extraction
# ---------------------------------------------------------------------------

# Sentences end at period followed by space+capital or end of paragraph.
# We keep it simple: split on ". " boundaries.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

# Skip AsciiDoc directives and blank lines
_SKIP_LINE_RE = re.compile(
    r"^\s*(?:#|\[|include::|image::|NOTE:|TIP:|WARNING:|CAUTION:|IMPORTANT:|\.{1,3}\s|\[source)",
    re.IGNORECASE,
)

# Patterns that indicate normative requirements sentences
_NORMATIVE_RE = re.compile(
    r"\b(shall|must|should|may)\b",
    re.IGNORECASE,
)

# AsciiDoc markup to strip before storing source text
_ADOC_CLEANUP_RE = re.compile(
    r"xref:[^\[]+\[([^\]]*)\]|<<[^>]+>>|`([^`]+)`|\{[^}]+\}|\[\[[^\]]+\]\]",
)


def _clean_adoc(text: str) -> str:
    """Strip AsciiDoc markup, leaving readable plain text."""
    def _replace(m: re.Match[str]) -> str:
        return m.group(1) or m.group(2) or ""

    return _ADOC_CLEANUP_RE.sub(_replace, text).strip()


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into individual sentences."""
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(paragraph) if s.strip()]


def _parse_normative_rules(text: str) -> list[ValidationRule]:
    """Extract ValidationRule objects from normative text in the document."""
    headers = _parse_section_headers(text)
    rules: list[ValidationRule] = []
    rule_counter: dict[str, int] = {}

    # Split into paragraphs on blank lines
    paragraphs = re.split(r"\n\n+", text)
    # Track approximate offset for section lookup
    offset = 0

    for para in paragraphs:
        # Skip non-normative lines
        if _SKIP_LINE_RE.match(para.strip()):
            offset += len(para) + 2
            continue
        if not _NORMATIVE_RE.search(para):
            offset += len(para) + 2
            continue

        section = _section_at(offset, headers)
        phase = _infer_phase(section, para)
        phase_key = phase.value

        for sentence in _split_sentences(para):
            if not _NORMATIVE_RE.search(sentence):
                continue

            severity = _detect_severity(sentence)
            clean = _clean_adoc(sentence)
            if not clean or len(clean) < 20:
                continue

            rule_counter[phase_key] = rule_counter.get(phase_key, 0) + 1
            rule_id = f"VAL-{phase_key.upper()[:4]}-{rule_counter[phase_key]:04d}"

            entities = _extract_entities(sentence)

            rules.append(ValidationRule(
                rule_id=rule_id,
                description=clean[:500],  # cap description length
                severity=severity,
                phase=phase,
                condition="",
                action="",
                referenced_entities=entities[:10],
                spec_section=section,
                source_text=clean[:200],
            ))

        offset += len(para) + 2

    return rules


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_validation_doc(
    validation_path: Path,
) -> tuple[list[ValidationRule], list[StatusCode]]:
    """Parse a C2PA Validation.adoc file.

    Extracts:
    - ValidationRule objects from normative sentences (shall/must/should/may).
    - StatusCode objects from the standard status code tables.

    Args:
        validation_path: Path to Validation.adoc.

    Returns:
        Tuple of (list[ValidationRule], list[StatusCode]).
    """
    text = validation_path.read_text(encoding="utf-8")

    status_codes = _parse_status_code_tables(text)
    rules = _parse_normative_rules(text)

    return rules, status_codes


def parse_assertion_docs(assertions_dir: Path) -> dict[str, str]:
    """Extract entity descriptions from Standard_Assertions AsciiDoc files.

    Each .adoc file begins with a description section. This function reads the
    first non-header paragraph of each file and indexes it by the assertion's
    inferred entity name (derived from the filename).

    Args:
        assertions_dir: Path to the Standard_Assertions directory.

    Returns:
        Dict mapping entity name (CamelCase) to description string.
    """
    descriptions: dict[str, str] = {}

    for adoc_file in sorted(assertions_dir.glob("*.adoc")):
        stem = adoc_file.stem  # e.g. "Actions", "DataHash", "Ingredient"
        text = adoc_file.read_text(encoding="utf-8")

        # Find the "#### Description" (or "==== Description") section header
        # and grab the first paragraph of body text after it
        desc_match = re.search(
            r"(?:#{2,6}|={2,6})\s*Description\s*\n+(.*?)(?=\n\n|\n#{2,6}|\n={2,6}|\Z)",
            text,
            re.DOTALL,
        )
        if desc_match:
            raw = desc_match.group(1).strip()
        else:
            # Fall back: first non-header, non-blank paragraph
            paras = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
            raw = ""
            for para in paras:
                if (
                    not para.startswith("=")
                    and not para.startswith("#")
                    and not para.startswith("[")
                    and len(para) > 30
                ):
                    raw = para
                    break

        if raw:
            clean = _clean_adoc(raw)
            # Collapse whitespace
            clean = re.sub(r"\s+", " ", clean).strip()
            descriptions[stem] = clean

    return descriptions
