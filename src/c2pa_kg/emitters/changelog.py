"""Changelog emitter: structured diffs between two KnowledgeGraph versions.

Compares two KnowledgeGraph instances (old and new) across entities, properties,
relationships, validation rules, and enum types. Produces a VersionChangelog
with EntityChange entries for added, removed, modified, renamed, and deprecated
items. Includes rename detection at entity, property, and enum-value levels.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from c2pa_kg.models import (
    ChangeType,
    Entity,
    EntityChange,
    KnowledgeGraph,
    Property,
    VersionChangelog,
)

# ---------------------------------------------------------------------------
# Rename detection helpers
# ---------------------------------------------------------------------------

def _normalize(name: str) -> str:
    """Normalize a name for fuzzy matching: lowercase, strip hyphens/underscores."""
    return name.lower().replace("-", "").replace("_", "").replace(".", "")


def _name_similarity(a: str, b: str) -> float:
    """Return 0.0-1.0 similarity ratio between two names."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity between two string sets."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _detect_entity_renames(
    old_only: set[str],
    new_only: set[str],
    old_kg: KnowledgeGraph,
    new_kg: KnowledgeGraph,
) -> list[tuple[str, str]]:
    """Detect entity renames between old-only and new-only name sets.

    Uses two signals: alias overlap (strongest) and property-set Jaccard
    similarity combined with name similarity (fallback).

    Returns list of (old_name, new_name) pairs.
    """
    renames: list[tuple[str, str]] = []
    matched_old: set[str] = set()
    matched_new: set[str] = set()

    # Pass 1: alias overlap (e.g. both have CDDL alias "action-items-map-v2")
    old_alias_index: dict[str, str] = {}
    for name in old_only:
        entity = old_kg.entities[name]
        for alias in entity.aliases:
            old_alias_index[_normalize(alias)] = name

    for new_name in new_only:
        entity = new_kg.entities[new_name]
        for alias in entity.aliases:
            norm = _normalize(alias)
            if norm in old_alias_index:
                old_name = old_alias_index[norm]
                if old_name not in matched_old:
                    renames.append((old_name, new_name))
                    matched_old.add(old_name)
                    matched_new.add(new_name)
                    break

    # Pass 2: property-set Jaccard + name similarity for remaining unmatched
    remaining_old = old_only - matched_old
    remaining_new = new_only - matched_new

    for old_name in sorted(remaining_old):
        old_entity = old_kg.entities[old_name]
        old_props = {p.name for p in old_entity.properties}
        best_score = 0.0
        best_new = ""

        for new_name in remaining_new - matched_new:
            new_entity = new_kg.entities[new_name]
            new_props = {p.name for p in new_entity.properties}

            prop_sim = _jaccard(old_props, new_props)
            name_sim = _name_similarity(old_name, new_name)
            combined = 0.6 * prop_sim + 0.4 * name_sim

            if combined > best_score:
                best_score = combined
                best_new = new_name

        if best_score >= 0.7 and best_new:
            renames.append((old_name, best_new))
            matched_old.add(old_name)
            matched_new.add(best_new)

    return renames


def _detect_property_renames(
    removed_props: set[str],
    added_props: set[str],
    old_prop_map: dict[str, Property],
    new_prop_map: dict[str, Property],
) -> list[tuple[str, str]]:
    """Detect property renames within an entity.

    Matches removed and added property names that have similar names
    and identical or near-identical signatures.
    """
    renames: list[tuple[str, str]] = []
    matched_old: set[str] = set()
    matched_new: set[str] = set()

    for old_name in sorted(removed_props):
        old_sig = _prop_signature(old_prop_map[old_name])
        best_score = 0.0
        best_new = ""

        for new_name in added_props - matched_new:
            new_sig = _prop_signature(new_prop_map[new_name])
            # Signatures must be identical or differ only in description-level fields
            sig_match = old_sig == new_sig
            name_sim = _name_similarity(old_name, new_name)

            if sig_match and name_sim >= 0.6:
                if name_sim > best_score:
                    best_score = name_sim
                    best_new = new_name

        if best_new:
            renames.append((old_name, best_new))
            matched_old.add(old_name)
            matched_new.add(best_new)

    return renames


