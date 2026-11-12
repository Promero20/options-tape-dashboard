# 0034. The GEX panel is replaced by a link to an external GEX reference

- **Date:** 2026-11-12
- **Status:** accepted (amends the specification)

## Context

The specification reserved the bottom right of tab 1 for a SPY GEX panel, fed by a new daily `gex_spy_YYYYMMDD.csv` from the capture pipeline: regime, gamma flip and main strikes by absolute GEX. Capturing, parsing and storing that data would add a new input file and a new calculation, for context that external pages already show.

## Decision

- **The dashboard does not capture, parse or store any GEX data.** The panel, the input file and its place in the data contract are dropped.
- **Tab 1 shows a "GEX SPX" button where the panel was.** It opens an external GEX reference page in a new browser tab (`target="_blank"`, `rel="noopener noreferrer"`).
- **The address comes from the `GEX_REFERENCE_URL_SPX` environment variable.** `python -m tape_dashboard` also loads it from a `.env` file at the repository root, with python-dotenv; variables already set in the environment win. The template is `.env.example`, with the variable empty. `.env` stays out of git.
- **Without the variable, or with it empty, there is no button** and everything else works the same.
- **Only `http` and `https` addresses are used.** Any other value hides the button and adds a warning to the banner, so that a typo does not fail silently and a `javascript:` address is never placed in a link.
- The repository names no data provider for this page: anyone can point the button at the GEX page they use.

## Rejected alternatives

- **Capturing the GEX daily and computing regime, flip and walls in the dashboard**: a new input file, a new calculation and its sign convention, for a context that is one click away.
- **A key in `config.toml`**: the user asked for an environment variable with a `.env` template, the usual place for optional settings that are not paths.

## Consequences

- The specification no longer has a third panel in tab 1 nor a GEX file among the changes outside the dashboard.
- Changing the address needs a restart of the dashboard, as with the rest of the configuration.
