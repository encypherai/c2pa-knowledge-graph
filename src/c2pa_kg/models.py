"""Intermediate representation (IR) data models for the C2PA knowledge graph.

These dataclasses define the canonical internal representation that all parsers
produce and all emitters consume. The IR captures entities, properties,
relationships, validation rules, and version metadata extracted from C2PA
specification source files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PropertyType(Enum):
    """Data type of an entity property."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    BYTES = "bytes"
    URI = "uri"
    DATETIME = "datetime"
    ENUM = "enum"
    ARRAY = "array"
    MAP = "map"
    REFERENCE = "reference"
    UNION = "union"
    ANY = "any"


class Cardinality(Enum):
    """Property or relationship cardinality."""

    ONE = "1"
    ZERO_OR_ONE = "0..1"
    ZERO_OR_MORE = "0..*"
    ONE_OR_MORE = "1..*"


class RelationshipType(Enum):
    """Type of relationship between entities."""

    HAS_ONE = "has_one"
    HAS_MANY = "has_many"
    BELONGS_TO = "belongs_to"
    REFERENCES = "references"
    EXTENDS = "extends"


class RuleSeverity(Enum):
    """RFC 2119 keyword severity level."""

    MUST = "must"
    SHALL = "shall"
    MUST_NOT = "must_not"
    SHALL_NOT = "shall_not"
    SHOULD = "should"
    SHOULD_NOT = "should_not"
    MAY = "may"


class ValidationPhase(Enum):
    """Phase of the validation process."""

    STRUCTURAL = "structural"
    CRYPTOGRAPHIC = "cryptographic"
    TRUST = "trust"
    SEMANTIC = "semantic"
    ASSERTION = "assertion"
    INGREDIENT = "ingredient"
    TIMESTAMP = "timestamp"
    SIGNATURE = "signature"
    CONTENT = "content"


