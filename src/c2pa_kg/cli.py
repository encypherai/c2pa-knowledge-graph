"""Command-line interface for the C2PA Knowledge Graph generator.

Commands:
    generate       Build KG artifacts for one spec version.
    generate-all   Build KG artifacts for all known spec versions.
    serve          Start the MCP server.
    diff           Compare two spec versions and print the changelog.
    list-versions  Print all known spec versions with release dates.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from c2pa_kg.models import KnowledgeGraph, SpecVersion
from c2pa_kg.versioning.manager import (
    checkout_spec_version,
    get_version,
    list_versions,
)

_GITHUB_REPO = "encypherai/c2pa-knowledge-graph"
_GITHUB_RAW = f"https://raw.githubusercontent.com/{_GITHUB_REPO}"


def _write_spec_version_json(version: str, output_dir: Path) -> None:
    """Write spec-version.json pointer file to the output root.

    This file lets agents discover which spec version is available at a given
    tag and provides direct URLs to all artifacts.
    """
    pointer = {
        "spec_version": version,
        "artifacts": {
            "metadata": f"versions/{version}/metadata.json",
            "ontology": f"versions/{version}/ontology.ttl",
            "context": f"versions/{version}/context.jsonld",
            "validation_rules": f"versions/{version}/validation-rules.json",
            "predicates": f"versions/{version}/predicates.json",
        },
        "urls": {
            "metadata": f"{_GITHUB_RAW}/v1.{version}/versions/{version}/metadata.json",
            "ontology": f"{_GITHUB_RAW}/v1.{version}/versions/{version}/ontology.ttl",
            "context": f"{_GITHUB_RAW}/v1.{version}/versions/{version}/context.jsonld",
            "validation_rules": (
                f"{_GITHUB_RAW}/v1.{version}/versions/{version}/validation-rules.json"
            ),
            "predicates": f"{_GITHUB_RAW}/v1.{version}/versions/{version}/predicates.json",
            "current_metadata": f"{_GITHUB_RAW}/spec-current/versions/{version}/metadata.json",
        },
    }
    pointer_path = output_dir / "spec-version.json"
    with pointer_path.open("w", encoding="utf-8") as f:
        json.dump(pointer, f, indent=2, ensure_ascii=False)
        f.write("\n")


@click.group()
def cli() -> None:
    """C2PA Knowledge Graph generator and MCP server."""


@cli.command("generate")
@click.option(
    "--spec-source",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the local clone of the c2pa-org/specs-core repository.",
)
@click.option(
    "--version",
    required=True,
    help="Spec version to generate (e.g. '2.4').",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory where output artifacts are written.",
)
def generate(spec_source: Path, version: str, output_dir: Path) -> None:
    """Build knowledge graph artifacts for a single spec version."""
    try:
        spec_version: SpecVersion = get_version(version)
    except KeyError as exc:
        raise click.BadParameter(str(exc), param_hint="'--version'") from exc

    from c2pa_kg.builders.ir_builder import build_knowledge_graph
    from c2pa_kg.emitters.jsonld import emit_jsonld_context
    from c2pa_kg.emitters.rules import emit_rules_json
    from c2pa_kg.emitters.turtle import emit_turtle

    click.echo(f"Checking out spec version {version} ...")
    try:
        checkout_spec_version(spec_source, version)
    except Exception as exc:
        raise click.ClickException(
            f"Failed to checkout spec version {version}: {exc}"
        ) from exc

    click.echo(f"Building knowledge graph for version {version} ...")
    kg: KnowledgeGraph = build_knowledge_graph(spec_source, spec_version)

    version_dir = output_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"Writing artifacts to {version_dir} ...")

    turtle_path = version_dir / "ontology.ttl"
    emit_turtle(kg, turtle_path)
    click.echo(f"  Wrote {turtle_path}")

    jsonld_path = version_dir / "context.jsonld"
    emit_jsonld_context(kg, jsonld_path)
    click.echo(f"  Wrote {jsonld_path}")

    rules_path = version_dir / "validation-rules.json"
    emit_rules_json(kg, rules_path)
    click.echo(f"  Wrote {rules_path}")

    metadata_path = version_dir / "metadata.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(kg.to_dict(), f, indent=2, ensure_ascii=False)
        f.write("\n")
    click.echo(f"  Wrote {metadata_path}")

    # Write spec-version.json pointer at the output root
    _write_spec_version_json(version, output_dir)
    click.echo(f"  Wrote {output_dir / 'spec-version.json'}")

    click.echo(
        f"Done. {kg.entity_count} entities, "
        f"{kg.relationship_count} relationships, "
        f"{kg.rule_count} validation rules."
    )


@cli.command("generate-all")
@click.option(
    "--spec-source",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Path to the local clone of the c2pa-org/specs-core repository.",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Directory where output artifacts are written.",
)
@click.pass_context
def generate_all(ctx: click.Context, spec_source: Path, output_dir: Path) -> None:
    """Build knowledge graph artifacts for all known spec versions."""
    versions = list_versions()
    failed: list[str] = []

    for sv in versions:
        click.echo(f"\n--- Version {sv.version} ({sv.date}) ---")
        try:
            ctx.invoke(
                generate,
                spec_source=spec_source,
                version=sv.version,
                output_dir=output_dir,
            )
        except (click.ClickException, Exception) as exc:
            click.echo(
                f"ERROR: version {sv.version} failed: {exc}", err=True
            )
            failed.append(sv.version)

    if failed:
        click.echo(
            f"\nCompleted with failures on: {', '.join(failed)}", err=True
        )
        sys.exit(1)
    else:
        click.echo(
            f"\nAll {len(versions)} versions generated successfully."
        )


@cli.command("serve")
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing pre-generated KG output artifacts.",
)
@click.option(
    "--port",
    default=8000,
    show_default=True,
    type=int,
    help="Port to bind the MCP server to.",
)
def serve(output_dir: Path, port: int) -> None:
    """Start the MCP server exposing the knowledge graph to AI agents."""
    from c2pa_kg.server.mcp_server import create_server

    click.echo(f"Starting MCP server on port {port} ...")
    click.echo(f"Output directory: {output_dir}")
    server = create_server(output_dir)
    server.run(transport="streamable-http", host="127.0.0.1", port=port)  # type: ignore[call-arg]


@cli.command("diff")
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing pre-generated KG output artifacts.",
)
@click.option(
    "--from",
    "from_version",
    required=True,
    help="Earlier spec version (e.g. '2.2').",
)
@click.option(
    "--to",
    "to_version",
    required=True,
    help="Later spec version (e.g. '2.4').",
)
def diff(output_dir: Path, from_version: str, to_version: str) -> None:
    """Compare two spec versions and print the structured changelog."""
    from c2pa_kg.emitters.changelog import generate_changelog

    from_path = output_dir / from_version / "metadata.json"
    to_path = output_dir / to_version / "metadata.json"

    for path, label in [(from_path, from_version), (to_path, to_version)]:
        if not path.exists():
            raise click.ClickException(
                f"No pre-generated KG found for version {label!r}. "
                f"Run `c2pa-kg generate --version {label}` first."
            )

    from c2pa_kg.models import kg_from_dict

    with from_path.open(encoding="utf-8") as fh:
        from_data = json.load(fh)
    with to_path.open(encoding="utf-8") as fh:
        to_data = json.load(fh)

    from_kg = kg_from_dict(from_data)
    to_kg = kg_from_dict(to_data)

    changelog = generate_changelog(from_kg, to_kg)
    doc = changelog.to_dict()
    doc["summary"] = {
        "entity_changes": len(changelog.entity_changes),
        "rule_changes": len(changelog.rule_changes),
        "enum_changes": len(changelog.enum_changes),
    }
    click.echo(json.dumps(doc, indent=2))


@cli.command("list-versions")
def list_versions_cmd() -> None:
    """Print all known C2PA spec versions with their release dates."""
    versions = list_versions()
    max_ver_len = max(len(sv.version) for sv in versions)
    click.echo(f"{'Version':<{max_ver_len + 2}}{'Date'}")
    click.echo("-" * (max_ver_len + 2 + 12))
    for sv in versions:
        click.echo(f"{sv.version:<{max_ver_len + 2}}{sv.date}")


if __name__ == "__main__":
    cli()
