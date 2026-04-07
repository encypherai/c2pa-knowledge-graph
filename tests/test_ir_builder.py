"""Tests for the IR builder (full pipeline from spec source to KnowledgeGraph)."""

from __future__ import annotations

from c2pa_kg.models import KnowledgeGraph


class TestIrBuilder:
    """Tests that use the module-scoped sample_kg fixture for efficiency."""

    def test_kg_is_knowledge_graph(self, sample_kg: KnowledgeGraph) -> None:
        assert isinstance(sample_kg, KnowledgeGraph)

    def test_entity_count_positive(self, sample_kg: KnowledgeGraph) -> None:
        assert sample_kg.entity_count > 0, "No entities in knowledge graph"

    def test_entity_count_reasonable(self, sample_kg: KnowledgeGraph) -> None:
        # The v2.4 spec has many entities; 50+ is a reasonable lower bound
        assert sample_kg.entity_count >= 50, (
            f"Expected >= 50 entities, got {sample_kg.entity_count}"
        )

    def test_relationship_count_positive(self, sample_kg: KnowledgeGraph) -> None:
        assert sample_kg.relationship_count > 0, "No relationships in knowledge graph"

    def test_rule_count_positive(self, sample_kg: KnowledgeGraph) -> None:
        assert sample_kg.rule_count > 0, "No validation rules in knowledge graph"

    def test_rule_count_reasonable(self, sample_kg: KnowledgeGraph) -> None:
        assert sample_kg.rule_count >= 50, (
            f"Expected >= 50 rules, got {sample_kg.rule_count}"
        )

    def test_status_codes_present(self, sample_kg: KnowledgeGraph) -> None:
        assert len(sample_kg.status_codes) >= 50, (
            f"Expected >= 50 status codes, got {len(sample_kg.status_codes)}"
        )

    def test_enum_types_present(self, sample_kg: KnowledgeGraph) -> None:
        assert len(sample_kg.enum_types) >= 1, "No enum types in knowledge graph"

    def test_claim_map_entity_exists(self, sample_kg: KnowledgeGraph) -> None:
        entity = sample_kg.get_entity("ClaimMap")
        assert entity is not None, "ClaimMap entity not found"

    def test_claim_map_has_properties(self, sample_kg: KnowledgeGraph) -> None:
        entity = sample_kg.get_entity("ClaimMap")
        assert entity is not None
        assert len(entity.properties) >= 3

    def test_action_items_map_entity_exists(self, sample_kg: KnowledgeGraph) -> None:
        entity = sample_kg.get_entity("ActionItemsMap")
        assert entity is not None, "ActionItemsMap entity not found"

    def test_relationships_were_inferred(self, sample_kg: KnowledgeGraph) -> None:
        # Inferred relationships should link known entities
        inferred = [
            r for r in sample_kg.relationships
            if r.source_entity in sample_kg.entities
            and r.target_entity in sample_kg.entities
        ]
        assert len(inferred) >= 1, "No inferred cross-entity relationships found"

    def test_version_metadata_set(self, sample_kg: KnowledgeGraph) -> None:
        assert sample_kg.version.version == "2.4"

    def test_entities_have_names(self, sample_kg: KnowledgeGraph) -> None:
        for name, entity in sample_kg.entities.items():
            assert entity.name == name

    def test_validation_rules_have_severity(self, sample_kg: KnowledgeGraph) -> None:
        for rule in sample_kg.validation_rules:
            assert rule.severity is not None

    def test_validation_rules_have_phase(self, sample_kg: KnowledgeGraph) -> None:
        for rule in sample_kg.validation_rules:
            assert rule.phase is not None

    def test_to_dict_is_serializable(self, sample_kg: KnowledgeGraph) -> None:
        import json
        d = sample_kg.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        assert len(serialized) > 100
