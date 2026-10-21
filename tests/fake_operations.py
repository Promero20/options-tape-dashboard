"""Operaciones mínimas para probar las reglas de clasificación sin pasar por el script."""

from dataclasses import dataclass, field


def leg(option_type, strike, exp_date, premium, agr, size=1000, price=None):
    """Una pata con las claves de patas_de() del script."""
    letter = "C" if option_type == "call" else "P"
    return {
        "contract_symbol": f"XYZ|{exp_date.replace('-', '')}|{strike:.2f}{letter}",
        "type": option_type, "strike": f"{strike:.2f}", "exp_date": exp_date,
        "n_trades": 1, "size": size, "premium": float(premium), "agr": agr,
        "precio_medio": price if price is not None else premium / size / 100,
    }


@dataclass
class FakeOperation:
    legs: list
    stock_option: bool = False
    incomplete: bool = False
    summary: dict = field(init=False)

    def __post_init__(self):
        self.summary = {
            "premium_total": round(sum(l["premium"] for l in self.legs), 2),
            "stock_option": self.stock_option,
            "patas_incompletas": self.incomplete,
        }


def op(*legs, **flags):
    return FakeOperation(list(legs), **flags)
