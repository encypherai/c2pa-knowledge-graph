"""Tests for IR data models in c2pa_kg.models."""

from __future__ import annotations

from c2pa_kg.models import (
    Cardinality,
    Entity,
    EnumType,
    KnowledgeGraph,
    Property,
    PropertyType,
    Relationship,
    RelationshipType,
    RuleSeverity,
    SpecVersion,
    StatusCode,
    ValidationPhase,
    ValidationRule,
    kg_from_dict,
)

# ---------------------------------------------------------------------------
# Property
# ---------------------------------------------------------------------------

class TestProperty:
    def test_basic_creation(self) -> None:
        prop = Property(name="foo", property_type=PropertyType.STRING)
        assert prop.name == "foo"
        assert prop.property_type == PropertyType.STRING
        assert prop.required is False
        assert prop.cardinality == Cardinality.ONE

    def test_to_dict_minimal(self) -> None:
        prop = Property(name="bar", property_type=PropertyType.INTEGER)
        d = prop.to_dict()
        assert d["name"] == "bar"
        assert d["type"] == "integer"
        assert d["required"] is False
        # Description omitted when empty
        assert "description" not in d

    def test_to_dict_full(self) -> None:
        prop = Property(
            name="alg",
            property_type=PropertyType.ENUM,
            description="Hash algorithm",
            required=True,
            cardinality=Cardinality.ONE,
            enum_values=["sha256", "sha384"],
            deprecated=True,
        )
        d = prop.to_dict()
        assert d["description"] == "Hash algorithm"
        assert d["required"] is True
        assert d["enum_values"] == ["sha256", "sha384"]
        assert d["deprecated"] is True

    def test_to_dict_reference(self) -> None:
        prop = Property(
            name="signer",
            property_type=PropertyType.REFERENCE,
            reference_target="SignerInfo",
        )
        d = prop.to_dict()
        assert d["reference_target"] == "SignerInfo"

    def test_to_dict_array(self) -> None:
        prop = Property(
            name="assertions",
            property_type=PropertyType.ARRAY,
            array_item_type="HashedUri",
            cardinality=Cardinality.ONE_OR_MORE,
        )
        d = prop.to_dict()
        assert d["array_item_type"] == "HashedUri"
        assert d["cardinality"] == "1..*"


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------

class TestEntity:
    def test_basic_creation(self) -> None:
        entity = Entity(name="ClaimMap")
        assert entity.name == "ClaimMap"
        assert entity.properties == []
        assert entity.relationships == []
        assert entity.deprecated is False

    def test_to_dict_with_properties(self) -> None:
        prop = Property(name="instanceID", property_type=PropertyType.STRING, required=True)
        entity = Entity(
            name="ClaimMap",
            description="The C2PA claim map",
            properties=[prop],
            spec_section="7.1",
            aliases=["claim-map"],
        )
        d = entity.to_dict()
        assert d["name"] == "ClaimMap"
        assert d["description"] == "The C2PA claim map"
        assert d["spec_section"] == "7.1"
        assert d["aliases"] == ["claim-map"]
        assert len(d["properties"]) == 1
        assert d["properties"][0]["name"] == "instanceID"

    def test_to_dict_deprecated(self) -> None:
        entity = Entity(name="OldMap", deprecated=True)
        d = entity.to_dict()
        assert d["deprecated"] is True

    def test_to_dict_omits_empty_fields(self) -> None:
        entity = Entity(name="SimpleMap")
        d = entity.to_dict()
        assert "description" not in d
        assert "parent" not in d
        assert "aliases" not in d
        assert "deprecated" not in d


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------

class TestRelationship:
    def test_basic_creation(self) -> None:
        rel = Relationship(
            name="assertions",
            source_entity="ClaimMap",
            target_entity="HashedUri",
            relationship_type=RelationshipType.HAS_MANY,
        )
        assert rel.source_entity == "ClaimMap"
        assert rel.target_entity == "HashedUri"

    def test_to_dict(self) -> None:
        rel = Relationship(
            name="signature",
            source_entity="ClaimMap",
            target_entity="Signature",
            relationship_type=RelationshipType.REFERENCES,
            description="JUMBF URI to signature",
            cardinality=Cardinality.ONE,
        )
        d = rel.to_dict()
        assert d["name"] == "signature"
        assert d["source"] == "ClaimMap"
        assert d["target"] == "Signature"
        assert d["type"] == "references"
        assert d["cardinality"] == "1"
        assert d["description"] == "JUMBF URI to signature"


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------

