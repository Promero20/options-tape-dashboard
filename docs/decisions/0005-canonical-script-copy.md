# 0005. The canonical copy of the script lives in this repository

- **Date:** 2026-10-16
- **Status:** accepted

## Context

The capture pipeline runs `nivel3_agrupar.py` from the data folder, and the dashboard needs to import it (see [0002](0002-single-grouping-logic.md)). Two copies evolving separately would end up diverging. At the same time, the dashboard never writes to the data folder.

## Decision

The canonical version is `pipeline/nivel3_agrupar.py`, with its history and its tests. When it changes, the user copies it to the data folder (procedure in [level3-script.md](../level3-script.md)). The report compares the hashes of both copies and warns if they differ; from phase 3, the interface will too.

## Rejected alternatives

- **Keeping the original in the data folder and importing it from there**: no history or tests, and the dashboard would depend on code it does not control.
- **A symbolic link from the data folder to the repository**: it has to be created inside that folder, and it is not clear the pipeline's environment would resolve it.

## Consequences

- Deploying to the pipeline is a manual step, but a rare and verifiable one.
- The script has to remain a standalone file, standard library only.
- It is the only exception to the English-identifiers convention: the script already had its API in Spanish (`cargar`, `agrupar`, `resumen`…), and the new functions (`patas_de`, `id_operacion`, `filtrar_por_umbral`…) follow that naming so the module stays consistent. The dashboard code and the tests use English identifiers.