class ChangeType(Enum):
    """Type of change between spec versions."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    DEPRECATED = "deprecated"
    RENAMED = "renamed"


@dataclass
class Property:
    """A property of an entity (field in a CDDL map or JSON Schema object)."""

    name: str
    property_type: PropertyType
    description: str = ""
    required: bool = False
    cardinality: Cardinality = Cardinality.ONE
    enum_values: list[str] = field(default_factory=list)
    reference_target: str = ""
    array_item_type: str = ""
    pattern: str = ""
    min_length: int | None = None
    max_length: int | None = None
    deprecated: bool = False
    source: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "type": self.property_type.value,
            "required": self.required,
            "cardinality": self.cardinality.value,
        }
        if self.description:
            d["description"] = self.description
        if self.enum_values:
            d["enum_values"] = self.enum_values
        if self.reference_target:
            d["reference_target"] = self.reference_target
        if self.array_item_type:
            d["array_item_type"] = self.array_item_type
        if self.pattern:
            d["pattern"] = self.pattern
        if self.deprecated:
            d["deprecated"] = True
        return d


@dataclass
class Relationship:
    """A relationship between two entities."""

    name: str
    source_entity: str
    target_entity: str
    relationship_type: RelationshipType
    description: str = ""
    cardinality: Cardinality = Cardinality.ONE

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source": self.source_entity,
            "target": self.target_entity,
            "type": self.relationship_type.value,
            "cardinality": self.cardinality.value,
            "description": self.description,
        }


@dataclass
class Entity:
    """A C2PA entity type (CDDL map, JSON Schema definition, or spec concept)."""

    name: str
    description: str = ""
    properties: list[Property] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    parent: str = ""
    source: str = ""
    spec_section: str = ""
    aliases: list[str] = field(default_factory=list)
    deprecated: bool = False
    version_introduced: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "properties": [p.to_dict() for p in self.properties],
            "relationships": [r.to_dict() for r in self.relationships],
        }
        if self.description:
            d["description"] = self.description
        if self.parent:
            d["parent"] = self.parent
        if self.aliases:
            d["aliases"] = self.aliases
        if self.deprecated:
            d["deprecated"] = True
        if self.spec_section:
            d["spec_section"] = self.spec_section
        return d


@dataclass
class ValidationRule:
    """A normative validation rule extracted from the specification."""

    rule_id: str
    description: str
    severity: RuleSeverity
    phase: ValidationPhase
    condition: str = ""
    action: str = ""
    referenced_entities: list[str] = field(default_factory=list)
    spec_section: str = ""
    source_text: str = ""

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "severity": self.severity.value,
            "phase": self.phase.value,
            "condition": self.condition,
            "action": self.action,
            "referenced_entities": self.referenced_entities,
            "spec_section": self.spec_section,
            "source_text": self.source_text,
        }


@dataclass
class EnumType:
    """An enumeration type (CDDL socket/plug choices or JSON Schema enum)."""

    name: str
    values: list[str] = field(default_factory=list)
    extensible: bool = False
    description: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "values": self.values,
            "extensible": self.extensible,
            "description": self.description,
        }


@dataclass
class TypeAlias:
    """A simple CDDL type alias that is not a full entity.

    Captures definitions like `buuid = #6.37(bstr)` or external types
    like `COSE_Sign1` (RFC 9052) that are referenced by entity properties
    but do not warrant full entity definitions.
    """

    name: str
    cddl_name: str = ""
    base_type: str = ""
    description: str = ""
    external: bool = False

    def to_dict(self) -> dict:
        d: dict = {
            "name": self.name,
            "base_type": self.base_type,
        }
        if self.cddl_name:
            d["cddl_name"] = self.cddl_name
        if self.description:
            d["description"] = self.description
        if self.external:
            d["external"] = True
        return d


@dataclass
class StatusCode:
    """A C2PA validation status code."""

    code: str
    meaning: str
    url_usage: str = ""
    category: str = ""

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "meaning": self.meaning,
            "url_usage": self.url_usage,
            "category": self.category,
        }


@dataclass
class SpecVersion:
    """Metadata about a specific C2PA specification version."""

    version: str
    date: str = ""
    commit_hash: str = ""
    tag: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "date": self.date,
            "commit_hash": self.commit_hash,
            "tag": self.tag,
        }


@dataclass
class EntityChange:
    """A change to an entity between spec versions."""

    entity_name: str
    change_type: ChangeType
    details: str = ""
    old_value: str = ""
    new_value: str = ""

    def to_dict(self) -> dict:
        d: dict = {
            "entity": self.entity_name,
            "change": self.change_type.value,
        }
        if self.details:
            d["details"] = self.details
        if self.old_value:
            d["old_value"] = self.old_value
        if self.new_value:
            d["new_value"] = self.new_value
        return d


@dataclass
class VersionChangelog:
    """Structured diff between two spec versions."""

    from_version: str
    to_version: str
    entity_changes: list[EntityChange] = field(default_factory=list)
    rule_changes: list[EntityChange] = field(default_factory=list)
    enum_changes: list[EntityChange] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "entity_changes": [c.to_dict() for c in self.entity_changes],
            "rule_changes": [c.to_dict() for c in self.rule_changes],
            "enum_changes": [c.to_dict() for c in self.enum_changes],
        }


@dataclass
class KnowledgeGraph:
    """The complete knowledge graph for a C2PA specification version.

    This is the central data structure that parsers build and emitters consume.
    """

    version: SpecVersion
    entities: dict[str, Entity] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)
    validation_rules: list[ValidationRule] = field(default_factory=list)
    enum_types: dict[str, EnumType] = field(default_factory=dict)
    type_aliases: dict[str, TypeAlias] = field(default_factory=dict)
    status_codes: list[StatusCode] = field(default_factory=list)
    spec_conventions: dict = field(default_factory=dict)

    C2PA_NAMESPACE = "https://c2pa.org/ontology/"
    C2PA_PREFIX = "c2pa"

    @property
    def entity_count(self) -> int:
        return len(self.entities)

    @property
    def relationship_count(self) -> int:
        return len(self.relationships)

    @property
    def rule_count(self) -> int:
        return len(self.validation_rules)

    def add_entity(self, entity: Entity) -> None:
        self.entities[entity.name] = entity

    def add_relationship(self, rel: Relationship) -> None:
        self.relationships.append(rel)
        if rel.source_entity in self.entities:
            self.entities[rel.source_entity].relationships.append(rel)

    def add_rule(self, rule: ValidationRule) -> None:
        self.validation_rules.append(rule)

    def add_enum(self, enum: EnumType) -> None:
        self.enum_types[enum.name] = enum

    def add_type_alias(self, alias: TypeAlias) -> None:
        self.type_aliases[alias.name] = alias

    def get_entity(self, name: str) -> Entity | None:
        return self.entities.get(name)

    def get_relationships_for(self, entity_name: str) -> list[Relationship]:
        return [
            r
            for r in self.relationships
            if r.source_entity == entity_name or r.target_entity == entity_name
        ]

    def get_rules_for_entity(self, entity_name: str) -> list[ValidationRule]:
        return [
            r for r in self.validation_rules if entity_name in r.referenced_entities
        ]

    def get_rules_by_phase(self, phase: ValidationPhase) -> list[ValidationRule]:
        return [r for r in self.validation_rules if r.phase == phase]

    def to_dict(self) -> dict:
        return {
            "version": self.version.to_dict(),
            "entities": {n: e.to_dict() for n, e in self.entities.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "validation_rules": [r.to_dict() for r in self.validation_rules],
            "enum_types": {n: e.to_dict() for n, e in self.enum_types.items()},
            "type_aliases": {n: a.to_dict() for n, a in self.type_aliases.items()},
            "spec_conventions": self.spec_conventions,
            "status_codes": [s.to_dict() for s in self.status_codes],
            "stats": {
                "entity_count": self.entity_count,
                "relationship_count": self.relationship_count,
                "rule_count": self.rule_count,
                "enum_count": len(self.enum_types),
                "type_alias_count": len(self.type_aliases),
                "status_code_count": len(self.status_codes),
            },
        }


def kg_from_dict(data: dict) -> KnowledgeGraph:
    """Reconstruct a KnowledgeGraph from its serialized dict representation.

    This is the inverse of KnowledgeGraph.to_dict(), used to load saved
    metadata.json files for diffing and MCP serving.
    """
    version_data = data.get("version", {})
    version = SpecVersion(
        version=version_data.get("version", ""),
        date=version_data.get("date", ""),
        commit_hash=version_data.get("commit_hash", ""),
        tag=version_data.get("tag", ""),
    )

    kg = KnowledgeGraph(version=version)

    for name, ed in data.get("entities", {}).items():
        props = []
        for pd in ed.get("properties", []):
            props.append(Property(
                name=pd["name"],
                property_type=PropertyType(pd.get("type", "any")),
                description=pd.get("description", ""),
                required=pd.get("required", False),
                cardinality=Cardinality(pd.get("cardinality", "1")),
                enum_values=pd.get("enum_values", []),
                reference_target=pd.get("reference_target", ""),
                array_item_type=pd.get("array_item_type", ""),
                deprecated=pd.get("deprecated", False),
            ))
        entity = Entity(
            name=name,
            description=ed.get("description", ""),
            properties=props,
            parent=ed.get("parent", ""),
            aliases=ed.get("aliases", []),
            deprecated=ed.get("deprecated", False),
            spec_section=ed.get("spec_section", ""),
        )
        kg.entities[name] = entity

    for rd in data.get("relationships", []):
        kg.relationships.append(Relationship(
            name=rd.get("name", ""),
            source_entity=rd.get("source", ""),
            target_entity=rd.get("target", ""),
            relationship_type=RelationshipType(rd.get("type", "references")),
            description=rd.get("description", ""),
            cardinality=Cardinality(rd.get("cardinality", "1")),
        ))

    for rud in data.get("validation_rules", []):
        kg.validation_rules.append(ValidationRule(
            rule_id=rud.get("rule_id", ""),
            description=rud.get("description", ""),
            severity=RuleSeverity(rud.get("severity", "may")),
            phase=ValidationPhase(rud.get("phase", "structural")),
            condition=rud.get("condition", ""),
            action=rud.get("action", ""),
            referenced_entities=rud.get("referenced_entities", []),
            spec_section=rud.get("spec_section", ""),
            source_text=rud.get("source_text", ""),
        ))

    for en, ed in data.get("enum_types", {}).items():
        kg.enum_types[en] = EnumType(
            name=en,
            values=ed.get("values", []),
            extensible=ed.get("extensible", False),
            description=ed.get("description", ""),
        )

    for an, ad in data.get("type_aliases", {}).items():
        kg.type_aliases[an] = TypeAlias(
            name=an,
            cddl_name=ad.get("cddl_name", ""),
            base_type=ad.get("base_type", ""),
            description=ad.get("description", ""),
            external=ad.get("external", False),
        )

    kg.spec_conventions = data.get("spec_conventions", {})

    for sd in data.get("status_codes", []):
        kg.status_codes.append(StatusCode(
            code=sd.get("code", ""),
            meaning=sd.get("meaning", ""),
            url_usage=sd.get("url_usage", ""),
            category=sd.get("category", ""),
        ))

    return kg
