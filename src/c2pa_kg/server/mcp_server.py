"""MCP server exposing the C2PA knowledge graph to AI agents.

Loads pre-generated KG JSON files from an output directory and exposes them
via resources and tools using the FastMCP high-level API.
"""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from c2pa_kg.versioning.manager import list_versions


def create_server(output_dir: Path) -> FastMCP:
    """Create and configure the MCP server.

    The server loads KG data lazily on first request per version from
    ``{output_dir}/{version}/metadata.json``.

    Args:
        output_dir: Directory containing pre-generated KG output, one
            sub-directory per spec version.

    Returns:
        A configured FastMCP server instance ready to run.
    """
    mcp = FastMCP(
        name="c2pa-knowledge-graph",
        instructions=(
            "Query the C2PA specification knowledge graph. "
            "Use list_versions() or the c2pa://versions resource to discover "
            "available versions before querying entities or rules."
        ),
    )

    # Per-version KG cache: version string -> parsed metadata dict.
    _cache: dict[str, dict] = {}

    def _load_version(version: str) -> dict:
        """Load and cache the KG metadata for a spec version.

        Args:
            version: Version string (e.g. "2.4").

        Returns:
            The parsed metadata.json dict for this version.

        Raises:
            FileNotFoundError: If the metadata file does not exist.
            ValueError: If the metadata file is malformed JSON.
        """
        if version in _cache:
            return _cache[version]
        metadata_path = output_dir / version / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"No pre-generated KG found for version {version!r}. "
                f"Run `c2pa-kg generate --version {version}` first."
            )
        with metadata_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
        _cache[version] = data
        return data

    # ------------------------------------------------------------------
    # Resources
    # ------------------------------------------------------------------

    @mcp.resource(
        "c2pa://versions",
        name="versions",
        description="List all known C2PA specification versions with release dates.",
        mime_type="application/json",
    )
    def resource_versions() -> str:
        versions = [sv.to_dict() for sv in list_versions()]
        return json.dumps(versions, indent=2)

    @mcp.resource(
        "c2pa://{version}/entities",
        name="entities",
        description="List all entity type names defined in a specific spec version.",
        mime_type="application/json",
    )
    def resource_entities(version: str) -> str:
        kg = _load_version(version)
        entities = list(kg.get("entities", {}).keys())
        return json.dumps({"version": version, "entities": entities}, indent=2)

    @mcp.resource(
        "c2pa://{version}/entity/{name}",
        name="entity",
        description=(
            "Full definition of a single entity type, including properties "
            "and relationships."
        ),
        mime_type="application/json",
    )
    def resource_entity(version: str, name: str) -> str:
        kg = _load_version(version)
        entities: dict = kg.get("entities", {})
        if name not in entities:
            available = list(entities.keys())
            raise KeyError(
                f"Entity {name!r} not found in version {version!r}. "
                f"Available: {available}"
            )
        return json.dumps(
            {"version": version, "entity": entities[name]}, indent=2
        )

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @mcp.tool(
        name="query_entity",
        description=(
            "Get the full definition of a C2PA entity type as JSON, "
            "including its properties, relationships, and spec section."
        ),
    )
    def query_entity(version: str, name: str) -> str:
        """Retrieve a single entity definition from the knowledge graph.

        Args:
            version: Spec version string (e.g. "2.4").
            name: Entity name (e.g. "Manifest", "Claim").

        Returns:
            JSON string with the entity definition.
        """
        kg = _load_version(version)
        entities: dict = kg.get("entities", {})
        if name not in entities:
            available = sorted(entities.keys())
            return json.dumps(
                {
                    "error": f"Entity {name!r} not found in version {version!r}.",
                    "available_entities": available,
                },
                indent=2,
            )
        return json.dumps(
            {"version": version, "entity": entities[name]}, indent=2
        )

    @mcp.tool(
        name="query_validation_rules",
        description=(
            "Retrieve normative validation rules for a spec version, "
            "optionally filtered by validation phase "
            "(structural, cryptographic, trust, semantic, assertion, "
            "ingredient, timestamp, signature, content)."
        ),
    )
    def query_validation_rules(
        version: str, phase: str | None = None
    ) -> str:
        """Get validation rules, optionally filtered by phase.

        Args:
            version: Spec version string (e.g. "2.4").
            phase: Optional ValidationPhase value to filter on. Pass None
                   to return all rules.

        Returns:
            JSON string with the matching rules list.
        """
        kg = _load_version(version)
        rules: list[dict] = kg.get("validation_rules", [])
        if phase is not None:
            rules = [r for r in rules if r.get("phase") == phase]
        return json.dumps(
            {"version": version, "phase": phase, "rules": rules}, indent=2
        )

    @mcp.tool(
        name="diff_versions",
        description=(
            "Produce a structured diff between two C2PA spec versions, "
            "showing added, removed, modified, and deprecated entities."
        ),
    )
    def diff_versions(from_version: str, to_version: str) -> str:
        """Compare two spec versions and return a structured changelog.

        Loads metadata for both versions and computes entity-level diffs.
        For property-level diffs, run `c2pa-kg diff` which uses the full
        changelog emitter.

        Args:
            from_version: Earlier version string (e.g. "2.2").
            to_version: Later version string (e.g. "2.4").

        Returns:
            JSON string describing the diff between the two versions.
        """
        from_kg = _load_version(from_version)
        to_kg = _load_version(to_version)

        from_entities: set[str] = set(from_kg.get("entities", {}).keys())
        to_entities: set[str] = set(to_kg.get("entities", {}).keys())

        added = sorted(to_entities - from_entities)
        removed = sorted(from_entities - to_entities)

        modified: list[str] = []
        for name in sorted(from_entities & to_entities):
            if from_kg["entities"][name] != to_kg["entities"][name]:
                modified.append(name)

        from_rules: list[dict] = from_kg.get("validation_rules", [])
        to_rules: list[dict] = to_kg.get("validation_rules", [])
        from_rule_ids = {r.get("rule_id", "") for r in from_rules}
        to_rule_ids = {r.get("rule_id", "") for r in to_rules}
        rules_added = sorted(to_rule_ids - from_rule_ids)
        rules_removed = sorted(from_rule_ids - to_rule_ids)

        diff = {
            "from_version": from_version,
            "to_version": to_version,
            "entities": {
                "added": added,
                "removed": removed,
                "modified": modified,
            },
            "rules": {
                "added": rules_added,
                "removed": rules_removed,
            },
            "summary": {
                "entities_added": len(added),
                "entities_removed": len(removed),
                "entities_modified": len(modified),
                "rules_added": len(rules_added),
                "rules_removed": len(rules_removed),
            },
        }
        return json.dumps(diff, indent=2)

    @mcp.tool(
        name="search_entities",
        description=(
            "Full-text search over entity names and descriptions in a "
            "specific spec version. Returns all entities whose name or "
            "description contains the query string (case-insensitive)."
        ),
    )
    def search_entities(version: str, query: str) -> str:
        """Search entity names and descriptions for a query string.

        Args:
            version: Spec version string (e.g. "2.4").
            query: Search term (case-insensitive substring match).

        Returns:
            JSON string with matching entity names and their descriptions.
        """
        kg = _load_version(version)
        entities: dict = kg.get("entities", {})
        needle = query.lower()
        matches: list[dict] = []
        for name, entity in entities.items():
            description: str = entity.get("description", "")
            if needle in name.lower() or needle in description.lower():
                matches.append(
                    {
                        "name": name,
                        "description": description,
                    }
                )
        return json.dumps(
            {
                "version": version,
                "query": query,
                "count": len(matches),
                "results": matches,
            },
            indent=2,
        )

    return mcp
