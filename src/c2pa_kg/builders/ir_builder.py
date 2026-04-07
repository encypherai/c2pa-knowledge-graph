"""IR builder: merges CDDL, JSON Schema, and AsciiDoc parser outputs into a KnowledgeGraph.

The build_knowledge_graph function is the single entry point. It:
1. Calls the CDDL parser on the spec cddl/ directory (normative source of truth for entities).
2. Calls the JSON Schema parser on crJSON-schema.json (supplements descriptions).
3. Calls the AsciiDoc parser on Validation.adoc and Standard_Assertions/*.adoc.
4. Merges results: CDDL entities are primary; JSON Schema fills gaps in descriptions.
5. Infers structural relationships between entities from property references.
6. Populates validation rules, status codes, and enum types.
"""

from __future__ import annotations

import re
from pathlib import Path

from c2pa_kg.models import (
    Cardinality,
    Entity,
    KnowledgeGraph,
    PropertyType,
    Relationship,
    RelationshipType,
    SpecVersion,
    TypeAlias,
)
from c2pa_kg.parsers.asciidoc import parse_assertion_docs, parse_validation_doc
from c2pa_kg.parsers.cddl import parse_cddl_directory
from c2pa_kg.parsers.json_schema import parse_json_schema

# ---------------------------------------------------------------------------
# Spec path constants (relative to the spec source root)
# ---------------------------------------------------------------------------

_CDDL_SUBPATH = "docs/modules/specs/partials/schemas/cddl"
_CRJSON_SUBPATH = "docs/modules/crJSON/partials/crJSON.schema.json"
_VALIDATION_SUBPATH = "docs/modules/specs/partials/Validation/Validation.adoc"
_ASSERTIONS_SUBPATH = "docs/modules/specs/partials/Standard_Assertions"


# ---------------------------------------------------------------------------
# Relationship inference
# ---------------------------------------------------------------------------

# These entity name patterns map to cardinality HAS_MANY via their property types.
_MANY_ARRAY_CARDINALITIES = {Cardinality.ZERO_OR_MORE, Cardinality.ONE_OR_MORE}


def _normalize_references(kg: KnowledgeGraph) -> None:
    """Normalize all reference_target and array_item_type values to match entity/enum names.

    JSON Schema uses camelCase (`regionMap`) while CDDL entities are PascalCase (`RegionMap`).
    This pass builds a case-insensitive lookup and fixes all mismatches in-place.
    """
    # Build case-insensitive index: lowercase -> canonical name
    canonical: dict[str, str] = {}
    for name in kg.entities:
        canonical[name.lower()] = name
    for name in kg.enum_types:
        canonical[name.lower()] = name

    def _fix(target: str) -> str:
        if not target:
            return target
        if target in kg.entities or target in kg.enum_types:
            return target
        resolved = canonical.get(target.lower())
        if resolved:
            return resolved
        return target

    for entity in kg.entities.values():
        for prop in entity.properties:
            prop.reference_target = _fix(prop.reference_target)
            prop.array_item_type = _fix(prop.array_item_type)


def _infer_relationships(kg: KnowledgeGraph) -> None:
    """Walk all entities and add cross-entity Relationship objects for REFERENCE properties.

    Rules:
    - REFERENCE property pointing to a known entity -> HAS_ONE (or HAS_MANY if array)
    - ARRAY property whose item type matches a known entity -> HAS_MANY
    - Property named 'parent' or with 'ingredient' -> BELONGS_TO or REFERENCES
    - Entities whose name ends in 'Map' or 'List' referencing another entity -> REFERENCES
    """
    entity_names: set[str] = set(kg.entities)

    # Normalise a reference target to see if it matches a known entity
    def _resolve(target: str) -> str | None:
        if target in entity_names:
            return target
        # Try CamelCase conversion from hyphenated name
        camel = _hyphen_to_camel(target)
        if camel in entity_names:
            return camel
        # Try PascalCase (capitalize first letter of camelCase)
        if target and target[0].islower():
            pascal = target[0].upper() + target[1:]
            if pascal in entity_names:
                return pascal
        # Try stripping trailing 'Map' suffix
        if target.endswith("Map") and target[:-3] in entity_names:
            return target[:-3]
        return None

    already_added: set[tuple[str, str, str]] = set()

    for entity_name, entity in list(kg.entities.items()):
        for prop in entity.properties:
            if prop.deprecated:
                continue

            target_name: str | None = None
            rel_type = RelationshipType.REFERENCES
            cardinality = prop.cardinality

            if prop.property_type == PropertyType.REFERENCE and prop.reference_target:
                target_name = _resolve(prop.reference_target)
                if cardinality in _MANY_ARRAY_CARDINALITIES:
                    rel_type = RelationshipType.HAS_MANY
                else:
                    rel_type = RelationshipType.HAS_ONE

            elif prop.property_type == PropertyType.ARRAY and prop.array_item_type:
                item = prop.array_item_type
                target_name = _resolve(item)
                if target_name:
                    rel_type = RelationshipType.HAS_MANY
                    cardinality = Cardinality.ZERO_OR_MORE

            if target_name is None:
                continue

            # Special-case 'parent' / 'ingredient' field names
            pname_lower = prop.name.lower().replace("_", "").replace("-", "")
            if "parent" in pname_lower or "ingredient" in pname_lower:
                rel_type = RelationshipType.BELONGS_TO

            key = (entity_name, target_name, prop.name)
            if key in already_added:
                continue
            already_added.add(key)

            rel = Relationship(
                name=prop.name,
                source_entity=entity_name,
                target_entity=target_name,
                relationship_type=rel_type,
                description=prop.description,
                cardinality=cardinality,
            )
            # Add to the global list only (not to entity.relationships to avoid
            # duplication with relationships already added by the parsers)
            kg.relationships.append(rel)


