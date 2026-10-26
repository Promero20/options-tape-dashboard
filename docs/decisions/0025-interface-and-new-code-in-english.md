# 0025. Interface, new code and stored values in English

- **Date:** 2026-10-26
- **Status:** accepted (supersedes part of [0024](0024-documentation-language.md))

## Context

Decision 0024 put the documentation in English and left code comments, interface text and the values stored in the edits file in Spanish, pending a decision. Phase 3 builds the interface, and the repository is now public. The interface also shows text produced by the data layer (warnings, validation states, classification labels), so translating only the screens would leave them half in Spanish.

## Decision

- **Interface in English**, and so is every text it shows that comes from the data, rules and edits layers: `Issue` messages and severities (`error`, `warning`, `info`), validation states, classification values (destinations `net`, `walls`, `undetermined`, `undetermined multi-leg`, `discarded`, `pending`; directions `bull`, `bear`, `undetermined`; walls `support`, `resistance`; sides `buy`, `sell`), structure and reason texts, and the command-line report.
- **Values stored in the edits file in English**: the file is renamed `edits.sqlite`, the direction is `bull`, `bear` or `undetermined`, and the operation-type keys are English (`long_straddle`, `diagonal_buy_near`, `unknown`…). No real edits file existed yet, so no migration is needed.
- **New code in English**, comments and docstrings included.
- **Unchanged**: the level-3 script and the CSV names (0024). Comments and docstrings of the code written before this decision are still in Spanish and will be translated later.

## Rejected alternatives

- **Spanish interface**: the screens would not match a public repository documented in English.
- **Bilingual interface with a language selector**: more work and more to test for a single user.

## Consequences

The command-line report and the warnings change language; tests that asserted the Spanish texts were updated.