def _detect_enum_value_renames(
    removed_vals: list[str],
    added_vals: list[str],
) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """Detect renamed enum values using normalized matching.

    Returns (renamed_pairs, remaining_removed, remaining_added).
    """
    renames: list[tuple[str, str]] = []
    matched_old: set[str] = set()
    matched_new: set[str] = set()

    # Build normalized index of added values
    added_norm: dict[str, str] = {_normalize(v): v for v in added_vals}

    for old_val in removed_vals:
        norm = _normalize(old_val)
        if norm in added_norm:
            new_val = added_norm[norm]
            if new_val not in matched_new:
                renames.append((old_val, new_val))
                matched_old.add(old_val)
                matched_new.add(new_val)

    remaining_removed = [v for v in removed_vals if v not in matched_old]
    remaining_added = [v for v in added_vals if v not in matched_new]
    return renames, remaining_removed, remaining_added


# ---------------------------------------------------------------------------
# Property-level diff helpers
# ---------------------------------------------------------------------------

def _prop_signature(prop: Property) -> dict[str, Any]:
    """Return a stable dict representing the essential fields of a property."""
    return {
        "type": prop.property_type.value,
        "required": prop.required,
        "cardinality": prop.cardinality.value,
        "reference_target": prop.reference_target,
        "array_item_type": prop.array_item_type,
        "deprecated": prop.deprecated,
    }


def _describe_prop_changes(old_prop: Property, new_prop: Property) -> str:
    """Produce a human-readable description of what changed in a property."""
    old_sig = _prop_signature(old_prop)
    new_sig = _prop_signature(new_prop)
    changes: list[str] = []
    for key in old_sig:
        if old_sig[key] != new_sig[key]:
            changes.append(f"{key}: {old_sig[key]!r} -> {new_sig[key]!r}")
    return "; ".join(changes) if changes else "description updated"


# ---------------------------------------------------------------------------
# Entity-level diff
# ---------------------------------------------------------------------------

def _diff_entity_properties(
    old_entity: Entity,
    new_entity: Entity,
) -> str | None:
    """Diff properties between two versions of the same entity.

    Returns a details string if there are changes, None otherwise.
    """
    old_props = {p.name: p for p in old_entity.properties}
    new_props = {p.name: p for p in new_entity.properties}

    added_props = set(new_props) - set(old_props)
    removed_props = set(old_props) - set(new_props)

    # Detect property renames within this entity
    prop_renames = _detect_property_renames(
        removed_props, added_props, old_props, new_props,
    )
    renamed_old = {r[0] for r in prop_renames}
    renamed_new = {r[1] for r in prop_renames}
    added_props -= renamed_new
    removed_props -= renamed_old

    changed_props: list[str] = []
    for prop_name in sorted(set(old_props) & set(new_props)):
        old_sig = _prop_signature(old_props[prop_name])
        new_sig = _prop_signature(new_props[prop_name])
        if old_sig != new_sig:
            changed_props.append(
                f"{prop_name}: "
                f"{_describe_prop_changes(old_props[prop_name], new_props[prop_name])}"
            )

    if added_props or removed_props or changed_props or prop_renames:
        parts: list[str] = []
        if prop_renames:
            rename_strs = [f"{old} -> {new}" for old, new in prop_renames]
            parts.append(f"renamed properties: {', '.join(rename_strs)}")
        if sorted(added_props):
            parts.append(f"added properties: {', '.join(sorted(added_props))}")
        if sorted(removed_props):
            parts.append(f"removed properties: {', '.join(sorted(removed_props))}")
        if changed_props:
            parts.append(f"modified properties: {'; '.join(changed_props)}")
        return " | ".join(parts)

    return None