class TestKnowledgeGraph:
    def _make_kg(self) -> KnowledgeGraph:
        return KnowledgeGraph(version=SpecVersion(version="2.4", date="2026-04-01", tag="2.4"))

    def test_add_and_get_entity(self) -> None:
        kg = self._make_kg()
        entity = Entity(name="ClaimMap")
        kg.add_entity(entity)
        assert kg.get_entity("ClaimMap") is entity
        assert kg.entity_count == 1

    def test_get_entity_missing_returns_none(self) -> None:
        kg = self._make_kg()
        assert kg.get_entity("NoSuchEntity") is None

    def test_add_relationship_appends_to_entity(self) -> None:
        kg = self._make_kg()
        entity = Entity(name="ClaimMap")
        kg.add_entity(entity)
        rel = Relationship(
            name="assertions",
            source_entity="ClaimMap",
            target_entity="HashedUri",
            relationship_type=RelationshipType.HAS_MANY,
        )
        kg.add_relationship(rel)
        assert kg.relationship_count == 1
        # Should also be appended to the source entity
        assert rel in kg.entities["ClaimMap"].relationships

    def test_add_rule(self) -> None:
        kg = self._make_kg()
        rule = ValidationRule(
            rule_id="VAL-STRU-0001",
            description="Claims must be valid CBOR.",
            severity=RuleSeverity.MUST,
            phase=ValidationPhase.STRUCTURAL,
        )
        kg.add_rule(rule)
        assert kg.rule_count == 1

    def test_add_enum(self) -> None:
        kg = self._make_kg()
        enum = EnumType(name="ActionChoice", values=["c2pa.created", "c2pa.edited"])
        kg.add_enum(enum)
        assert "ActionChoice" in kg.enum_types

    def test_get_relationships_for(self) -> None:
        kg = self._make_kg()
        rel = Relationship(
            name="sig",
            source_entity="ClaimMap",
            target_entity="Signature",
            relationship_type=RelationshipType.REFERENCES,
        )
        kg.relationships.append(rel)
        rels = kg.get_relationships_for("ClaimMap")
        assert rel in rels
        rels_target = kg.get_relationships_for("Signature")
        assert rel in rels_target

    def test_get_rules_by_phase(self) -> None:
        kg = self._make_kg()
        rule1 = ValidationRule(
            rule_id="VAL-CRYP-0001",
            description="Signature must verify.",
            severity=RuleSeverity.MUST,
            phase=ValidationPhase.CRYPTOGRAPHIC,
        )
        rule2 = ValidationRule(
            rule_id="VAL-STRU-0001",
            description="Must be CBOR.",
            severity=RuleSeverity.MUST,
            phase=ValidationPhase.STRUCTURAL,
        )
        kg.add_rule(rule1)
        kg.add_rule(rule2)
        crypto_rules = kg.get_rules_by_phase(ValidationPhase.CRYPTOGRAPHIC)
        assert rule1 in crypto_rules
        assert rule2 not in crypto_rules

    def test_to_dict_contains_stats(self) -> None:
        kg = self._make_kg()
        kg.add_entity(Entity(name="ClaimMap"))
        d = kg.to_dict()
        assert "stats" in d
        assert d["stats"]["entity_count"] == 1


# ---------------------------------------------------------------------------
# kg_from_dict round-trip
# ---------------------------------------------------------------------------

class TestKgFromDict:
    def _minimal_kg(self) -> KnowledgeGraph:
        kg = KnowledgeGraph(version=SpecVersion(version="2.4", date="2026-04-01", tag="2.4"))
        prop = Property(
            name="instanceID",
            property_type=PropertyType.STRING,
            required=True,
            cardinality=Cardinality.ONE,
            description="Unique asset ID",
        )
        entity = Entity(
            name="ClaimMap",
            description="C2PA claim",
            properties=[prop],
            aliases=["claim-map"],
        )
        kg.add_entity(entity)
        rel = Relationship(
            name="assertions",
            source_entity="ClaimMap",
            target_entity="HashedUri",
            relationship_type=RelationshipType.HAS_MANY,
            cardinality=Cardinality.ONE_OR_MORE,
        )
        kg.relationships.append(rel)
        rule = ValidationRule(
            rule_id="VAL-STRU-0001",
            description="Must be valid.",
            severity=RuleSeverity.MUST,
            phase=ValidationPhase.STRUCTURAL,
        )
        kg.add_rule(rule)
        enum = EnumType(name="ActionChoice", values=["c2pa.created"], extensible=True)
        kg.add_enum(enum)
        code = StatusCode(code="claimSignature.validated", meaning="OK", category="success")
        kg.status_codes.append(code)
        return kg

    def test_round_trip_stable(self) -> None:
        kg = self._minimal_kg()
        d1 = kg.to_dict()
        restored = kg_from_dict(d1)
        d2 = restored.to_dict()
        # Core counts must match
        assert d2["stats"]["entity_count"] == d1["stats"]["entity_count"]
        assert d2["stats"]["rule_count"] == d1["stats"]["rule_count"]
        assert d2["stats"]["enum_count"] == d1["stats"]["enum_count"]
        assert d2["stats"]["status_code_count"] == d1["stats"]["status_code_count"]

    def test_round_trip_entity_properties(self) -> None:
        kg = self._minimal_kg()
        restored = kg_from_dict(kg.to_dict())
        entity = restored.get_entity("ClaimMap")
        assert entity is not None
        assert entity.description == "C2PA claim"
        prop_names = [p.name for p in entity.properties]
        assert "instanceID" in prop_names

    def test_round_trip_relationships(self) -> None:
        kg = self._minimal_kg()
        restored = kg_from_dict(kg.to_dict())
        assert len(restored.relationships) == len(kg.relationships)
        rel = restored.relationships[0]
        assert rel.source_entity == "ClaimMap"
        assert rel.target_entity == "HashedUri"

    def test_round_trip_rules(self) -> None:
        kg = self._minimal_kg()
        restored = kg_from_dict(kg.to_dict())
        assert len(restored.validation_rules) == 1
        assert restored.validation_rules[0].rule_id == "VAL-STRU-0001"
        assert restored.validation_rules[0].severity == RuleSeverity.MUST

    def test_round_trip_enums(self) -> None:
        kg = self._minimal_kg()
        restored = kg_from_dict(kg.to_dict())
        assert "ActionChoice" in restored.enum_types
        assert restored.enum_types["ActionChoice"].extensible is True

    def test_round_trip_status_codes(self) -> None:
        kg = self._minimal_kg()
        restored = kg_from_dict(kg.to_dict())
        assert len(restored.status_codes) == 1
        assert restored.status_codes[0].code == "claimSignature.validated"
