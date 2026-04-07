"""RDF/OWL Turtle emitter for the C2PA knowledge graph.

Serializes a KnowledgeGraph to a Turtle (.ttl) file as an OWL ontology.

Namespace: https://c2pa.org/ontology/ (prefix c2pa)
- Each Entity -> owl:Class
- Each Property -> owl:DatatypeProperty (primitive) or owl:ObjectProperty (reference)
- Each Relationship -> owl:ObjectProperty with rdfs:domain and rdfs:range
- Enum types -> owl:Class with owl:oneOf individuals
- Cardinality constraints -> owl:Restriction where meaningful
- Deprecated entities/properties -> owl:deprecated true
"""

from __future__ import annotations

from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from c2pa_kg.models import (
    Cardinality,
    Entity,
    EnumType,
    KnowledgeGraph,
    Property,
    PropertyType,
    Relationship,
    RelationshipType,
)

# ---------------------------------------------------------------------------
# Namespace and IRI helpers
# ---------------------------------------------------------------------------

C2PA = Namespace("https://c2pa.org/ontology/")
DC = Namespace("http://purl.org/dc/terms/")
SCHEMA = Namespace("https://schema.org/")


_IRI_UNSAFE = str.maketrans({
    " ": "_", ":": "_", "/": "_", "`": "", '"': "", "'": "",
    "<": "", ">": "", "{": "", "}": "", "|": "", "\\": "", "^": "",
})


def _sanitize(name: str) -> str:
    """Strip characters that are invalid in IRIs."""
    return name.translate(_IRI_UNSAFE)


def _entity_iri(name: str) -> URIRef:
    """IRI for an entity (class) in the c2pa namespace."""
    return C2PA[_sanitize(name)]


def _property_iri(entity_name: str, prop_name: str) -> URIRef:
    """IRI for a property in the c2pa namespace, qualified by entity."""
    safe_prop = _sanitize(prop_name).replace(".", "_").replace("-", "_")
    return C2PA[f"{_sanitize(entity_name)}.{safe_prop}"]


def _rel_iri(rel_name: str, source: str) -> URIRef:
    """IRI for a relationship object property."""
    safe_rel = _sanitize(rel_name).replace(".", "_").replace("-", "_")
    return C2PA[f"{_sanitize(source)}.{safe_rel}"]


# ---------------------------------------------------------------------------
# Type mapping: PropertyType -> XSD datatype or OWL property type
# ---------------------------------------------------------------------------

_PRIMITIVE_TYPES = {
    PropertyType.STRING,
    PropertyType.INTEGER,
    PropertyType.FLOAT,
    PropertyType.BOOLEAN,
    PropertyType.BYTES,
    PropertyType.URI,
    PropertyType.DATETIME,
    PropertyType.ENUM,
    PropertyType.ANY,
    PropertyType.UNION,
}

_XSD_MAP: dict[PropertyType, URIRef] = {
    PropertyType.STRING: XSD.string,
    PropertyType.INTEGER: XSD.integer,
    PropertyType.FLOAT: XSD.decimal,
    PropertyType.BOOLEAN: XSD.boolean,
    PropertyType.BYTES: XSD.base64Binary,
    PropertyType.URI: XSD.anyURI,
    PropertyType.DATETIME: XSD.dateTime,
    PropertyType.ENUM: XSD.string,
    PropertyType.ANY: RDFS.Literal,
    PropertyType.UNION: RDFS.Literal,
}


def _xsd_range(prop: Property) -> URIRef:
    """Return the XSD or RDFS range for a datatype property."""
    return _XSD_MAP.get(prop.property_type, XSD.string)


def _is_object_property(prop: Property) -> bool:
    """Return True if this property should be an owl:ObjectProperty."""
    return prop.property_type in (PropertyType.REFERENCE, PropertyType.MAP)


# ---------------------------------------------------------------------------
# Cardinality constraint helpers
# ---------------------------------------------------------------------------

