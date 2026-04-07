"""Parse CDDL schema files into IR Entity, Property, Relationship, and EnumType objects.

C2PA uses CDDL (Concise Data Definition Language, RFC 8610) to define its data structures.
This parser handles the patterns present in the C2PA v2.4 specification schemas.

Strategy:
- Use cddlparser for AST-based extraction of map definitions and type-choice plugs.
- Fall back to regex for comment extraction and patterns the AST does not expose cleanly.
- Produce Entity (for map definitions) and EnumType (for socket/plug choices) objects.

Key cddlparser AST facts (from empirical testing against C2PA CDDL files):
- Map rule type_node: rule.type is a Type wrapping a single Map node.
- Occurrence for `?`: n=0, m=inf, tokens=[QUEST].
- Occurrence for `*`: n=0, m=inf, tokens=[ASTERISK].
- Occurrence for `1*`: n=1, m=inf, tokens=[NUMBER, ASTERISK].
- No occurrence marker on required fields (occurrence=None).
- Inline comments (`; text`) appear in mk.type.comments (the key's Typename node).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import cddlparser
from cddlparser import ast as cddl_ast
from cddlparser.tokens import Tokens

from c2pa_kg.models import (
    Cardinality,
    Entity,
    EnumType,
    Property,
    PropertyType,
    Relationship,
    RelationshipType,
)

# ---------------------------------------------------------------------------
# Prelude / type mapping
# ---------------------------------------------------------------------------

_PRELUDE_MAP: dict[str, PropertyType] = {
    "tstr": PropertyType.STRING,
    "text": PropertyType.STRING,
    "bstr": PropertyType.BYTES,
    "bytes": PropertyType.BYTES,
    "uint": PropertyType.INTEGER,
    "nint": PropertyType.INTEGER,
    "int": PropertyType.INTEGER,
    "integer": PropertyType.INTEGER,
    "unsigned": PropertyType.INTEGER,
    "float": PropertyType.FLOAT,
    "float16": PropertyType.FLOAT,
    "float32": PropertyType.FLOAT,
    "float64": PropertyType.FLOAT,
    "float16-32": PropertyType.FLOAT,
    "float32-64": PropertyType.FLOAT,
    "bool": PropertyType.BOOLEAN,
    "true": PropertyType.BOOLEAN,
    "false": PropertyType.BOOLEAN,
    "tdate": PropertyType.DATETIME,
    "time": PropertyType.DATETIME,
    "uri": PropertyType.URI,
    "any": PropertyType.ANY,
    "nil": PropertyType.ANY,
    "null": PropertyType.ANY,
    "undefined": PropertyType.ANY,
}

# Named type aliases used in C2PA schemas that resolve to STRING
_STRING_ALIASES = {
    "jumbf-uri-type",
    "format-string",
    "semver-string",
}


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

def _hyphen_to_camel(name: str) -> str:
    """Convert cddl-style-name or cddl_style_name to CamelCaseName."""
    parts = re.split(r"[-_]", name)
    return "".join(p.capitalize() for p in parts if p)


def _strip_socket_prefix(name: str) -> str:
    """Remove leading $ (socket) or ~ (unwrap) characters."""
    return name.lstrip("$~")


# ---------------------------------------------------------------------------
# Occurrence helpers
# ---------------------------------------------------------------------------

def _occurrence_is_optional(occ: cddl_ast.Occurrence) -> bool:
    """Return True when the occurrence is `?` (QUEST token, n=0 m=inf with single token)."""
    tokens = occ.tokens
    return len(tokens) == 1 and tokens[0].type == Tokens.QUEST


def _occurrence_is_zero_or_more(occ: cddl_ast.Occurrence) -> bool:
    """Return True for `*` (ASTERISK only, n=0 m=inf)."""
    tokens = occ.tokens
    return len(tokens) == 1 and tokens[0].type == Tokens.ASTERISK


def _occurrence_is_one_or_more(occ: cddl_ast.Occurrence) -> bool:
    """Return True for `1*` (NUMBER + ASTERISK, n=1 m=inf)."""
    tokens = occ.tokens
    return (
        len(tokens) == 2
        and tokens[0].type == Tokens.NUMBER
        and tokens[1].type == Tokens.ASTERISK
        and occ.n >= 1
    )


def _map_entry_cardinality(
    outer_occ: cddl_ast.Occurrence | None,
    array_inner_occ: cddl_ast.Occurrence | None,
) -> tuple[bool, Cardinality]:
    """Return (required, Cardinality) for a map entry.

    outer_occ: occurrence marker on the map entry itself (? makes it optional).
    array_inner_occ: occurrence marker inside [1* item] or [* item] arrays.
    """
    optional = outer_occ is not None and _occurrence_is_optional(outer_occ)
    required = not optional

    if array_inner_occ is not None:
        if _occurrence_is_one_or_more(array_inner_occ):
            return required, (Cardinality.ONE_OR_MORE if required else Cardinality.ZERO_OR_MORE)
        if _occurrence_is_zero_or_more(array_inner_occ):
            return required, Cardinality.ZERO_OR_MORE

    if optional:
        return False, Cardinality.ZERO_OR_ONE
    return True, Cardinality.ONE


# ---------------------------------------------------------------------------
# Comment extraction
# ---------------------------------------------------------------------------

# Comment extraction uses regex on raw text rather than AST node traversal.
# cddlparser attaches inline comments (`;`) to the _following_ token, not the
# token they trail. Regex on the source is simpler and more reliable.

# Matches: (optional ?) "field_name": <type_expression>, ; comment
# The type expression may contain any non-semicolon characters including nested parens.
_FIELD_COMMENT_RE = re.compile(
    r'"([^"]+)"\s*[^;]*;\s*([^\n]+)',
    re.MULTILINE,
)


def _build_comment_index(raw_text: str) -> dict[str, str]:
    """Build a dict mapping field_name -> first non-empty inline comment.

    When a field name appears in multiple map definitions within one file,
    the first occurrence's comment is used. For CDDL files with a single map,
    this is always correct. For multi-map files (e.g. ingredient.cddl), the
    first definition's comments win for shared field names.
    """
    index: dict[str, str] = {}
    for m in _FIELD_COMMENT_RE.finditer(raw_text):
        key = m.group(1)
        comment = m.group(2).strip()
        # Skip regex pattern keys like ^\w+/...
        if key.startswith("^") or key.startswith("\\"):
            continue
        if key not in index and comment:
            index[key] = comment
    return index


def _extract_map_comment(raw_text: str, map_name: str) -> str:
    """Extract leading semicolon comment block before a map definition."""
    # Match one or more comment lines immediately before `name-map =` or `name-map-v2 =`
    pattern = rf"((?:(?:^|(?<=\n))\s*;[^\n]*\n)+)\s*{re.escape(map_name)}\s*="
    m = re.search(pattern, raw_text)
    if not m:
        return ""
    comment_block = m.group(1)
    lines = []
    for ln in comment_block.strip().splitlines():
        stripped = ln.strip().lstrip(";").strip()
        if stripped:
            lines.append(stripped)
    return " ".join(lines)


# ---------------------------------------------------------------------------
# Type inference from AST nodes
# ---------------------------------------------------------------------------

def _infer_property_type(type_node: Any) -> tuple[PropertyType, str, str]:
    """Return (PropertyType, reference_target, array_item_type).

    reference_target is non-empty when PropertyType.REFERENCE.
    array_item_type is non-empty when PropertyType.ARRAY.
    """
    if isinstance(type_node, cddl_ast.Type):
        inner_types = type_node.types
        if len(inner_types) == 1:
            return _infer_property_type(inner_types[0])
        # Multiple alternatives -> UNION; capture first reference target
        refs = []
        for t in inner_types:
            pt, ref, arr = _infer_property_type(t)
            if ref:
                refs.append(ref)
        return PropertyType.UNION, refs[0] if refs else "", ""

    if isinstance(type_node, cddl_ast.Operator):
        # e.g. tstr .size (1..max-tstr-length) or tstr .regexp "..."
        # The base type is the left operand; the operator constrains it.
        return _infer_property_type(type_node.type)

    if isinstance(type_node, cddl_ast.Range):
        return PropertyType.INTEGER, "", ""

    if isinstance(type_node, cddl_ast.Value):
        if type_node.type == "text":
            return PropertyType.STRING, "", ""
        if type_node.type in ("bytes", "hex", "base64"):
            return PropertyType.BYTES, "", ""
        if type_node.type == "number":
            return PropertyType.INTEGER, "", ""
        return PropertyType.ANY, "", ""

    if isinstance(type_node, cddl_ast.Typename):
        raw_name = type_node.name
        name = _strip_socket_prefix(raw_name)
        if name in _PRELUDE_MAP:
            return _PRELUDE_MAP[name], "", ""
        if name in _STRING_ALIASES:
            return PropertyType.STRING, "", ""
        return PropertyType.REFERENCE, _hyphen_to_camel(name), ""

    if isinstance(type_node, cddl_ast.Array):
        # Determine item type and find any inner occurrence
        item_type = ""
        for gc in type_node.groupChoices:
            for entry in gc.groupEntries:
                pt, ref, _ = _infer_property_type(entry.type)
                if pt == PropertyType.REFERENCE:
                    item_type = ref
                else:
                    item_type = pt.value
                break
            break
        return PropertyType.ARRAY, "", item_type

    if isinstance(type_node, cddl_ast.Map):
        return PropertyType.MAP, "", ""

    if isinstance(type_node, cddl_ast.Group):
        return PropertyType.MAP, "", ""

    if isinstance(type_node, cddl_ast.Tag):
        # CBOR tag e.g. #6.37(bstr) -> treat as bytes
        return PropertyType.BYTES, "", ""

    if isinstance(type_node, cddl_ast.ChoiceFrom):
        return PropertyType.ENUM, "", ""

    return PropertyType.ANY, "", ""


def _get_array_inner_occurrence(type_node: Any) -> cddl_ast.Occurrence | None:
    """Extract the inner occurrence from an array type node (e.g. `[1* item]`)."""
    if isinstance(type_node, cddl_ast.Type):
        if len(type_node.types) == 1:
            return _get_array_inner_occurrence(type_node.types[0])
        return None
    if isinstance(type_node, cddl_ast.Array):
        for gc in type_node.groupChoices:
            for entry in gc.groupEntries:
                return entry.occurrence
    return None


def _get_operator_constraints(type_node: Any) -> tuple[str, int | None]:
    """Extract (pattern, min_length) from a .size/.regexp operator node."""
    pattern = ""
    min_len: int | None = None

    def _walk(node: Any) -> None:
        nonlocal pattern, min_len
        if isinstance(node, cddl_ast.Operator):
            op_tokens = [tok for tok in [node.name] if tok]
            op_name = op_tokens[0].literal if op_tokens else ""
            if not op_name and hasattr(node.name, "type"):
                op_name = str(node.name.type)
            # Check for .size
            if "size" in op_name.lower() or "SIZE" in op_name:
                ctrl = node.controller
                if isinstance(ctrl, cddl_ast.Range):
                    min_node = ctrl.min
                    if isinstance(min_node, cddl_ast.Value) and min_node.value.isdigit():
                        min_len = int(min_node.value)
            # Check for .regexp / .pcre
            elif "regexp" in op_name.lower() or "pcre" in op_name.lower():
                ctrl = node.controller
                if isinstance(ctrl, cddl_ast.Value):
                    pattern = ctrl.value
            _walk(node.type)
        elif isinstance(node, cddl_ast.Type):
            for t in node.types:
                _walk(t)

    _walk(type_node)
    return pattern, min_len


# ---------------------------------------------------------------------------
# Socket/plug enum extraction (regex-based)
# ---------------------------------------------------------------------------

_PLUG_RE = re.compile(r"^\$([A-Za-z0-9_-]+)\s*/=\s*(.+?)(?:\s*;.*)?$", re.MULTILINE)


def _extract_enums_from_text(text: str, source: str) -> list[EnumType]:
    """Extract all socket/plug enum types from raw CDDL text using regex."""
    enums: dict[str, EnumType] = {}
    for m in _PLUG_RE.finditer(text):
        socket_name = m.group(1)
        value_text = m.group(2).strip().rstrip(",")
        camel_name = _hyphen_to_camel(socket_name)
        if camel_name not in enums:
            enums[camel_name] = EnumType(
                name=camel_name,
                values=[],
                extensible=False,
                description="",
                source=source,
            )
        enum = enums[camel_name]
        str_m = re.match(r'^"([^"]+)"$', value_text)
        if str_m:
            enum.values.append(str_m.group(1))
        else:
            # Non-literal value (e.g. tstr .regexp ...) -> extensible
            enum.extensible = True
    return list(enums.values())


# ---------------------------------------------------------------------------
# Helpers for map entries
# ---------------------------------------------------------------------------

def _is_wildcard_entry(entry: cddl_ast.GroupEntry) -> bool:
    """Return True for wildcard catch-all entries like `* tstr => any`."""
    mk = entry.key
    if mk is None:
        return False
    key_type = mk.type
    if isinstance(key_type, cddl_ast.Typename) and key_type.name in ("tstr", "text", "any"):
        # Has no meaningful key name - it's a wildcard
        return True
    return False


def _is_group_inclusion(entry: cddl_ast.GroupEntry) -> str | None:
    """Return the CDDL name of a group included without a key (e.g. `action-common-map-v2,`).

    In CDDL, a group entry with no key and type Typename is a group inclusion.
    We only detect named map-like groups (containing '-map').
    """
    if entry.key is not None:
        return None
    t = entry.type
    if isinstance(t, cddl_ast.Type):
        types = t.types
        if len(types) == 1 and isinstance(types[0], cddl_ast.Typename):
            name = types[0].name
            if not name.startswith("$") and ("-map" in name or "_map" in name):
                return name
    return None


def _key_string(entry: cddl_ast.GroupEntry) -> str | None:
    """Return the string key of a map entry, or None if not a string key."""
    mk = entry.key
    if mk is None:
        return None
    key_type = mk.type
    if isinstance(key_type, cddl_ast.Value) and key_type.type == "text":
        return key_type.value
    if isinstance(key_type, cddl_ast.Typename):
        return key_type.name
    return None


# ---------------------------------------------------------------------------
# Map rule -> Entity
# ---------------------------------------------------------------------------

def _unwrap_map(type_node: Any) -> cddl_ast.Map | None:
    """Unwrap a Type or Map node to the underlying Map, or return None."""
    if isinstance(type_node, cddl_ast.Map):
        return type_node
    if isinstance(type_node, cddl_ast.Type):
        if len(type_node.types) == 1:
            return _unwrap_map(type_node.types[0])
    return None


def _process_map_rule(
    rule: cddl_ast.Rule,
    raw_text: str,
    source: str,
) -> Entity | None:
    """Convert a CDDL map rule to an Entity, or None if not a map definition."""
    map_node = _unwrap_map(rule.type)
    if map_node is None:
        return None

    cddl_name = rule.name.name
    # Strip socket prefix ($) from rule names like $hashed-uri-map
    clean_cddl_name = _strip_socket_prefix(cddl_name)
    camel_name = _hyphen_to_camel(clean_cddl_name)
    description = _extract_map_comment(raw_text, cddl_name)
    deprecated = "(DEPRECATED)" in description or "DEPRECATED" in description

    # Build comment index for this map's field names from raw text
    comment_index = _build_comment_index(raw_text)

    entity = Entity(
        name=camel_name,
        description=description.replace("(DEPRECATED)", "").strip(),
        properties=[],
        relationships=[],
        source=source,
        deprecated=deprecated,
        aliases=[cddl_name],
    )

    for group_choice in map_node.groupChoices:
        for entry in group_choice.groupEntries:
            # Wildcard catch-all (`* tstr => any`) - skip
            if _is_wildcard_entry(entry):
                continue

            # Group inclusion (`some-common-map,`) - add extends relationship
            included_name = _is_group_inclusion(entry)
            if included_name is not None:
                rel = Relationship(
                    name="includes",
                    source_entity=camel_name,
                    target_entity=_hyphen_to_camel(included_name),
                    relationship_type=RelationshipType.EXTENDS,
                    description=f"Inherits fields from {included_name}",
                    cardinality=Cardinality.ONE,
                )
                entity.relationships.append(rel)
                continue

            field_name = _key_string(entry)
            if field_name is None:
                continue

            # Determine optionality from the outer occurrence marker
            outer_occ = entry.occurrence
            array_inner_occ = _get_array_inner_occurrence(entry.type)
            required, cardinality = _map_entry_cardinality(outer_occ, array_inner_occ)

            # Infer property type
            pt, ref_target, arr_item = _infer_property_type(entry.type)

            # Extract constraints from operators
            pattern, min_len = _get_operator_constraints(entry.type)

            # Extract inline comment from the regex index (more reliable than AST)
            comment = comment_index.get(field_name, "")
            prop_deprecated = "(DEPRECATED)" in comment or "(deprecated)" in comment.lower()
            clean_comment = re.sub(r"\(DEPRECATED\)", "", comment, flags=re.IGNORECASE).strip()

            prop = Property(
                name=field_name,
                property_type=pt,
                description=clean_comment,
                required=required,
                cardinality=cardinality,
                reference_target=ref_target,
                array_item_type=arr_item,
                pattern=pattern,
                min_length=min_len,
                max_length=None,
                deprecated=prop_deprecated,
                source=source,
            )
            entity.properties.append(prop)

            # Add relationship for reference properties
            if pt in (PropertyType.REFERENCE, PropertyType.UNION) and ref_target:
                rel_type = (
                    RelationshipType.HAS_MANY
                    if cardinality in (Cardinality.ONE_OR_MORE, Cardinality.ZERO_OR_MORE)
                    else RelationshipType.REFERENCES
                )
                rel = Relationship(
                    name=field_name,
                    source_entity=camel_name,
                    target_entity=ref_target,
                    relationship_type=rel_type,
                    description=clean_comment,
                    cardinality=cardinality,
                )
                entity.relationships.append(rel)

    return entity


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_cddl_file(cddl_path: Path) -> tuple[list[Entity], list[EnumType]]:
    """Parse a single CDDL file into Entities and EnumTypes.

    Uses cddlparser for map definitions and regex for socket/plug enum types.

    Args:
        cddl_path: Path to the .cddl file.

    Returns:
        Tuple of (list[Entity], list[EnumType]).
    """
    text = cddl_path.read_text(encoding="utf-8")
    source = cddl_path.name

    entities: list[Entity] = []
    enums: list[EnumType] = []

    # Extract enums via regex (socket/plug patterns cddlparser handles differently)
    enums.extend(_extract_enums_from_text(text, source))

    # Parse AST
    try:
        tree = cddlparser.parse(text)
    except Exception:
        # Fall through with empty entity list if parse fails
        return entities, enums

    for rule in tree.rules:
        entity = _process_map_rule(rule, text, source)
        if entity is not None:
            entities.append(entity)

    return entities, enums


def parse_cddl_directory(cddl_dir: Path) -> tuple[list[Entity], list[EnumType]]:
    """Parse all CDDL files in a directory into a merged set of Entities and EnumTypes.

    Entity names are unique; if two files define the same entity name, they are merged
    (first definition wins for the description; later files add any missing properties).
    EnumType values are merged across files (union of all values).

    Args:
        cddl_dir: Path to the directory containing .cddl files.

    Returns:
        Tuple of (list[Entity], list[EnumType]).
    """
    all_entities: dict[str, Entity] = {}
    all_enums: dict[str, EnumType] = {}

    for cddl_file in sorted(cddl_dir.glob("*.cddl")):
        file_entities, file_enums = parse_cddl_file(cddl_file)

        for entity in file_entities:
            if entity.name in all_entities:
                existing = all_entities[entity.name]
                if not existing.description and entity.description:
                    existing.description = entity.description
                existing_prop_names = {p.name for p in existing.properties}
                for prop in entity.properties:
                    if prop.name not in existing_prop_names:
                        existing.properties.append(prop)
                existing_rel_keys = {(r.name, r.target_entity) for r in existing.relationships}
                for rel in entity.relationships:
                    if (rel.name, rel.target_entity) not in existing_rel_keys:
                        existing.relationships.append(rel)
            else:
                all_entities[entity.name] = entity

        for enum in file_enums:
            if enum.name in all_enums:
                existing_enum = all_enums[enum.name]
                for v in enum.values:
                    if v not in existing_enum.values:
                        existing_enum.values.append(v)
                if enum.extensible:
                    existing_enum.extensible = True
            else:
                all_enums[enum.name] = enum

    return list(all_entities.values()), list(all_enums.values())
