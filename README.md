# C2PA Knowledge Graph

The C2PA specification as versioned, machine-readable knowledge graphs. Each published
spec version has its own git tag and commit containing structured artifacts - entities,
properties, relationships, validation rules, enum types, and status codes - ready to
load as JSON, query via RDF/OWL, or serve to AI agents through the Model Context Protocol.

No build step required. Fetch one file and start working:

```
https://raw.githubusercontent.com/encypherai/c2pa-knowledge-graph/spec-current/spec-version.json
```

This evergreen URL always points to the current C2PA spec version. It returns a JSON
pointer with direct URLs to all artifacts. See [Direct URLs](#direct-urls-no-clone-required) below.

## Versioning

Tags follow `v1.{spec_version}`, where the leading `1` is the knowledge graph generation
and the rest is the C2PA spec version:

| Tag | C2PA Spec | Entities | Rules |
|-----|-----------|----------|-------|
| `v1.2.4` | 2.4 | 148 | 237 |
| `v1.2.3` | 2.3 | 98 | 233 |
| `v1.2.2` | 2.2 | 86 | 203 |
| `v1.2.1` | 2.1 | 81 | 159 |
| `v1.2.0` | 2.0 | 74 | 129 |
| `v1.1.4` | 1.4 | 74 | 131 |
| `v1.1.3` | 1.3 | 64 | 102 |
| `v1.1.2` | 1.2 | 44 | 82 |
| `v1.1.1` | 1.1 | 44 | 82 |
| `v1.1.0` | 1.0 | 42 | 75 |
| `v1.0.8` | 0.8 | 0 | 0 |
| `v1.0.7` | 0.7 | 0 | 0 |

The **`spec-current`** tag always points to the latest spec version (currently v2.4).

To fetch a specific version:

```bash
# Latest spec
git checkout spec-current

# Specific version
git checkout v1.2.4
```

## Direct URLs (no clone required)

Every tag has a `spec-version.json` pointer at the repo root. An agent can fetch this
single file to discover the current spec version and artifact URLs:

```
# Always-current spec (follows spec-current tag)
https://raw.githubusercontent.com/encypherai/c2pa-knowledge-graph/spec-current/spec-version.json

# Specific version
https://raw.githubusercontent.com/encypherai/c2pa-knowledge-graph/v1.2.4/spec-version.json
```

Or fetch artifacts directly:

```
# Current spec metadata (always latest)
https://raw.githubusercontent.com/encypherai/c2pa-knowledge-graph/spec-current/versions/2.4/metadata.json

# Specific older version
https://raw.githubusercontent.com/encypherai/c2pa-knowledge-graph/v1.1.4/versions/1.4/metadata.json
```

The `spec-version.json` file contains relative paths and full URLs for all five artifacts,
so an agent loading it knows exactly where to find everything without parsing tag names.

## Load a knowledge graph

To load the v2.4 knowledge graph:

```python
import json
from pathlib import Path

data = json.loads(Path("versions/2.4/metadata.json").read_text())

# Browse entities
for name, entity in data["entities"].items():
    print(name, [p["name"] for p in entity["properties"]])

# Check a specific entity
claim = data["entities"]["ClaimMapV2"]
for prop in claim["properties"]:
    req = "required" if prop["required"] else "optional"
    print(f"  {prop['name']}: {prop['type']} ({req})")

# List validation rules by phase
for rule in data["validation_rules"]:
    if rule["phase"] == "assertion":
        print(f"  [{rule['severity']}] {rule['description'][:80]}")

# Enumerate enum types
for name, enum in data["enum_types"].items():
    print(f"  {name}: {len(enum['values'])} values")

# Look up type aliases (simple CDDL types not modeled as full entities)
for name, alias in data["type_aliases"].items():
    print(f"  {name}: base_type={alias['base_type']}")
```

Each version directory contains five files:

| File | Format | Contents |
|------|--------|----------|
| `metadata.json` | JSON | Complete knowledge graph: entities, properties, relationships, enums, type aliases, rules, status codes |
| `ontology.ttl` | Turtle (RDF/OWL) | OWL class hierarchy with property definitions and cardinality constraints |
| `context.jsonld` | JSON-LD | Term definitions for embedding in C2PA manifests |
| `validation-rules.json` | JSON | Normative rules grouped by validation phase with RFC 2119 severity |
| `predicates.json` | JSON | Deterministic conformance predicates with test vectors, grouped by MIME format family |

## Conformance predicates

The `predicates.json` artifact translates normative validation rules from prose into
deterministic, machine-checkable conditions. Each predicate formalizes one or more
SHALL/MUST rules into structured logic that a conformance test harness can evaluate
without human judgment.

Predicates cover every binding mechanism in the v2.4 spec and every MIME type
supported by the c2pa-rs SDK:

| Family | MIME Types | Binding | Predicates |
|--------|-----------|---------|------------|
| `text_plain` | text/plain, text/markdown | C2PATextManifestWrapper | 2 |
| `image` | image/jpeg, image/png, image/webp, image/tiff, image/heif | c2pa.hash.data | 4 |
| `video_bmff` | video/mp4, video/quicktime, audio/mp4, image/avif, image/heif | c2pa.hash.bmff | 4 |
| `audio_wav` | audio/wav, audio/flac, audio/aiff, audio/mpeg | c2pa.hash.data | 2 |
| `document_pdf` | application/pdf | c2pa.hash.data | 3 |
| `multi_asset` | compound assets | c2pa.hash.multi-asset | 3 |
| `boxes_hash` | image/jxl, font/ttf, font/otf, image/jpeg (APP11) | c2pa.hash.boxes | 11 |
| `collection_hash` | application/zip | c2pa.hash.collection | 5 |
| `structured_text` | image/svg+xml, application/xhtml+xml | structured text blocks | 3 |
| `streaming_bmff` | video/mp4, audio/mp4 (progressive) | c2pa.hash.bmff | 2 |
| Cross-cutting | all formats | all bindings | 6 |

Each predicate includes source rule IDs, structured conditions, and test vectors
(passing and failing manifest fragments). The file also includes a `c2pa_rs_comparison`
section mapping each c2pa-rs SDK format handler to its corresponding predicates.

```python
import json
from pathlib import Path

preds = json.loads(Path("versions/2.4/predicates.json").read_text())

# List all predicates for image validation
for p in preds["format_families"]["image"]["predicates"]:
    print(f"{p['predicate_id']}: {p['title']}")
    print(f"  Rules: {p['source_rules']}")
    print(f"  Severity: {p['severity']}")

# Check c2pa-rs format coverage
for handler, info in preds["c2pa_rs_comparison"]["c2pa_rs_handlers"].items():
    print(f"{handler}: {info['coverage']} -- {info['our_predicates']}")

# Get test vectors for a specific predicate
img_pred = preds["format_families"]["image"]["predicates"][0]
for name, vector in img_pred["test_vectors"].items():
    print(f"  {name}: {vector.get('expected_result', vector.get('expected_status'))}")
```

The v2.4 predicates contain 145 conformance predicates formalizing 237/237 validation
rules (100% coverage), spanning 10 format families plus a cross-cutting section.
Coverage maps to 100% of the 12 c2pa-rs format handlers, plus three format families
the SDK does not yet implement (fonts, ZIP collections, unstructured text). Predicates
are hand-maintained because translating normative prose into executable logic requires
human judgment about the spec's intent.

## Regenerating from source

Most users do not need this section. The pre-generated artifacts in `versions/` are
the primary deliverable. Use the generator only when a new spec version is released
and this repo has not been updated yet.

```bash
# Install
git clone https://github.com/encypherai/c2pa-knowledge-graph.git
cd c2pa-knowledge-graph
uv sync

# Clone the C2PA spec source (needed at generation time only)
git clone https://github.com/c2pa-org/specs-core.git /tmp/specs-core

# Generate artifacts for a single version
uv run c2pa-kg generate \
  --spec-source /tmp/specs-core \
  --version 2.4 \
  --output-dir ./output

# Inspect results
ls ./output/2.4/
# ontology.ttl  context.jsonld  validation-rules.json  metadata.json
```

**Requirements:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Git.

## CLI reference

### `generate`

Build knowledge graph artifacts for a single spec version.

```bash
uv run c2pa-kg generate \
  --spec-source <path-to-specs-core> \
  --version <version> \
  --output-dir <output-dir>
```

The command checks out the corresponding git tag in the specs-core repo, parses all
source files, and writes four artifacts to `<output-dir>/<version>/`.

| Flag | Required | Description |
|------|----------|-------------|
| `--spec-source` | Yes | Path to local `specs-core` git clone |
| `--version` | Yes | Spec version string, e.g. `2.4` |
| `--output-dir` | Yes | Output root; version subdirectory created automatically |

### `generate-all`

Build artifacts for all 12 known spec versions in sequence.

```bash
uv run c2pa-kg generate-all \
  --spec-source /tmp/specs-core \
  --output-dir ./output
```

### `diff`

Compare two spec versions and print a structured JSON changelog. Detects renamed
entities, renamed properties, renamed enum values, and standard additions/removals/modifications.

```bash
uv run c2pa-kg diff \
  --output-dir ./versions \
  --from 1.4 \
  --to 2.4
```

Both versions must have pre-generated `metadata.json` files. Output is JSON, suitable
for piping to `jq`.

### `list-versions`

Print all known spec versions with their release dates.

```bash
uv run c2pa-kg list-versions
```

### `serve`

Start an MCP server that exposes knowledge graph data to AI agents.

```bash
uv run c2pa-kg serve \
  --output-dir ./versions \
  --port 8000
```

The server loads each version's `metadata.json` lazily on first request.

## MCP server

### Resources

| URI | Description |
|-----|-------------|
| `c2pa://versions` | All known spec versions with release dates |
| `c2pa://{version}/entities` | List of all entity type names in a version |
| `c2pa://{version}/entity/{name}` | Full definition of one entity type |

### Tools

| Tool | Arguments | Description |
|------|-----------|-------------|
| `query_entity` | `version`, `name` | Full entity definition with properties and relationships |
| `query_validation_rules` | `version`, `phase?` | Normative rules, optionally filtered by validation phase |
| `diff_versions` | `from_version`, `to_version` | Structured diff with rename detection |
| `search_entities` | `version`, `query` | Case-insensitive search over entity names and descriptions |

Validation phases: `structural`, `cryptographic`, `trust`, `semantic`, `assertion`,
`ingredient`, `timestamp`, `signature`, `content`.

### Configuring in Claude Code

Add to `~/.claude/mcp_settings.json` or the project-level `.claude/mcp_settings.json`:

```json
{
  "mcpServers": {
    "c2pa-knowledge-graph": {
      "command": "uv",
      "args": [
        "run",
        "--project", "/path/to/c2pa-knowledge-graph",
        "c2pa-kg", "serve",
        "--output-dir", "/path/to/c2pa-knowledge-graph/versions",
        "--port", "8000"
      ],
      "transport": "streamable-http",
      "url": "http://127.0.0.1:8000"
    }
  }
}
```

Replace `/path/to/c2pa-knowledge-graph` with your clone path.

## How artifacts are generated

The generator pipeline parses C2PA spec source files and emits structured artifacts.
This section is relevant if you are contributing or regenerating.

```
specs-core repository
    |
    +-- cddl/              -> cddl.py          (primary: entities, enums, properties)
    +-- crJSON.schema.json  -> json_schema.py   (secondary: fills description gaps)
    +-- Validation.adoc     -> asciidoc.py      (validation rules, status codes)
    +-- Standard_Assertions -> asciidoc.py      (assertion descriptions)
    |
    v
ir_builder.py  (merges parser outputs into KnowledgeGraph IR)
    |
    +-- emitters/turtle.py    -> ontology.ttl
    +-- emitters/jsonld.py    -> context.jsonld
    +-- emitters/rules.py     -> validation-rules.json
    +-- emitters/changelog.py -> version diffs with rename detection
    |
    v
metadata.json  (full IR, loaded by MCP server and Claude Code skill)
```

CDDL schemas are authoritative for entity structure. JSON Schema descriptions fill
fields the CDDL leaves blank. AsciiDoc provides normative validation rules and
assertion descriptions. The IR builder infers cross-entity relationships by resolving
`REFERENCE` and `ARRAY` property targets.

## Spec version notes

All 12 published C2PA spec versions are covered (see [Versioning](#versioning) for the
full tag table). Notable details:

- **v2.3** (2025-12-01): Adds live video and unstructured text support.
- **v0.7, v0.8** (2021): Pre-CDDL drafts with no machine-readable schemas; artifacts are minimal.

## Known upstream issues

The C2PA specification embeds schema URLs in manifest structures that do not resolve.
As of April 2026, the following URLs return HTTP 404:

- `https://c2pa.org/specifications/specifications/2.4/schema/c2pa.schema.json`
- `https://c2pa.org/specifications/specifications/2.1/schema/c2pa.schema.json`
- `https://c2pa.org/specifications/specifications/1.4/schema/c2pa.schema.json`
- `https://c2pa.org/ontology/` (the base namespace used in generated `ontology.ttl`)

This tool works around the 404s by reading source files directly from the git
repository. The generated `ontology.ttl` uses `https://c2pa.org/ontology/` as its
namespace, consistent with what the spec intends but does not yet serve.

## Claude Code skill

This repo ships a Claude Code skill at `.claude/skills/c2pa-kg/SKILL.md`. To make
`/c2pa-kg` available in your sessions:

```bash
ln -s /path/to/c2pa-knowledge-graph/.claude/skills/c2pa-kg ~/.claude/skills/c2pa-kg
```

Example queries:

```
/c2pa-kg ClaimMapV2 properties
/c2pa-kg validation rules for signatures
/c2pa-kg diff 2.2 2.4
```

## Contributing

Bug reports and pull requests welcome at
https://github.com/encypherai/c2pa-knowledge-graph/issues.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and testing.

## License

Source code is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

Generated artifacts are derived from the C2PA specification, licensed under
**CC-BY-4.0**. When redistributing generated artifacts, attribution to C2PA is
required per CC-BY-4.0 Section 3. See [NOTICE](NOTICE) for details.

Copyright 2026 Encypher Corporation