def _hyphen_to_camel(name: str) -> str:
    """Convert kebab-case or snake_case to CamelCase."""
    parts = re.split(r"[-_]", name)
    return "".join(p.capitalize() for p in parts if p)


# ---------------------------------------------------------------------------
# Entity merging
# ---------------------------------------------------------------------------

def _merge_json_schema_descriptions(
    kg: KnowledgeGraph,
    js_entities: list[Entity],
) -> None:
    """Supplement CDDL entity descriptions with JSON Schema descriptions.

    JSON Schema is secondary: it fills in description fields that CDDL left blank.
    It also adds entities not present in CDDL (e.g. the crJSON document root).
    """
    js_by_name: dict[str, Entity] = {e.name: e for e in js_entities}

    for name, entity in kg.entities.items():
        # Try exact match
        js_entity = js_by_name.get(name)
        if js_entity is None:
            # Try case-insensitive or alias match
            for js_name, js_e in js_by_name.items():
                if js_name.lower() == name.lower():
                    js_entity = js_e
                    break

        if js_entity is None:
            continue

        # Fill missing entity description
        if not entity.description and js_entity.description:
            entity.description = js_entity.description

        # Supplement property descriptions
        js_props_by_name = {p.name: p for p in js_entity.properties}
        for prop in entity.properties:
            if not prop.description:
                js_prop = js_props_by_name.get(prop.name)
                if js_prop and js_prop.description:
                    prop.description = js_prop.description

    # Add JSON Schema entities that have no CDDL equivalent
    for js_entity in js_entities:
        if js_entity.name not in kg.entities:
            # Only add if it has meaningful properties
            if js_entity.properties:
                js_entity.source = js_entity.source or "crJSON-schema.json"
                kg.add_entity(js_entity)


def _merge_assertion_descriptions(
    kg: KnowledgeGraph,
    assertion_descriptions: dict[str, str],
) -> None:
    """Use AsciiDoc assertion doc descriptions to fill in entity descriptions."""
    for stem, description in assertion_descriptions.items():
        # Stem is already CamelCase (from filename): e.g. "Actions", "DataHash"
        if stem in kg.entities:
            entity = kg.entities[stem]
            if not entity.description:
                entity.description = description
        else:
            # Try matching with 'Assertion' suffix or prefix
            for suffix in ("Assertion", "Map", ""):
                candidate = stem + suffix
                if candidate in kg.entities and not kg.entities[candidate].description:
                    kg.entities[candidate].description = description
                    break


# ---------------------------------------------------------------------------
# Type alias capture
# ---------------------------------------------------------------------------

# Known external types referenced by CDDL but defined in other standards
_EXTERNAL_TYPES: dict[str, str] = {
    "CoseSign1": "COSE_Sign1 structure (RFC 9052)",
    "CoseKey": "COSE_Key structure (RFC 9052)",
}

# Base type mapping for common CDDL prelude and tagged types
_ALIAS_BASE_TYPES: dict[str, str] = {
    "tstr": "string",
    "text": "string",
    "bstr": "bytes",
    "bytes": "bytes",
    "int": "integer",
    "uint": "integer",
    "float": "float",
    "float16": "float",
    "float32": "float",
    "float64": "float",
    "bool": "boolean",
    "nil": "null",
    "null": "null",
    "any": "any",
}


