"""Avisos de la capa de datos: nada se ignora en silencio, todo se reporta."""

from dataclasses import dataclass

ERROR = "error"      # el fichero (o el día) no se puede usar
WARNING = "aviso"    # se usa, pero hay algo que revisar
INFO = "info"        # dato informativo


@dataclass(frozen=True)
class Issue:
    severity: str
    file: str | None
    message: str

    def __str__(self):
        where = f"{self.file}: " if self.file else ""
        return f"[{self.severity}] {where}{self.message}"
