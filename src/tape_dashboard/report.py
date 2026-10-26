"""
Command-line report on the data folder.

    python -m tape_dashboard.report [--data-dir PATH] [--info]

Shows which files there are and their schema variant, which days can be
rebuilt, how each reconstruction compares with the stored level 3, the
quality indicators, the breakdown of operations by destination (with manual
edits applied), orphan edits and every warning. It only reads the data
folder and the edits file.
"""

import argparse
import sys
from pathlib import Path

from .config import load_settings
from .data.dataset import load_dataset
from .data.files import declared_hash
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


def render(dataset, edits=None, show_info=False, declared=None):
    edits = edits or Edits.empty()
    out = [f"Data folder: {dataset.data_dir}"]
    s = dataset.script
    if not s.found:
        out.append("Pipeline script: not found in the data folder")
    elif s.matches:
        out.append("Pipeline script: matches pipeline/nivel3_agrupar.py")
    else:
        out.append(f"Pipeline script: DIFFERENT from pipeline/nivel3_agrupar.py "
                   f"(sha256 {s.deployed_sha256[:12]}… versus {s.canonical_sha256[:12]}…); "
                   f"see docs/level3-script.md")
    if declared is not None:
        if not declared.exists:
            out.append(f"Declared script hash: file not found ({declared.path})")
        elif declared.matches:
            out.append(f"Declared script hash: matches ({declared.path.name})")
        else:
            out.append(f"Declared script hash: DOES NOT MATCH the canonical script ({declared.path.name}); "
                       f"update it after deploying, see docs/level3-script.md")

    rows = []
    for day, c in dataset.captures.items():
        v = validate_capture(c)
        rows.append([
            day.isoformat(),
            (c.level1.variant or "new") if c.level1 else ("error" if c.files.level1 else "—"),
            (c.level2.variant or "new") if c.level2 else ("error" if c.files.level2 else "—"),
            (v.variant or "new") if c.files.level3 else "—",
            c.n_trades if c.usable else "—",
            len(c.operations) if c.usable else "—",
            len(c.passing) if c.usable else "—",
            v.status + (f" ({v.detail})" if v.detail else ""),
        ])
    usable = dataset.usable_dates
    out += ["", f"Captures: {len(dataset.captures)}, rebuildable: {len(usable)}",
            _table(["capture", "level1", "level2", "level3", "trades", "groups", "≥ threshold",
                    "stored level 3"], rows)]

    repeated = dataset.repeated_ids()
    out += ["", f"Operations in more than one capture: {len(repeated)}"
                + (" (in a multi-day range the most recent capture counts)" if repeated else "")]
    for op_id, days in list(repeated.items())[:10]:
        out.append(f"  {op_id}: {', '.join(d.isoformat() for d in days)}")

    q_rows = []
    for day in usable:
        q = level2_quality(dataset.captures[day].level2)
        q_rows.append([day.isoformat(), q.trades, q.crossed_quotes, q.cancellations,
                       q.identical_rows, q.size_ten, q.without_aggressiveness])
    out += ["", "Level-2 quality (informational, does not change the grouping)",
            _table(["capture", "trades", "bid>ask", "cancellations", "identical rows",
                    "size 10", "no aggressiveness"], q_rows)]

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
    out += ["", "Operations above the threshold, by destination (with manual edits)",
            _table(["capture", *DESTINATIONS, "anomalous ratio"], d_rows)]

    lost = orphans(dataset, edits)
    out += ["", f"Orphan edits (their operation no longer exists; never deleted): {len(lost)}"]
    out += [f"  {o.kind} {o.operation_id}: {o.detail}" for o in lost]

    issues = [i for i in dataset.issues if show_info or i.severity != INFO]
    out += ["", f"Warnings ({len(issues)}{'' if show_info else ', informational ones hidden; use --info'}):"]
    out += [f"  {i}" for i in issues] or ["  none"]
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Report on the data folder")
    parser.add_argument("--data-dir", type=Path, help="data folder (default: the configured one)")
    parser.add_argument("--info", action="store_true", help="also show informational warnings")
    args = parser.parse_args(argv)

    settings = load_settings()
    data_dir = args.data_dir or settings.data_dir
    if not data_dir.is_dir():
        print(f"The data folder does not exist: {data_dir}", file=sys.stderr)
        return 1
    edits = read_edits(settings.user_data_dir / FILE_NAME)
    declared = declared_hash(settings.expected_hash_file) if settings.expected_hash_file else None
    print(render(load_dataset(data_dir), edits, show_info=args.info, declared=declared))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
