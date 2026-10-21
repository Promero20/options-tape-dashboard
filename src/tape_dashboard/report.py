"""
Informe de la carpeta de datos por consola.

    python -m tape_dashboard.report [--data-dir RUTA] [--info]

Muestra qué ficheros hay, con qué variante de esquema, qué días se pueden
reconstruir, cómo se compara la reconstrucción con el nivel 3 guardado, los
indicadores de calidad, el reparto de operaciones por destino (con las
ediciones manuales), las ediciones huérfanas y todos los avisos. Solo lee la
carpeta de datos y el fichero de ediciones.
"""

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .data.dataset import load_dataset
from .data.issues import INFO
from .data.quality import level2_quality
from .data.validation import validate_capture
from .edits.apply import apply_edits, orphans
from .edits.store import FILE_NAME, Edits, read_edits
from .rules.classification import DESTINATIONS


def _table(headers, rows):
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]
    line = lambda values: "  ".join(str(v).ljust(w) for v, w in zip(values, widths)).rstrip()
    return "\n".join([line(headers), line("-" * w for w in widths)] + [line(r) for r in rows])


def render(dataset, edits=None, show_info=False):
    edits = edits or Edits.empty()
    out = [f"Carpeta de datos: {dataset.data_dir}"]
    s = dataset.script
    if not s.found:
        out.append("Script del pipeline: no está en la carpeta de datos")
    elif s.matches:
        out.append("Script del pipeline: coincide con pipeline/nivel3_agrupar.py")
    else:
        out.append(f"Script del pipeline: DISTINTO de pipeline/nivel3_agrupar.py "
                   f"(sha256 {s.deployed_sha256[:12]}… frente a {s.canonical_sha256[:12]}…); "
                   f"ver docs/level3-script.md")

    rows = []
    for day, c in dataset.captures.items():
        v = validate_capture(c)
        rows.append([
            day.isoformat(),
            (c.level1.variant or "nueva") if c.level1 else ("error" if c.files.level1 else "—"),
            (c.level2.variant or "nueva") if c.level2 else ("error" if c.files.level2 else "—"),
            (v.variant or "nueva") if c.files.level3 else "—",
            c.n_trades if c.usable else "—",
            len(c.operations) if c.usable else "—",
            len(c.passing) if c.usable else "—",
            v.status + (f" ({v.detail})" if v.detail else ""),
        ])
    usable = dataset.usable_dates
    out += ["", f"Capturas: {len(dataset.captures)}, reconstruibles: {len(usable)}",
            _table(["captura", "nivel1", "nivel2", "nivel3", "trades", "grupos", "≥ umbral",
                    "nivel 3 guardado"], rows)]

    repeated = dataset.repeated_ids()
    out += ["", f"Operaciones en más de una captura: {len(repeated)}"
                + (" (en un rango de varios días cuenta la captura más reciente)" if repeated else "")]
    for op_id, days in list(repeated.items())[:10]:
        out.append(f"  {op_id}: {', '.join(d.isoformat() for d in days)}")

    q_rows = []
    for day in usable:
        q = level2_quality(dataset.captures[day].level2)
        q_rows.append([day.isoformat(), q.trades, q.crossed_quotes, q.cancellations,
                       q.identical_rows, q.size_ten, q.without_aggressiveness])
    out += ["", "Calidad del nivel 2 (informativo, no altera la agrupación)",
            _table(["captura", "trades", "bid>ask", "cancelaciones", "filas idénticas",
                    "tamaño 10", "sin agresividad"], q_rows)]

    d_rows, totals = [], dict.fromkeys(DESTINATIONS, 0)
    flagged_total = 0
    for day in usable:
        classified = [c for c in apply_edits(dataset.captures[day].operations, edits)
                      if c.operation.passes_threshold]
        counts = dict.fromkeys(DESTINATIONS, 0)
        for c in classified:
            counts[c.classification.destination] += 1
        flagged = sum(1 for c in classified if c.classification.anomalous_size_ratio)
        for k in DESTINATIONS:
            totals[k] += counts[k]
        flagged_total += flagged
        d_rows.append([day.isoformat(), *counts.values(), flagged])
    d_rows.append(["total", *totals.values(), flagged_total])
    out += ["", "Operaciones por encima del umbral, por destino (con las ediciones manuales)",
            _table(["captura", *DESTINATIONS, "ratio anómalo"], d_rows)]

    lost = orphans(dataset, edits)
    out += ["", f"Ediciones huérfanas (su operación ya no existe; no se borran): {len(lost)}"]
    out += [f"  {o.kind} {o.operation_id}: {o.detail}" for o in lost]

    issues = [i for i in dataset.issues if show_info or i.severity != INFO]
    out += ["", f"Avisos ({len(issues)}{'' if show_info else ', sin los informativos; --info para verlos'}):"]
    out += [f"  {i}" for i in issues] or ["  ninguno"]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Informe de la carpeta de datos")
    parser.add_argument("--data-dir", type=Path, help="carpeta de datos (por defecto, la configurada)")
    parser.add_argument("--info", action="store_true", help="mostrar también los avisos informativos")
    args = parser.parse_args(argv)

    settings = load_settings()
    data_dir = args.data_dir or settings.data_dir
    if not data_dir.is_dir():
        print(f"No existe la carpeta de datos: {data_dir}", file=sys.stderr)
        return 1
    edits = read_edits(settings.user_data_dir / FILE_NAME)
    print(render(load_dataset(data_dir), edits, show_info=args.info))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
