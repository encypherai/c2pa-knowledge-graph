"""Parse JSON Schema files (crJSON) into IR Entity and Property objects.

The crJSON schema uses JSON Schema 2020-12 with a flat `definitions` map containing
~49 named type definitions linked by `$ref`. Each object definition becomes an Entity;
its `properties` become Property objects. `required` arrays determine which properties
are required. `$ref` links become REFERENCE properties. Union types (`oneOf`/`anyOf`)
become UNION properties.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from c2pa_kg.models import (
    Cardinality,
    Entity,
    Property,
    PropertyType,
    Relationship,
    RelationshipType,
)

# ---------------------------------------------------------------------------
# JSON Schema type mapping
# ---------------------------------------------------------------------------

_JSON_TYPE_MAP: dict[str, PropertyType] = {
    "string": PropertyType.STRING,
    "integer": PropertyType.INTEGER,
    "number": PropertyType.FLOAT,
    "boolean": PropertyType.BOOLEAN,
    "object": PropertyType.MAP,
    "array": PropertyType.ARRAY,
    "null": PropertyType.ANY,
}

# Well-known format hints
_FORMAT_MAP: dict[str, PropertyType] = {
    "uri": PropertyType.URI,
    "date-time": PropertyType.DATETIME,
    "date": PropertyType.DATETIME,
}


def _ref_to_name(ref: str) -> str:
    """Convert a JSON Schema $ref to a definition name.

    '#/definitions/someType' -> 'someType'
    """
    return ref.rsplit("/", 1)[-1]


def _infer_prop_type(schema: dict[str, Any]) -> tuple[PropertyType, str, str, list[str]]:
    """Return (PropertyType, reference_target, array_item_type, enum_values).

    Handles: type, $ref, oneOf/anyOf, enum, format, items.
    """
    # Direct $ref
    if "$ref" in schema:
        target = _ref_to_name(schema["$ref"])
        return PropertyType.REFERENCE, target, "", []

    # oneOf / anyOf union
    if "oneOf" in schema or "anyOf" in schema:
        choices = schema.get("oneOf", schema.get("anyOf", []))
        # If all choices are $ref -> still UNION but capture first ref
        refs = [_ref_to_name(c["$ref"]) for c in choices if "$ref" in c]
        if refs:
            return PropertyType.UNION, refs[0], "", []
        return PropertyType.UNION, "", "", []

    # Explicit enum
    if "enum" in schema:
        return PropertyType.ENUM, "", "", [str(v) for v in schema["enum"]]

    json_type = schema.get("type", "")

    # format override
    fmt = schema.get("format", "")
    if fmt in _FORMAT_MAP:
        return _FORMAT_MAP[fmt], "", "", []

    if json_type == "array":
        items = schema.get("items", {})
        if "$ref" in items:
            item_type = _ref_to_name(items["$ref"])
            return PropertyType.ARRAY, "", item_type, []
        if "type" in items:
            item_pt = _JSON_TYPE_MAP.get(items["type"], PropertyType.ANY)
            return PropertyType.ARRAY, "", item_pt.value, []
        return PropertyType.ARRAY, "", "", []

    if json_type:
        pt = _JSON_TYPE_MAP.get(json_type, PropertyType.ANY)
        return pt, "", "", []

    return PropertyType.ANY, "", "", []


def _cardinality_for(
    prop_name: str, prop_schema: dict[str, Any], required_set: set[str]
) -> Cardinality:
    """Return cardinality for a property."""
    required = prop_name in required_set
    json_type = prop_schema.get("type", "")
    if json_type == "array":
        min_items = prop_schema.get("minItems", 0)
        if required and min_items >= 1:
            return Cardinality.ONE_OR_MORE
        if not required and min_items >= 1:
            return Cardinality.ZERO_OR_MORE
        if required:
            return Cardinality.ONE_OR_MORE
        return Cardinality.ZERO_OR_MORE
    return Cardinality.ONE if required else Cardinality.ZERO_OR_ONE


def _extract_pattern(prop_schema: dict[str, Any]) -> str:
    return prop_schema.get("pattern", "")


def _build_entity(
    def_name: str,
    def_schema: dict[str, Any],
    source: str,
) -> Entity | None:
    """Build an Entity from a JSON Schema definition object.

    Returns None if the definition is not an object type (e.g. a primitive alias).
    """
    schema_type = def_schema.get("type", "")
    has_properties = "properties" in def_schema
    has_oneof = "oneOf" in def_schema or "anyOf" in def_schema

    # Only object definitions (with properties, or oneOf of objects) become Entities
    if schema_type not in ("object", "") and not has_oneof:
        return None
    if not has_properties and not has_oneof:
        return None

    description = def_schema.get("description", "")
    required_fields: set[str] = set(def_schema.get("required", []))

    entity = Entity(
        name=def_name,
        description=description,
        properties=[],
        relationships=[],
        source=source,
        aliases=[],
    )

    properties_schema = def_schema.get("properties", {})
    for prop_name, prop_schema in properties_schema.items():
        pt, ref_target, arr_item, enum_vals = _infer_prop_type(prop_schema)
        cardinality = _cardinality_for(prop_name, prop_schema, required_fields)
        required = prop_name in required_fields

        prop_desc = prop_schema.get("description", "")
        # If the prop_schema itself has a nested description via $ref, use existing
        pattern = _extract_pattern(prop_schema)

        prop = Property(
            name=prop_name,
            property_type=pt,
            description=prop_desc,
            required=required,
            cardinality=cardinality,
            reference_target=ref_target,
            array_item_type=arr_item,
            enum_values=enum_vals,
            pattern=pattern,
            source=source,
        )
        entity.properties.append(prop)

    # oneOf/anyOf at the definition level: add a UNION property named "value"
    # (used for discriminated union types like locatorMap)
    if has_oneof and not has_properties:
        choices = def_schema.get("oneOf", def_schema.get("anyOf", []))
        refs = [_ref_to_name(c.get("$ref", "")) for c in choices if "$ref" in c]
        if refs:
            # Create a synthetic property representing the union
            prop = Property(
                name="_union",
                property_type=PropertyType.UNION,
                description=f"One of: {', '.join(refs)}",
                required=True,
                cardinality=Cardinality.ONE,
                reference_target=refs[0],
                source=source,
            )
            entity.properties.append(prop)

    # Build REFERENCE relationships for properties that reference other definitions
    for prop in entity.properties:
        if prop.property_type in (PropertyType.REFERENCE, PropertyType.UNION):
            if prop.reference_target:
                rel = Relationship(
                    name=prop.name,
                    source_entity=def_name,
                    target_entity=prop.reference_target,
                    relationship_type=RelationshipType.REFERENCES,
                    description=prop.description,
                    cardinality=prop.cardinality,
                )
                entity.relationships.append(rel)
        elif prop.property_type == PropertyType.ARRAY and prop.array_item_type:
            # Check if item type looks like a definition name (starts with uppercase)
            item = prop.array_item_type
            if item and item[0].isupper():
                rel = Relationship(
                    name=prop.name,
                    source_entity=def_name,
                    target_entity=item,
                    relationship_type=RelationshipType.HAS_MANY,
                    description=prop.description,
                    cardinality=prop.cardinality,
                )
                entity.relationships.append(rel)

    return entity


def _extract_root_entity(schema: dict[str, Any], source: str) -> Entity | None:
    """Extract the root (document-level) entity from the top-level schema object."""
    if schema.get("type") != "object":
        return None
    title = schema.get("title", "crJSONDocument")
    # Sanitize title to a valid entity name
    entity_name = re.sub(r"[^A-Za-z0-9]", "", title) or "CrJSONDocument"
    description = schema.get("description", "")
    required_fields: set[str] = set(schema.get("required", []))

    entity = Entity(
        name=entity_name,
        description=description,
        properties=[],
        relationships=[],
        source=source,
    )

    for prop_name, prop_schema in schema.get("properties", {}).items():
        pt, ref_target, arr_item, enum_vals = _infer_prop_type(prop_schema)
        cardinality = _cardinality_for(prop_name, prop_schema, required_fields)
        required = prop_name in required_fields
        prop_desc = prop_schema.get("description", "")
        pattern = _extract_pattern(prop_schema)

        prop = Property(
            name=prop_name,
            property_type=pt,
            description=prop_desc,
            required=required,
            cardinality=cardinality,
            reference_target=ref_target,
            array_item_type=arr_item,
            enum_values=enum_vals,
            pattern=pattern,
            source=source,
        )
        entity.properties.append(prop)

        if pt in (PropertyType.REFERENCE, PropertyType.UNION) and ref_target:
            rel = Relationship(
                name=prop_name,
                source_entity=entity_name,
                target_entity=ref_target,
                relationship_type=RelationshipType.REFERENCES,
                description=prop_desc,
                cardinality=cardinality,
            )
            entity.relationships.append(rel)

    return entity


def parse_json_schema(schema_path: Path) -> list[Entity]:
    """Parse a JSON Schema file into a list of Entity objects.

    Each object definition in `definitions` becomes an Entity.
    The root schema object (if type=object) also becomes an Entity.

    Args:
        schema_path: Path to the JSON Schema file (e.g. crJSON.schema.json).

    Returns:
        List of Entity objects extracted from the schema.
    """
    raw = schema_path.read_text(encoding="utf-8")
    schema = json.loads(raw)
    source = schema_path.name

    entities: list[Entity] = []

    # Root document entity
    root_entity = _extract_root_entity(schema, source)
    if root_entity is not None:
        entities.append(root_entity)

    # Definitions
    definitions = schema.get("definitions", {})
    for def_name, def_schema in definitions.items():
        entity = _build_entity(def_name, def_schema, source)
        if entity is not None:
            entities.append(entity)

    return entities
