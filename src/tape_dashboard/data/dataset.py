"""
Conjunto de capturas cargadas y consultas por rango de fechas de captura.

Los rangos se filtran por fecha de captura (decisión 0008). Una operación que
aparece en varias capturas del rango se cuenta una vez, la de la captura más
reciente (decisión 0010).
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .files import ScriptStatus, discover, script_status
from .issues import Issue
from .reconstruction import Capture, reconstruct_capture


@dataclass
class Dataset:
    data_dir: Path
    captures: dict[date, Capture]
    script: ScriptStatus
    discovery_issues: list[Issue] = field(default_factory=list)

    @property
    def issues(self):
        return self.discovery_issues + [i for c in self.captures.values() for i in c.issues]

    @property
    def usable_dates(self):
        return [d for d, c in self.captures.items() if c.usable]

    def resolve_today(self, today):
        """
        Captura que corresponde a «hoy»: la de hoy si existe y es utilizable; si
        no, la última disponible. Devuelve (fecha o None, True si es la de hoy).
        """
        dates = [d for d in self.usable_dates if d <= today]
        if not dates:
            return None, False
        return dates[-1], dates[-1] == today

    def operations(self, start, end, passing_only=True):
        """
        Operaciones de las capturas con fecha en [start, end], sin repetir IDs
        (gana la captura más reciente), ordenadas por premium descendente.
        """
        chosen = {}
        for day in sorted(self.usable_dates):
            if start <= day <= end:
                for op in self.captures[day].operations:
                    if op.passes_threshold or not passing_only:
                        chosen[op.id] = op
        return sorted(chosen.values(), key=lambda op: -op.premium)

    def price_on_or_before(self, symbol, day):
        """
        Underlying price in the latest usable capture up to `day` whose level 1
        has the symbol: (capture date, price), or None.
        """
        for d in sorted(self.usable_dates, reverse=True):
            level1 = self.captures[d].level1
            if d <= day and level1 is not None and symbol in level1.prices:
                return d, level1.prices[symbol]
        return None

    def repeated_ids(self):
        """IDs de operación que aparecen en más de una captura: {id: [fechas]}."""
        seen = {}
        for day in self.usable_dates:
            for op in self.captures[day].operations:
                seen.setdefault(op.id, []).append(day)
        return {op_id: days for op_id, days in seen.items() if len(days) > 1}


def load_dataset(data_dir):
    data_dir = Path(data_dir)
    files_by_date, issues = discover(data_dir)
    captures = {day: reconstruct_capture(files) for day, files in files_by_date.items()}
    return Dataset(data_dir, captures, script_status(data_dir), issues)