def _build_type_aliases(kg: KnowledgeGraph) -> None:
    """Find all unresolved reference targets and create TypeAlias entries.

    Walks entity properties to find reference_target and array_item_type values
    that don't resolve to any entity or enum. Captures them as type aliases
    so agents can look up what they mean.
    """
    known_names = set(kg.entities) | set(kg.enum_types)
    known_lower = {n.lower() for n in known_names}
    unresolved: set[str] = set()

    # PropertyType value strings that appear as array_item_type -- not real types
    builtin_types = {pt.value for pt in PropertyType}

    for entity in kg.entities.values():
        for prop in entity.properties:
            for target in (prop.reference_target, prop.array_item_type):
                if (
                    target
                    and target not in known_names
                    and target.lower() not in known_lower
                    and target not in builtin_types
                ):
                    unresolved.add(target)

    for name in sorted(unresolved):
        if name in _EXTERNAL_TYPES:
            kg.add_type_alias(TypeAlias(
                name=name,
                base_type="external",
                description=_EXTERNAL_TYPES[name],
                external=True,
            ))
        else:
            # Infer base type from the name pattern
            name_lower = name.lower()
            if (
                "string" in name_lower
                or "url" in name_lower
                or "uri" in name_lower
                or "mime" in name_lower
                or "format" in name_lower
            ):
                base = "string"
            elif "range" in name_lower or "int" in name_lower or "size" in name_lower:
                base = "integer"
            elif "flag" in name_lower or "uuid" in name_lower:
                base = "bytes"
            elif "map" in name_lower or "group" in name_lower or "entry" in name_lower:
                base = "map"
            else:
                base = "string"  # safe default for CDDL tstr aliases
            kg.add_type_alias(TypeAlias(
                name=name,
                base_type=base,
                description="CDDL type alias (see spec source for constraints)",
            ))


# ---------------------------------------------------------------------------
# Spec conventions
# ---------------------------------------------------------------------------

