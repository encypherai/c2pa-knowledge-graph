# Contributing

## Development setup

```bash
git clone https://github.com/encypher-ai/c2pa-knowledge-graph.git
cd c2pa-knowledge-graph
uv sync
```

Run the tests:

```bash
uv run pytest
```

Run lint and format checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

## Adding a new spec version

1. Add a `SpecVersion` entry to `SPEC_VERSIONS` in
   `src/c2pa_kg/versioning/manager.py`. The `tag` field must match the git tag in
   `c2pa-org/specs-core` exactly (bare number, no `v` prefix).

2. Run `c2pa-kg generate --version <new-version> ...` against a local specs-core clone
   and verify the artifact counts look plausible.

3. Run `c2pa-kg diff --from <previous> --to <new-version>` and sanity-check the
   changelog against the spec release notes.

4. Add a test in `tests/` covering the new version's entity count or a known entity.

## Parser changes

The four parsers (`cddl.py`, `json_schema.py`, `asciidoc.py`) produce `Entity`,
`EnumType`, `ValidationRule`, and `StatusCode` objects. They must not import from each
other. The IR builder (`ir_builder.py`) is the only place where parser outputs merge.

When a new spec version changes how source files are structured (new subdirectory paths,
renamed files), update the path constants at the top of `ir_builder.py`.

## Emitter changes

Emitters consume the `KnowledgeGraph` IR and write files. They must not call parsers or
touch the git repo. Keep emitters stateless: same input produces same output.

## Code style

- Python 3.11+ type annotations throughout.
- `ruff` for lint and format. Configuration is in `pyproject.toml`.
- Docstrings on all public functions, using the Google style (Args/Returns/Raises).
- ASCII-only source files and documentation. No Unicode arrows, box-drawing, or
  non-ASCII punctuation.
- No `@ts-ignore` equivalents: fix type errors at their root.

## Commit messages

Use imperative subject lines with a conventional commit prefix:

```
feat(versioning): add spec version 2.5
fix(cddl): handle optional group entries with bare type
docs: update quick-start example for uv 0.5
```

One commit per logical change. Do not bundle unrelated fixes.

## Reporting issues

Open an issue at https://github.com/encypher-ai/c2pa-knowledge-graph/issues. Include
the spec version, the command you ran, and the full error output.
