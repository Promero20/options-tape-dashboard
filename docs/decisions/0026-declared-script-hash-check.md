# 0026. Optional check of the script hash declared by the pipeline

- **Date:** 2026-10-26
- **Status:** accepted

## Context

Before running the level-3 script, the capture pipeline compares its SHA-256 with a value written in the pipeline's own instructions, and stops if they differ. Deploying a new version therefore has two steps: copy the script and update that declared hash ([level-3 script](../level3-script.md#how-to-deploy-a-new-version)). The dashboard already warns when the deployed copy differs from the canonical one, but a forgotten second step only shows up the next day, when level 3 is missing.

## Decision

- An optional setting, `[pipeline] expected_hash_file` in `config.toml` (or the `TAPE_EXPECTED_HASH_FILE` environment variable), points to the file where the pipeline declares the hash.
- If it is set, the dashboard reads that file (read-only) and warns when the SHA-256 of `pipeline/nivel3_agrupar.py` does not appear anywhere in it, ignoring case, or when the file does not exist. The warning appears in the interface banner and in `python -m tape_dashboard.report`.
- The file's format is not assumed, and the code does not name any particular file: which file it is depends on each pipeline.

## Rejected alternatives

- **Parsing a specific table or field**: it would tie the dashboard to the layout of a document it does not own, and break the day that layout changes.
- **A fixed file name in the code**: the repository describes the data contract, not how the data is captured.

## Consequences

- It only checks that the hash appears, not where. A file that mentioned the current hash in some other context would pass; with a declaration that is a single value or a version table, that is enough.
- Without the setting, nothing changes.