def _build_spec_conventions(kg: KnowledgeGraph) -> None:
    """Populate spec_conventions with C2PA editorial and structural rules.

    These rules govern how the spec communicates requirements, how new
    assertions should be structured, and how CDDL schemas should be written.
    Derived from the C2PA specification editorial conventions.
    """
    kg.spec_conventions = {
        "normative_language": {
            "standard": "RFC 2119",
            "rules": [
                {
                    "keyword": "shall",
                    "meaning": "Absolute requirement. Equivalent to 'must'.",
                    "constraints": [
                        "Never use in informational, security, or threat analysis sections",
                        "Never use inside NOTE blocks",
                        "Same concept uses the same normative verb throughout the spec",
                    ],
                },
                {
                    "keyword": "should",
                    "meaning": "Recommended but exceptions exist with clear justification.",
                    "constraints": [
                        "Non-compliance must have clear justification",
                        "Do not use 'it is recommended that' -- use 'should' directly",
                    ],
                },
                {
                    "keyword": "may",
                    "meaning": "Truly optional behavior.",
                    "constraints": [
                        "Verify it does not mask a 'should'",
                        "Network access is always optional -- any retrieval uses 'may attempt'",
                    ],
                },
            ],
            "anti_patterns": [
                "'it is recommended that' -- replace with 'should'",
                "'it is required' -- replace with 'shall'",
                "Normative statements in NOTE blocks",
                "Normative hedging in requirement text",
            ],
        },
        "structural_placement": {
            "rules": [
                {
                    "section": "feature_definition",
                    "contains": "Mechanism description, data structures, CDDL schemas",
                    "must_not_contain": (
                        "Validation logic, security analysis, implementation guidance"
                    ),
                },
                {
                    "section": "validation",
                    "contains": "How to validate the mechanism, status codes, error conditions",
                    "must_not_contain": "Feature description, security analysis",
                },
                {
                    "section": "threats_harms",
                    "contains": "Security analysis, threat model, risk assessment",
                    "must_not_contain": "Normative requirements ('shall'), validation logic",
                },
            ],
            "principle": (
                "The feature section defines the mechanism. Validation and security sections"
                " define how to check it. Guidance does not belong in normative spec text."
            ),
        },
        "cddl_conventions": {
            "naming": (
                "kebab-case for all CDDL rule names (e.g. region-map, action-items-map-v2)"
            ),
            "extensibility": {
                "open_enum": "Socket/plug pattern: $name /= value",
                "open_group": "Double-dollar pattern: $$name //= group",
                "forward_compat": (
                    "Include '* tstr => any' wildcard in maps for forward compatibility"
                ),
            },
            "field_rules": [
                "Optional fields use '?' prefix",
                "String fields use '.size (1..max-tstr-length)' constraint",
                "URI fields reference $hashed-uri-map or jumbf-uri-type",
                "CBOR diagnostic examples must match schema field names, types, and structure",
                "Examples demonstrate the minimal valid case unless showing optional fields",
            ],
        },
        "new_assertion_checklist": [
            "Define data structure in feature section with CDDL schema",
            "Add assertion label to the assertion label registry",
            "Add validation rules to Validation.adoc specific assertion validation list",
            "Add all status codes to consolidated status code tables"
            " (success/informational/failure)",
            "Add security analysis to Threats_Harms.adoc if applicable",
            "Include CBOR diagnostic example matching the schema",
            "Verify extensibility: '* tstr => any' wildcard present",
        ],
        "semantic_terms": {
            "manifest": "The C2PA Manifest -- a signed collection of assertions about an asset",
            "manifest_store": "The container holding one or more manifests",
            "active_manifest": "The current (most recent) manifest in a manifest chain",
            "claim_generator": "The entity creating the manifest, not a software component",
            "validator": "The entity performing validation of a manifest",
            "trust": (
                "Claim signature verification against a trust list -- distinct from integrity"
            ),
            "integrity": "Hash verification of content bindings -- distinct from trust",
            "componentOf": "Parent-to-child relationship ONLY. Never describe as child-to-parent.",
            "parentOf": "The derived-from/predecessor relationship in Update Manifests",
        },
        "cross_reference_rules": [
            "Every new assertion must appear in the Specific Assertion Validation list",
            "Every new status code must appear in consolidated status code tables",
            "hashed-uri references must use $hashed-uri-map in CDDL",
            "Update Manifests have exactly one parentOf ingredient and no hard bindings",
            "Network access is ALWAYS optional -- retrieval must use 'may attempt'",
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_knowledge_graph(
    spec_source: Path,
    version: SpecVersion,
) -> KnowledgeGraph:
    """Build a complete KnowledgeGraph from C2PA specification source files.

    Args:
        spec_source: Root path of the specs-core repository checkout.
        version: SpecVersion metadata for the graph being built.

    Returns:
        Fully populated KnowledgeGraph.
    """
    kg = KnowledgeGraph(version=version)

    # ------------------------------------------------------------------
    # 1. CDDL: primary source of structural entity definitions
    # ------------------------------------------------------------------
    cddl_dir = spec_source / _CDDL_SUBPATH
    if cddl_dir.is_dir():
        cddl_entities, cddl_enums = parse_cddl_directory(cddl_dir)
        for entity in cddl_entities:
            kg.add_entity(entity)
        for enum_type in cddl_enums:
            kg.add_enum(enum_type)

    # ------------------------------------------------------------------
    # 2. JSON Schema: secondary source for descriptions and crJSON entities
    # ------------------------------------------------------------------
    crjson_path = spec_source / _CRJSON_SUBPATH
    js_entities: list[Entity] = []
    if crjson_path.is_file():
        js_entities = parse_json_schema(crjson_path)
        _merge_json_schema_descriptions(kg, js_entities)

    # ------------------------------------------------------------------
    # 3. AsciiDoc: validation rules, status codes, assertion descriptions
    # ------------------------------------------------------------------
    validation_path = spec_source / _VALIDATION_SUBPATH
    if validation_path.is_file():
        rules, status_codes = parse_validation_doc(validation_path)
        for rule in rules:
            kg.add_rule(rule)
        for code in status_codes:
            kg.status_codes.append(code)

    assertions_dir = spec_source / _ASSERTIONS_SUBPATH
    if assertions_dir.is_dir():
        assertion_descs = parse_assertion_docs(assertions_dir)
        _merge_assertion_descriptions(kg, assertion_descs)

    # ------------------------------------------------------------------
    # 4. Spec conventions (editorial and structural rules)
    # ------------------------------------------------------------------
    _build_spec_conventions(kg)

    # ------------------------------------------------------------------
    # 5. Capture type aliases for unresolved references
    # ------------------------------------------------------------------
    _build_type_aliases(kg)

    # ------------------------------------------------------------------
    # 6. Normalize reference targets (fix camelCase -> PascalCase mismatches)
    # ------------------------------------------------------------------
    _normalize_references(kg)

    # ------------------------------------------------------------------
    # 7. Infer cross-entity relationships from property references
    # ------------------------------------------------------------------
    _infer_relationships(kg)

    return kg
