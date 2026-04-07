---
name: c2pa-kg
description: >
  Query the C2PA specification knowledge graph. Use when: implementing C2PA,
  checking spec requirements, looking up entity definitions, finding validation
  rules, comparing spec versions, or answering questions about C2PA data structures.
  TRIGGER when: user asks about C2PA entities, manifests, claims, assertions,
  ingredients, validation, trust model, or spec changes between versions.
argument-hint: "[query or entity name, e.g. 'ClaimMap properties' or 'diff 2.2 2.4']"
allowed-tools: Read, Bash, Glob, Grep, Agent
---

# C2PA Knowledge Graph Query

You have access to a machine-readable knowledge graph derived from the C2PA specification.
Use it to answer questions about C2PA data structures, validation rules, and version changes
with precision rather than relying on training data.

## Data sources

The knowledge graph is generated from the C2PA specs-core repository and stored as JSON artifacts.
Check for pre-generated artifacts in this order:

1. **MCP tools** (if c2pa-knowledge-graph MCP server is running): use `query_entity`,
   `query_validation_rules`, `diff_versions`, or `search_entities` tools directly.
2. **Local artifacts**: look for `output/<version>/metadata.json` in the c2pa-knowledge-graph
   repo directory. If found, read and parse the JSON.
3. **Generate on demand**: if no artifacts exist and the user has specs-core cloned locally,
   run `uv run c2pa-kg generate --spec-source <path> --version <version> --output-dir ./output`.

## How to answer queries

### Entity lookup
When asked about a C2PA entity (e.g., "what properties does a Claim have?"):

1. Load `metadata.json` for the requested version (default: latest, currently 2.4).
2. Look up the entity in the `entities` dict. Entity names are CamelCase (e.g., `ClaimMap`,
   `ClaimMapV2`, `ActionItemsMap`, `IngredientMapV3`).
3. Report the entity's properties (name, type, required, cardinality, description),
   relationships (target entity, relationship type), and whether it is deprecated.
4. If the entity name is ambiguous, search across all entity names and suggest matches.

### Validation rules
When asked about validation requirements:

1. Load validation rules from `metadata.json` -> `validation_rules`.
2. Filter by phase if specified: `structural`, `cryptographic`, `trust`, `semantic`,
   `assertion`, `ingredient`, `timestamp`, `signature`, `content`.
3. Report rules with their severity (must/shall/should/may), description, and
   referenced entities.
4. Cross-reference with status codes from `status_codes` when relevant.

### Version comparison
When asked "what changed between X and Y":

1. Load `metadata.json` for both versions.
2. Compare entity sets: report added, removed, and modified entities.
3. For modified entities, compare properties: added/removed/changed fields.
4. Compare validation rule sets: added and removed rules.
5. Compare enum types: added/removed values.

### Search
When the user's question is open-ended:

1. Search entity names and descriptions for keyword matches (case-insensitive).
2. Search validation rule descriptions for the query terms.
3. Report matching entities and rules with their definitions.

## Known spec versions

| Version | Date | Tag |
|---------|------|-----|
| 2.4 | 2026-04-01 | 2.4 |
| 2.3 | 2025-12-01 | 38e492b0 (tag missing upstream) |
| 2.2 | 2025-09-22 | 2.2 |
| 2.1 | 2024-09-26 | 2.1 |
| 2.0 | 2024-01-24 | 2.0 |
| 1.4 | 2023-11-06 | 1.4 |
| 1.3 | 2023-03-30 | 1.3 |
| 1.2 | 2022-11-15 | 1.2 |
| 1.1 | 2022-09-12 | 1.1 |
| 1.0 | 2021-12-24 | 1.0 |
| 0.8 | 2021-11-11 | 0.8 |
| 0.7 | 2021-09-12 | 0.7 |

Version 2.3 (December 2025) covers live video and unstructured text. The upstream
c2pa-org/specs-core repo is missing the `2.3` tag due to a process gap; this tool
targets the merge commit `38e492b0` directly.

## Output format

- Report entity definitions as structured tables (name, type, required, description).
- Report validation rules grouped by phase with severity indicators.
- Report version diffs as categorized lists (added, removed, modified).
- Always cite the spec version number in your response.
- Use precise C2PA terminology: manifests, claims, assertions, ingredients, trust anchors.

## Critical distinction

C2PA (the standard) defines document-level provenance. Entity definitions in this knowledge
graph describe the C2PA standard's data structures. Do not confuse C2PA standard capabilities
with any proprietary extensions built on top of C2PA.