def _diff_entities(
    old_kg: KnowledgeGraph,
    new_kg: KnowledgeGraph,
) -> list[EntityChange]:
    """Return EntityChange entries for added, removed, modified, renamed, and deprecated entities.
    """
    changes: list[EntityChange] = []

    old_names = set(old_kg.entities)
    new_names = set(new_kg.entities)

    purely_added = new_names - old_names
    purely_removed = old_names - new_names

    # Detect renames among added/removed pairs
    entity_renames = _detect_entity_renames(
        purely_removed, purely_added, old_kg, new_kg,
    )
    renamed_old = {r[0] for r in entity_renames}
    renamed_new = {r[1] for r in entity_renames}

    # Emit rename entries (with property-level diff on the renamed entity)
    for old_name, new_name in sorted(entity_renames):
        old_entity = old_kg.entities[old_name]
        new_entity = new_kg.entities[new_name]
        detail_parts = [f"{old_name} -> {new_name}"]

        prop_details = _diff_entity_properties(old_entity, new_entity)
        if prop_details:
            detail_parts.append(prop_details)

        changes.append(EntityChange(
            entity_name=new_name,
            change_type=ChangeType.RENAMED,
            details=" | ".join(detail_parts),
            old_value=old_name,
            new_value=new_name,
        ))

    # Added entities (excluding renames)
    for name in sorted(purely_added - renamed_new):
        entity = new_kg.entities[name]
        details = f"Added entity with {len(entity.properties)} properties"
        changes.append(EntityChange(
            entity_name=name,
            change_type=ChangeType.ADDED,
            details=details,
            new_value=name,
        ))

    # Removed entities (excluding renames)
    for name in sorted(purely_removed - renamed_old):
        changes.append(EntityChange(
            entity_name=name,
            change_type=ChangeType.REMOVED,
            details="Entity removed",
            old_value=name,
        ))

    # Modified entities (present in both, not renamed)
    for name in sorted(old_names & new_names):
        old_entity = old_kg.entities[name]
        new_entity = new_kg.entities[name]

        # Check for newly deprecated
        if not old_entity.deprecated and new_entity.deprecated:
            changes.append(EntityChange(
                entity_name=name,
                change_type=ChangeType.DEPRECATED,
                details="Entity marked deprecated",
            ))
            continue

        # Compare properties with rename detection
        prop_details = _diff_entity_properties(old_entity, new_entity)
        if prop_details:
            changes.append(EntityChange(
                entity_name=name,
                change_type=ChangeType.MODIFIED,
                details=prop_details,
            ))

    return changes


# ---------------------------------------------------------------------------
# Validation rule diff
# ---------------------------------------------------------------------------

def _diff_rules(
    old_kg: KnowledgeGraph,
    new_kg: KnowledgeGraph,
) -> list[EntityChange]:
    """Return EntityChange entries for added and removed validation rules."""
    changes: list[EntityChange] = []

    old_rules = {r.rule_id: r for r in old_kg.validation_rules}
    new_rules = {r.rule_id: r for r in new_kg.validation_rules}

    for rule_id in sorted(set(new_rules) - set(old_rules)):
        rule = new_rules[rule_id]
        changes.append(EntityChange(
            entity_name=rule_id,
            change_type=ChangeType.ADDED,
            details=f"Rule added: {rule.description[:120]}",
            new_value=rule.severity.value,
        ))

    for rule_id in sorted(set(old_rules) - set(new_rules)):
        rule = old_rules[rule_id]
        changes.append(EntityChange(
            entity_name=rule_id,
            change_type=ChangeType.REMOVED,
            details=f"Rule removed: {rule.description[:120]}",
            old_value=rule.severity.value,
        ))

    for rule_id in sorted(set(old_rules) & set(new_rules)):
        old_rule = old_rules[rule_id]
        new_rule = new_rules[rule_id]
        diffs: list[str] = []
        if old_rule.severity != new_rule.severity:
            diffs.append(f"severity: {old_rule.severity.value} -> {new_rule.severity.value}")
        if old_rule.phase != new_rule.phase:
            diffs.append(f"phase: {old_rule.phase.value} -> {new_rule.phase.value}")
        if old_rule.description != new_rule.description:
            diffs.append("description changed")
        if diffs:
            changes.append(EntityChange(
                entity_name=rule_id,
                change_type=ChangeType.MODIFIED,
                details=" | ".join(diffs),
                old_value=old_rule.severity.value,
                new_value=new_rule.severity.value,
            ))

    return changes


