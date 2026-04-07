"""JSON-LD context emitter for the C2PA knowledge graph.

Generates a JSON-LD @context document that maps C2PA entity and property names
to their IRIs, enabling JSON-LD framing of C2PA data structures.

The emitter reuses the rdflib graph from the Turtle emitter to ensure that
IRIs are exactly consistent between the two output formats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rdflib.namespace import OWL, RDF, RDFS, XSD

# Re-use the graph builder from the Turtle emitter
from c2pa_kg.models import (
    KnowledgeGraph,
    PropertyType,
)

# ---------------------------------------------------------------------------
# Standard namespace prefixes included in every context
# ---------------------------------------------------------------------------

_STANDARD_PREFIXES: dict[str, str] = {
    "c2pa": "https://c2pa.org/ontology/",
    "owl": str(OWL),
    "rdfs": str(RDFS),
    "rdf": str(RDF),
    "xsd": str(XSD),
    "dc": "http://purl.org/dc/terms/",
    "schema": "https://schema.org/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}

# ---------------------------------------------------------------------------
# Type coercion map: PropertyType -> JSON-LD @type keyword
# ---------------------------------------------------------------------------

_LD_TYPE_MAP: dict[PropertyType, str] = {
    PropertyType.STRING: "xsd:string",
    PropertyType.INTEGER: "xsd:integer",
    PropertyType.FLOAT: "xsd:decimal",
    PropertyType.BOOLEAN: "xsd:boolean",
    PropertyType.BYTES: "xsd:base64Binary",
    PropertyType.URI: "@id",
    PropertyType.DATETIME: "xsd:dateTime",
    PropertyType.REFERENCE: "@id",
    PropertyType.MAP: "@id",
}


def _prop_iri(entity_name: str, prop_name: str) -> str:
    """Return the full IRI string for a property."""
    safe_entity = entity_name.replace(" ", "_").replace(":", "_")
    safe_prop = (
        prop_name.replace(" ", "_")
        .replace(":", "_")
        .replace(".", "_")
        .replace("-", "_")
    )
    return f"https://c2pa.org/ontology/{safe_entity}.{safe_prop}"


def _entity_iri(name: str) -> str:
    """Return the full IRI string for an entity."""
    safe = name.replace(" ", "_").replace(":", "_").replace("/", "_")
    return f"https://c2pa.org/ontology/{safe}"


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _build_context(kg: KnowledgeGraph) -> dict[str, Any]:
    """Build the JSON-LD @context dictionary from a KnowledgeGraph."""
    context: dict[str, Any] = {}

    # Standard namespace prefixes
    context.update(_STANDARD_PREFIXES)

    # Set default vocabulary
    context["@vocab"] = "https://c2pa.org/ontology/"

    # Entity mappings: entity name -> IRI
    for entity_name in kg.entities:
        iri = _entity_iri(entity_name)
        context[entity_name] = {"@id": iri, "@type": "@id"}

    # Property mappings: property name -> IRI with type coercion
    # Properties are qualified by entity to avoid namespace clashes, but we
    # also emit unqualified short-form aliases for the most common names.
    seen_prop_names: dict[str, list[str]] = {}  # short_name -> [qualified_iris]

    for entity_name, entity in kg.entities.items():
        for prop in entity.properties:
            prop_iri = _prop_iri(entity_name, prop.name)

            # Fully-qualified key: EntityName.propName
            qualified_key = f"{entity_name}.{prop.name}"
            entry: dict[str, Any] = {"@id": prop_iri}

            ld_type = _LD_TYPE_MAP.get(prop.property_type)
            if ld_type:
                entry["@type"] = ld_type

            # Arrays in JSON-LD use @container: @set or @list
            from c2pa_kg.models import PropertyType
            if prop.property_type == PropertyType.ARRAY:
                entry["@container"] = "@list"

            context[qualified_key] = entry

            # Track short names for potential deduplication
            if prop.name not in seen_prop_names:
                seen_prop_names[prop.name] = []
            seen_prop_names[prop.name].append(prop_iri)

    # Short-form property aliases: emit when the short name is unambiguous
    # (all entities that have this property use the same IRI pattern)
    for short_name, iris in seen_prop_names.items():
        # Skip if already shadowed by an entity name
        if short_name in context:
            continue
        # Use the short form only when all IRIs share the same local fragment pattern
        # (i.e., the property name is unique across entity namespaces)
        unique_fragments = set(iri.rsplit(".", 1)[-1] for iri in iris)
        if len(unique_fragments) == 1:
            # The property name maps consistently; emit first IRI as the canonical
            context[short_name] = {"@id": iris[0]}

    # Enum type mappings
    for enum_name in kg.enum_types:
        iri = _entity_iri(enum_name)
        if enum_name not in context:
            context[enum_name] = {"@id": iri, "@type": "@id"}

    return {"@context": context}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def emit_jsonld_context(kg: KnowledgeGraph, output_path: Path) -> None:
    """Serialize the knowledge graph as a JSON-LD @context document.

    Args:
        kg: The knowledge graph to emit.
        output_path: Destination .jsonld file path.
    """
    context_doc = _build_context(kg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(context_doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
