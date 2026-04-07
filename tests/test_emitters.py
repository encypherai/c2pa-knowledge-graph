"""Tests for all knowledge graph emitters."""

from __future__ import annotations

import json
from pathlib import Path

from c2pa_kg.emitters.changelog import (
    _detect_entity_renames,
    _detect_enum_value_renames,
    _detect_property_renames,
    emit_changelog_json,
    generate_changelog,
)
from c2pa_kg.emitters.jsonld import emit_jsonld_context
from c2pa_kg.emitters.rules import emit_rules_json
from c2pa_kg.emitters.turtle import emit_turtle, kg_to_graph
from c2pa_kg.models import (
    Cardinality,
    ChangeType,
    Entity,
    EnumType,
    KnowledgeGraph,
    Property,
    PropertyType,
    SpecVersion,
)

# ---------------------------------------------------------------------------
# Turtle emitter
# ---------------------------------------------------------------------------

class TestTurtleEmitter:
    def test_emit_creates_file(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "ontology.ttl"
        emit_turtle(sample_kg, out)
        assert out.exists()

    def test_ttl_file_non_empty(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "ontology.ttl"
        emit_turtle(sample_kg, out)
        content = out.read_text(encoding="utf-8")
        assert len(content) > 100

    def test_ttl_contains_owl_class(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "ontology.ttl"
        emit_turtle(sample_kg, out)
        content = out.read_text(encoding="utf-8")
        assert "owl:Class" in content

    def test_ttl_contains_c2pa_namespace(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        out = tmp_output / "ontology.ttl"
        emit_turtle(sample_kg, out)
        content = out.read_text(encoding="utf-8")
        assert "c2pa.org/ontology" in content

    def test_kg_to_graph_returns_rdflib_graph(self, sample_kg: KnowledgeGraph) -> None:
        import rdflib
        g = kg_to_graph(sample_kg)
        assert isinstance(g, rdflib.Graph)
        assert len(g) > 0

    def test_ttl_contains_object_property(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        out = tmp_output / "ontology.ttl"
        emit_turtle(sample_kg, out)
        content = out.read_text(encoding="utf-8")
        assert "owl:ObjectProperty" in content or "owl:DatatypeProperty" in content

    def test_emit_creates_parent_dirs(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "subdir" / "ontology.ttl"
        emit_turtle(sample_kg, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# JSON-LD context emitter
# ---------------------------------------------------------------------------

class TestJsonLdEmitter:
    def test_emit_creates_file(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        assert out.exists()

    def test_jsonld_is_valid_json(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_jsonld_has_context_key(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "@context" in data

    def test_jsonld_has_vocab(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        ctx = data["@context"]
        assert "@vocab" in ctx
        assert "c2pa.org/ontology" in ctx["@vocab"]

    def test_jsonld_includes_c2pa_prefix(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        ctx = data["@context"]
        assert "c2pa" in ctx

    def test_jsonld_entity_mappings_present(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        out = tmp_output / "context.jsonld"
        emit_jsonld_context(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        ctx = data["@context"]
        # At least one entity name should appear in the context
        entity_names = set(sample_kg.entities.keys())
        context_keys = set(ctx.keys())
        overlap = entity_names & context_keys
        assert overlap, "No entity names found in JSON-LD @context"


# ---------------------------------------------------------------------------
# Rules JSON emitter
# ---------------------------------------------------------------------------

class TestRulesEmitter:
    def test_emit_creates_file(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        assert out.exists()

    def test_rules_json_is_valid(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_rules_json_has_phases(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "phases" in data
        assert isinstance(data["phases"], dict)
        assert len(data["phases"]) >= 1

    def test_rules_json_has_status_codes(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "status_codes" in data

    def test_rules_json_has_summary(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "summary" in data
        assert "total" in data["summary"]
        assert data["summary"]["total"] == sample_kg.rule_count

    def test_rules_json_version_matches(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        out = tmp_output / "validation-rules.json"
        emit_rules_json(sample_kg, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["version"] == sample_kg.version.version


# ---------------------------------------------------------------------------
# Changelog emitter
# ---------------------------------------------------------------------------

class TestChangelogEmitter:
    def test_identical_kgs_produce_empty_changelog(self, sample_kg: KnowledgeGraph) -> None:
        changelog = generate_changelog(sample_kg, sample_kg)
        assert len(changelog.entity_changes) == 0
        assert len(changelog.rule_changes) == 0
        assert len(changelog.enum_changes) == 0

    def test_changelog_version_fields(self, sample_kg: KnowledgeGraph) -> None:
        changelog = generate_changelog(sample_kg, sample_kg)
        assert changelog.from_version == sample_kg.version.version
        assert changelog.to_version == sample_kg.version.version

    def test_emit_changelog_creates_file(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        changelog = generate_changelog(sample_kg, sample_kg)
        out = tmp_output / "changelog.json"
        emit_changelog_json(changelog, out)
        assert out.exists()

    def test_emit_changelog_is_valid_json(
        self, sample_kg: KnowledgeGraph, tmp_output: Path
    ) -> None:
        changelog = generate_changelog(sample_kg, sample_kg)
        out = tmp_output / "changelog.json"
        emit_changelog_json(changelog, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_emit_changelog_has_summary(self, sample_kg: KnowledgeGraph, tmp_output: Path) -> None:
        changelog = generate_changelog(sample_kg, sample_kg)
        out = tmp_output / "changelog.json"
        emit_changelog_json(changelog, out)
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "summary" in data
        assert data["summary"]["total_changes"] == 0

    def test_added_entity_detected(self, sample_kg: KnowledgeGraph) -> None:
        # Clone-like kg with one extra entity
        new_kg = KnowledgeGraph(
            version=SpecVersion(version="2.5", date="2026-06-01", tag="2.5"),
            entities=dict(sample_kg.entities),
            relationships=list(sample_kg.relationships),
            validation_rules=list(sample_kg.validation_rules),
            enum_types=dict(sample_kg.enum_types),
            status_codes=list(sample_kg.status_codes),
        )
        new_kg.add_entity(Entity(name="BrandNewEntity"))

        old_kg = KnowledgeGraph(
            version=SpecVersion(version="2.4", date="2026-04-01", tag="2.4"),
            entities=dict(sample_kg.entities),
            relationships=list(sample_kg.relationships),
            validation_rules=list(sample_kg.validation_rules),
            enum_types=dict(sample_kg.enum_types),
            status_codes=list(sample_kg.status_codes),
        )

        changelog = generate_changelog(old_kg, new_kg)
        added_names = [c.entity_name for c in changelog.entity_changes]
        assert "BrandNewEntity" in added_names


# ---------------------------------------------------------------------------
# Rename detection unit tests
# ---------------------------------------------------------------------------

def _make_kg(
    version: str = "1.0",
    entities: dict[str, Entity] | None = None,
    enum_types: dict[str, EnumType] | None = None,
) -> KnowledgeGraph:
    """Helper to build a minimal KnowledgeGraph for diff tests."""
    return KnowledgeGraph(
        version=SpecVersion(version=version, date="2025-01-01", tag=version),
        entities=entities or {},
        enum_types=enum_types or {},
    )


def _make_entity(
    name: str,
    props: list[str] | None = None,
    aliases: list[str] | None = None,
) -> Entity:
    """Helper to build an Entity with named string properties."""
    properties = [
        Property(name=p, property_type=PropertyType.STRING)
        for p in (props or [])
    ]
    return Entity(name=name, properties=properties, aliases=aliases or [])


class TestEntityRenameDetection:
    """Tests for entity-level rename detection in the changelog."""

    def test_alias_overlap_detects_rename(self) -> None:
        """Entities sharing a normalized CDDL alias are detected as a rename."""
        old_kg = _make_kg(entities={
            "OldHashedUri": _make_entity(
                "OldHashedUri",
                props=["url", "alg", "hash"],
                aliases=["hashed-uri-map"],
            ),
        })
        new_kg = _make_kg(version="2.0", entities={
            "NewHashedUri": _make_entity(
                "NewHashedUri",
                props=["url", "alg", "hash"],
                aliases=["hashed-uri-map"],
            ),
        })

        changelog = generate_changelog(old_kg, new_kg)
        renamed = [c for c in changelog.entity_changes if c.change_type == ChangeType.RENAMED]
        assert len(renamed) == 1
        assert renamed[0].old_value == "OldHashedUri"
        assert renamed[0].new_value == "NewHashedUri"

    def test_property_similarity_detects_rename(self) -> None:
        """Entities with high property overlap and similar names are detected as renames."""
        old_kg = _make_kg(entities={
            "ParametersMapV2": _make_entity(
                "ParametersMapV2",
                props=["redacted", "ingredients", "description"],
            ),
        })
        new_kg = _make_kg(version="2.0", entities={
            "ParametersMapV2New": _make_entity(
                "ParametersMapV2New",
                props=["redacted", "ingredients", "description", "sourceLanguage"],
            ),
        })

        renames = _detect_entity_renames(
            {"ParametersMapV2"}, {"ParametersMapV2New"}, old_kg, new_kg,
        )
        assert len(renames) == 1
        assert renames[0] == ("ParametersMapV2", "ParametersMapV2New")

    def test_dissimilar_entities_not_matched(self) -> None:
        """Entities with different properties and names are not matched as renames."""
        old_kg = _make_kg(entities={
            "ClaimMap": _make_entity("ClaimMap", props=["signature", "assertions"]),
        })
        new_kg = _make_kg(version="2.0", entities={
            "RegionMap": _make_entity("RegionMap", props=["x", "y", "width", "height"]),
        })

        renames = _detect_entity_renames(
            {"ClaimMap"}, {"RegionMap"}, old_kg, new_kg,
        )
        assert len(renames) == 0

    def test_renamed_entity_not_in_added_or_removed(self) -> None:
        """A renamed entity should appear as RENAMED, not as separate ADDED + REMOVED."""
        old_entity = _make_entity(
            "OldName", props=["a", "b", "c", "d", "e"],
        )
        new_entity = _make_entity(
            "NewName", props=["a", "b", "c", "d", "e"],
        )
        old_kg = _make_kg(entities={"OldName": old_entity})
        new_kg = _make_kg(version="2.0", entities={"NewName": new_entity})

        changelog = generate_changelog(old_kg, new_kg)
        types = {c.change_type for c in changelog.entity_changes}
        assert ChangeType.RENAMED in types
        assert ChangeType.ADDED not in types
        assert ChangeType.REMOVED not in types

    def test_rename_includes_property_diff(self) -> None:
        """A renamed entity also reports property-level changes in details."""
        old_entity = _make_entity(
            "ActionItemsMap", props=["action", "when", "changed", "reason", "parameters"],
        )
        new_entity = _make_entity(
            "ActionItemMap", props=["action", "when", "changes", "reason", "parameters"],
        )
        old_kg = _make_kg(entities={"ActionItemsMap": old_entity})
        new_kg = _make_kg(version="2.0", entities={"ActionItemMap": new_entity})

        changelog = generate_changelog(old_kg, new_kg)
        renamed = [c for c in changelog.entity_changes if c.change_type == ChangeType.RENAMED]
        assert len(renamed) == 1
        # The property rename (changed -> changes) should appear in details
        assert "renamed properties: changed -> changes" in renamed[0].details


class TestPropertyRenameDetection:
    """Tests for property-level rename detection within an entity."""

    def test_similar_name_same_signature_detected(self) -> None:
        """Properties with similar names and identical signatures are detected as renames."""
        old_prop = Property(
            name="changed", property_type=PropertyType.ARRAY, cardinality=Cardinality.ONE_OR_MORE
        )
        new_prop = Property(
            name="changes", property_type=PropertyType.ARRAY, cardinality=Cardinality.ONE_OR_MORE
        )

        renames = _detect_property_renames(
            {"changed"}, {"changes"},
            {"changed": old_prop}, {"changes": new_prop},
        )
        assert len(renames) == 1
        assert renames[0] == ("changed", "changes")

    def test_different_signature_not_matched(self) -> None:
        """Properties with different types are not matched even if names are similar."""
        old_prop = Property(name="count", property_type=PropertyType.STRING)
        new_prop = Property(name="counts", property_type=PropertyType.INTEGER)

        renames = _detect_property_renames(
            {"count"}, {"counts"},
            {"count": old_prop}, {"counts": new_prop},
        )
        assert len(renames) == 0

    def test_completely_different_names_not_matched(self) -> None:
        """Properties with totally different names are not matched."""
        old_prop = Property(name="alpha", property_type=PropertyType.STRING)
        new_prop = Property(name="zebra", property_type=PropertyType.STRING)

        renames = _detect_property_renames(
            {"alpha"}, {"zebra"},
            {"alpha": old_prop}, {"zebra": new_prop},
        )
        assert len(renames) == 0

    def test_property_rename_in_entity_diff(self) -> None:
        """Property renames appear in the entity's MODIFIED change details."""
        old_entity = Entity(
            name="Foo",
            properties=[
                Property(
                    name="changed",
                    property_type=PropertyType.ARRAY,
                    cardinality=Cardinality.ONE_OR_MORE,
                ),
                Property(name="action", property_type=PropertyType.STRING),
            ],
        )
        new_entity = Entity(
            name="Foo",
            properties=[
                Property(
                    name="changes",
                    property_type=PropertyType.ARRAY,
                    cardinality=Cardinality.ONE_OR_MORE,
                ),
                Property(name="action", property_type=PropertyType.STRING),
            ],
        )
        old_kg = _make_kg(entities={"Foo": old_entity})
        new_kg = _make_kg(version="2.0", entities={"Foo": new_entity})

        changelog = generate_changelog(old_kg, new_kg)
        modified = [c for c in changelog.entity_changes if c.change_type == ChangeType.MODIFIED]
        assert len(modified) == 1
        assert "renamed properties: changed -> changes" in modified[0].details


class TestEnumValueRenameDetection:
    """Tests for enum value rename detection."""

    def test_normalized_match_detected(self) -> None:
        """Values differing only by hyphens/underscores are detected as renames."""
        renames, rem_removed, rem_added = _detect_enum_value_renames(
            ["c2pa.tradesecret.present"],
            ["c2pa.trade-secret.present"],
        )
        assert len(renames) == 1
        assert renames[0] == ("c2pa.tradesecret.present", "c2pa.trade-secret.present")
        assert rem_removed == []
        assert rem_added == []

    def test_genuinely_different_values_not_matched(self) -> None:
        """Values with completely different content are not matched."""
        renames, rem_removed, rem_added = _detect_enum_value_renames(
            ["c2pa.created"],
            ["c2pa.watermarked.bound"],
        )
        assert len(renames) == 0
        assert rem_removed == ["c2pa.created"]
        assert rem_added == ["c2pa.watermarked.bound"]

    def test_mixed_renames_and_additions(self) -> None:
        """Renames are separated from genuine additions/removals."""
        renames, rem_removed, rem_added = _detect_enum_value_renames(
            ["c2pa.tradesecret.present", "c2pa.old_action"],
            ["c2pa.trade-secret.present", "c2pa.brand_new"],
        )
        assert len(renames) == 1
        assert renames[0] == ("c2pa.tradesecret.present", "c2pa.trade-secret.present")
        assert rem_removed == ["c2pa.old_action"]
        assert rem_added == ["c2pa.brand_new"]

    def test_enum_rename_in_full_diff(self) -> None:
        """Enum value renames appear in the changelog details."""
        old_kg = _make_kg(enum_types={
            "ActionReason": EnumType(
                name="ActionReason",
                values=["c2pa.PII.present", "c2pa.tradesecret.present"],
            ),
        })
        new_kg = _make_kg(version="2.0", enum_types={
            "ActionReason": EnumType(
                name="ActionReason",
                values=["c2pa.PII.present", "c2pa.trade-secret.present"],
            ),
        })

        changelog = generate_changelog(old_kg, new_kg)
        assert len(changelog.enum_changes) == 1
        change = changelog.enum_changes[0]
        assert "renamed values:" in change.details
        assert "tradesecret" in change.details
        assert "trade-secret" in change.details

    def test_no_false_renames_on_identical_enums(self) -> None:
        """Identical enums produce no changes."""
        old_kg = _make_kg(enum_types={
            "Foo": EnumType(name="Foo", values=["a", "b", "c"]),
        })
        new_kg = _make_kg(version="2.0", enum_types={
            "Foo": EnumType(name="Foo", values=["a", "b", "c"]),
        })

        changelog = generate_changelog(old_kg, new_kg)
        assert len(changelog.enum_changes) == 0