# ---------------------------------------------------------------------------
# Enum type diff
# ---------------------------------------------------------------------------

def _diff_enums(
    old_kg: KnowledgeGraph,
    new_kg: KnowledgeGraph,
) -> list[EntityChange]:
    """Return EntityChange entries for added, removed, and modified enum types."""
    changes: list[EntityChange] = []

    old_enums = old_kg.enum_types
    new_enums = new_kg.enum_types

    for name in sorted(set(new_enums) - set(old_enums)):
        enum = new_enums[name]
        changes.append(EntityChange(
            entity_name=name,
            change_type=ChangeType.ADDED,
            details=f"Enum added with {len(enum.values)} values: {', '.join(enum.values[:5])}",
        ))

    for name in sorted(set(old_enums) - set(new_enums)):
        changes.append(EntityChange(
            entity_name=name,
            change_type=ChangeType.REMOVED,
            details="Enum type removed",
        ))

    for name in sorted(set(old_enums) & set(new_enums)):
        old_enum = old_enums[name]
        new_enum = new_enums[name]
        raw_added = sorted(set(new_enum.values) - set(old_enum.values))
        raw_removed = sorted(set(old_enum.values) - set(new_enum.values))

        if not raw_added and not raw_removed:
            continue

        # Detect value renames (e.g. "tradesecret" -> "trade-secret")
        value_renames, remaining_removed, remaining_added = _detect_enum_value_renames(
            raw_removed, raw_added,
        )

        parts: list[str] = []
        if value_renames:
            rename_strs = [f"{old} -> {new}" for old, new in value_renames]
            parts.append(f"renamed values: {', '.join(rename_strs)}")
        if remaining_added:
            parts.append(f"added values: {', '.join(remaining_added)}")
        if remaining_removed:
            parts.append(f"removed values: {', '.join(remaining_removed)}")

        changes.append(EntityChange(
            entity_name=name,
            change_type=ChangeType.MODIFIED,
            details=" | ".join(parts),
            old_value=str(len(old_enum.values)),
            new_value=str(len(new_enum.values)),
        ))

    return changes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_changelog(
    old_kg: KnowledgeGraph,
    new_kg: KnowledgeGraph,
) -> VersionChangelog:
    """Generate a structured diff between two KnowledgeGraph instances.

    Args:
        old_kg: The earlier knowledge graph (from version).
        new_kg: The later knowledge graph (to version).

    Returns:
        A VersionChangelog with categorised EntityChange objects.
    """
    return VersionChangelog(
        from_version=old_kg.version.version,
        to_version=new_kg.version.version,
        entity_changes=_diff_entities(old_kg, new_kg),
        rule_changes=_diff_rules(old_kg, new_kg),
        enum_changes=_diff_enums(old_kg, new_kg),
    )


def emit_changelog_json(changelog: VersionChangelog, output_path: Path) -> None:
    """Serialize a VersionChangelog to a structured JSON file.

    Args:
        changelog: The changelog to emit.
        output_path: Destination .json file path.
    """
    doc = changelog.to_dict()

    # Add summary counts for quick scanning
    doc["summary"] = {
        "entity_changes": len(changelog.entity_changes),
        "rule_changes": len(changelog.rule_changes),
        "enum_changes": len(changelog.enum_changes),
        "total_changes": (
            len(changelog.entity_changes)
            + len(changelog.rule_changes)
            + len(changelog.enum_changes)
        ),
    }

    # Group entity changes by change type for readability
    by_type: dict[str, list[dict[str, Any]]] = {}
    for change in changelog.entity_changes:
        key = change.change_type.value
        by_type.setdefault(key, []).append(change.to_dict())
    doc["entity_changes_by_type"] = by_type

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
