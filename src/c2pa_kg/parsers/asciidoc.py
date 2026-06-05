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

from c2pa_kg.models import StatusCode, ValidationRule
from c2pa_kg.parsers._normative import (
    detect_severity,
    extract_entities,
    has_normative_keyword,
    infer_phase,
    split_sentences,
)

# Backward-compatible private aliases used within this module.
_detect_severity = detect_severity
_infer_phase = infer_phase
_extract_entities = extract_entities


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

_INCLUDE_RE = re.compile(r"^include::([^\[]+)\[[^\]]*\]\s*$", re.MULTILINE)


def _resolve_adoc_includes(path: Path, *, seen: frozenset[Path] = frozenset()) -> str:
    """Read an AsciiDoc file and inline relative ``include::*.adoc[]`` files.

    The validation clause is split across partials, and the status-code tables
    put their rows in included files. Non-AsciiDoc includes, such as CDDL source
    snippets, are intentionally dropped from the parsed text: they are examples
    or schemas, not normative prose for this parser.
    """
    resolved = path.resolve()
    if resolved in seen:
        return ""
    seen = seen | {resolved}
    text = path.read_text(encoding="utf-8")

    def _replace(match: re.Match[str]) -> str:
        include_target = match.group(1).strip()
        include_path = (path.parent / include_target).resolve()
        if include_path.suffix.lower() != ".adoc" or not include_path.is_file():
            return ""
        return _resolve_adoc_includes(include_path, seen=seen)

    return _INCLUDE_RE.sub(_replace, text)


def _read_validation_adoc(validation_path: Path) -> str:
    """Read Validation.adoc with validation partials and status-code annex."""
    text = _resolve_adoc_includes(validation_path)
    annex = validation_path.with_name("ValidationCodes_Annex.adoc")
    if annex.is_file():
        text = f"{text}\n\n{_resolve_adoc_includes(annex)}"
    return text


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

            codes.append(
                StatusCode(
                    code=code_val,
                    meaning=meaning,
                    url_usage=url_usage,
                    category=category,
                )
            )
        i += 2
    return codes


# ---------------------------------------------------------------------------
# Normative sentence extraction
# ---------------------------------------------------------------------------

# Skip AsciiDoc directives and blank lines
_SKIP_LINE_RE = re.compile(
    r"^\s*(?:#|\[|include::|image::|NOTE:|TIP:|WARNING:|CAUTION:|IMPORTANT:|\.{1,3}\s|\[source)",
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


_split_sentences = split_sentences


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
        if not has_normative_keyword(para):
            offset += len(para) + 2
            continue

        section = _section_at(offset, headers)
        phase = _infer_phase(section, para)
        phase_key = phase.value

        for sentence in _split_sentences(para):
            if not has_normative_keyword(sentence):
                continue

            severity = _detect_severity(sentence)
            clean = _clean_adoc(sentence)
            if not clean or len(clean) < 20:
                continue

            rule_counter[phase_key] = rule_counter.get(phase_key, 0) + 1
            rule_id = f"VAL-{phase_key.upper()[:4]}-{rule_counter[phase_key]:04d}"

            entities = _extract_entities(sentence)

            rules.append(
                ValidationRule(
                    rule_id=rule_id,
                    description=clean[:500],  # cap description length
                    severity=severity,
                    phase=phase,
                    condition="",
                    action="",
                    referenced_entities=entities[:10],
                    spec_section=section,
                    source_text=clean[:200],
                )
            )

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
    text = _read_validation_adoc(validation_path)

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