def _add_cardinality_restriction(
    g: Graph,
    class_uri: URIRef,
    prop_uri: URIRef,
    cardinality: Cardinality,
    required: bool,
) -> None:
    """Add owl:Restriction subClassOf triple for cardinality constraints."""
    if cardinality == Cardinality.ONE and required:
        # Exactly one: minCardinality 1, maxCardinality 1
        for min_max, val in [("minCardinality", 1), ("maxCardinality", 1)]:
            restriction = BNode()
            g.add((restriction, RDF.type, OWL.Restriction))
            g.add((restriction, OWL.onProperty, prop_uri))
            g.add((
                restriction, getattr(OWL, min_max), Literal(val, datatype=XSD.nonNegativeInteger)
            ))
            g.add((class_uri, RDFS.subClassOf, restriction))
    elif cardinality == Cardinality.ZERO_OR_ONE:
        restriction = BNode()
        g.add((restriction, RDF.type, OWL.Restriction))
        g.add((restriction, OWL.onProperty, prop_uri))
        g.add((restriction, OWL.maxCardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
        g.add((class_uri, RDFS.subClassOf, restriction))
    elif cardinality == Cardinality.ONE_OR_MORE:
        restriction = BNode()
        g.add((restriction, RDF.type, OWL.Restriction))
        g.add((restriction, OWL.onProperty, prop_uri))
        g.add((restriction, OWL.minCardinality, Literal(1, datatype=XSD.nonNegativeInteger)))
        g.add((class_uri, RDFS.subClassOf, restriction))
    # ZERO_OR_MORE has no constraint to add


# ---------------------------------------------------------------------------
# Entity -> owl:Class
# ---------------------------------------------------------------------------

def _add_entity(g: Graph, entity: Entity) -> None:
    """Add an owl:Class triple set for an entity."""
    class_uri = _entity_iri(entity.name)
    g.add((class_uri, RDF.type, OWL.Class))
    g.add((class_uri, RDFS.label, Literal(entity.name, lang="en")))

    if entity.description:
        g.add((class_uri, RDFS.comment, Literal(entity.description, lang="en")))

    if entity.deprecated:
        g.add((class_uri, OWL.deprecated, Literal(True, datatype=XSD.boolean)))

    if entity.spec_section:
        g.add((class_uri, RDFS.isDefinedBy, Literal(entity.spec_section)))

    if entity.parent:
        parent_uri = _entity_iri(entity.parent)
        g.add((class_uri, RDFS.subClassOf, parent_uri))

    for alias in entity.aliases:
        if alias != entity.name:
            g.add((class_uri, OWL.sameAs, _entity_iri(alias)))


# ---------------------------------------------------------------------------
# Property -> owl:DatatypeProperty / owl:ObjectProperty
# ---------------------------------------------------------------------------

def _add_property(g: Graph, entity: Entity, prop: Property) -> None:
    """Add property triples for a single Property on an entity."""
    prop_uri = _property_iri(entity.name, prop.name)
    class_uri = _entity_iri(entity.name)

    if _is_object_property(prop):
        g.add((prop_uri, RDF.type, OWL.ObjectProperty))
        if prop.reference_target:
            g.add((prop_uri, RDFS.range, _entity_iri(prop.reference_target)))
    elif prop.property_type == PropertyType.ARRAY:
        # Array properties: ObjectProperty if item type is a reference, else DatatypeProperty
        if prop.array_item_type and prop.array_item_type[0].isupper():
            g.add((prop_uri, RDF.type, OWL.ObjectProperty))
            g.add((prop_uri, RDFS.range, _entity_iri(prop.array_item_type)))
        else:
            g.add((prop_uri, RDF.type, OWL.DatatypeProperty))
            g.add((prop_uri, RDFS.range, XSD.string))
    else:
        g.add((prop_uri, RDF.type, OWL.DatatypeProperty))
        g.add((prop_uri, RDFS.range, _xsd_range(prop)))

    g.add((prop_uri, RDFS.domain, class_uri))
    g.add((prop_uri, RDFS.label, Literal(prop.name, lang="en")))

    if prop.description:
        g.add((prop_uri, RDFS.comment, Literal(prop.description, lang="en")))

    if prop.deprecated:
        g.add((prop_uri, OWL.deprecated, Literal(True, datatype=XSD.boolean)))

    if prop.pattern:
        g.add((prop_uri, C2PA["pattern"], Literal(prop.pattern)))

    if prop.enum_values:
        # Annotate with allowed values as a comma-separated literal
        g.add((prop_uri, C2PA["enumValues"], Literal(", ".join(prop.enum_values))))

    # Cardinality restriction on the class
    _add_cardinality_restriction(g, class_uri, prop_uri, prop.cardinality, prop.required)


# ---------------------------------------------------------------------------
# Relationship -> owl:ObjectProperty
# ---------------------------------------------------------------------------

def _add_relationship(g: Graph, rel: Relationship) -> None:
    """Add an owl:ObjectProperty for a cross-entity relationship."""
    prop_uri = _rel_iri(rel.name, rel.source_entity)
    g.add((prop_uri, RDF.type, OWL.ObjectProperty))
    g.add((prop_uri, RDFS.label, Literal(rel.name, lang="en")))
    g.add((prop_uri, RDFS.domain, _entity_iri(rel.source_entity)))
    g.add((prop_uri, RDFS.range, _entity_iri(rel.target_entity)))

    if rel.description:
        g.add((prop_uri, RDFS.comment, Literal(rel.description, lang="en")))

    # Annotate relationship type
    g.add((prop_uri, C2PA["relationshipType"], Literal(rel.relationship_type.value)))

    if rel.relationship_type == RelationshipType.EXTENDS:
        # structural subclass relationship
        g.add((_entity_iri(rel.source_entity), RDFS.subClassOf, _entity_iri(rel.target_entity)))


# ---------------------------------------------------------------------------
# EnumType -> owl:Class with named individuals
# ---------------------------------------------------------------------------

def _add_enum(g: Graph, enum_type: EnumType) -> None:
    """Add an owl:Class for an enum type with owl:oneOf named individuals."""
    class_uri = _entity_iri(enum_type.name)
    g.add((class_uri, RDF.type, OWL.Class))
    g.add((class_uri, RDFS.label, Literal(enum_type.name, lang="en")))

    if enum_type.description:
        g.add((class_uri, RDFS.comment, Literal(enum_type.description, lang="en")))

    if enum_type.extensible:
        g.add((class_uri, C2PA["extensible"], Literal(True, datatype=XSD.boolean)))

    # Create named individuals for each enum value
    if enum_type.values:
        individuals: list[URIRef] = []
        for val in enum_type.values:
            safe_val = _sanitize(val).replace(".", "_")
            ind_uri = C2PA[f"{_sanitize(enum_type.name)}.{safe_val}"]
            g.add((ind_uri, RDF.type, OWL.NamedIndividual))
            g.add((ind_uri, RDF.type, class_uri))
            g.add((ind_uri, RDFS.label, Literal(val, lang="en")))
            individuals.append(ind_uri)

        if not enum_type.extensible:
            # owl:oneOf restriction
            collection = BNode()
            current = collection
            for idx, ind_uri in enumerate(individuals):
                g.add((current, RDF.first, ind_uri))
                if idx < len(individuals) - 1:
                    rest = BNode()
                    g.add((current, RDF.rest, rest))
                    current = rest
                else:
                    g.add((current, RDF.rest, RDF.nil))
            one_of_bnode = BNode()
            g.add((one_of_bnode, OWL.oneOf, collection))
            g.add((class_uri, OWL.equivalentClass, one_of_bnode))


# ---------------------------------------------------------------------------
# Ontology header
# ---------------------------------------------------------------------------

def _add_ontology_header(g: Graph, kg: KnowledgeGraph) -> None:
    """Add owl:Ontology metadata triples."""
    ontology_uri = C2PA[""]
    g.add((ontology_uri, RDF.type, OWL.Ontology))
    g.add((ontology_uri, RDFS.label, Literal("C2PA Ontology", lang="en")))
    g.add((ontology_uri, RDFS.comment, Literal(
        "OWL ontology generated from the C2PA specification source files. "
        "Entities, properties, and relationships are derived primarily from "
        "CDDL schemas, supplemented by JSON Schema and AsciiDoc documentation.",
        lang="en",
    )))
    g.add((ontology_uri, OWL.versionIRI, C2PA[f"v{kg.version.version}/"]))
    g.add((ontology_uri, OWL.versionInfo, Literal(kg.version.version)))

    if kg.version.date:
        g.add((ontology_uri, DC["date"], Literal(kg.version.date, datatype=XSD.date)))

    # Bind common prefixes
    g.bind("c2pa", C2PA)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("rdf", RDF)
    g.bind("xsd", XSD)
    g.bind("dc", DC)
    g.bind("schema", SCHEMA)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def kg_to_graph(kg: KnowledgeGraph) -> Graph:
    """Convert a KnowledgeGraph to an rdflib Graph (OWL ontology).

    This function is also used by the JSON-LD emitter.

    Args:
        kg: The knowledge graph to convert.

    Returns:
        An rdflib.Graph containing all OWL triples.
    """
    g = Graph()
    _add_ontology_header(g, kg)

    # Classes for all entities
    for entity in kg.entities.values():
        _add_entity(g, entity)

    # Properties on each entity
    for entity in kg.entities.values():
        for prop in entity.properties:
            _add_property(g, entity, prop)

    # Enum types
    for enum_type in kg.enum_types.values():
        _add_enum(g, enum_type)

    # Global relationships (inferred and parser-added)
    seen_rels: set[tuple[str, str, str]] = set()
    for rel in kg.relationships:
        key = (rel.source_entity, rel.target_entity, rel.name)
        if key in seen_rels:
            continue
        seen_rels.add(key)
        _add_relationship(g, rel)

    return g


def emit_turtle(kg: KnowledgeGraph, output_path: Path) -> None:
    """Serialize a KnowledgeGraph as an OWL ontology in Turtle format.

    Args:
        kg: The knowledge graph to emit.
        output_path: Destination .ttl file path.
    """
    g = kg_to_graph(kg)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_path), format="turtle")
