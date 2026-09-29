"""Valores em reais no Python e centavos inteiros no SQLite."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy import BigInteger, Numeric
from sqlalchemy.types import TypeDecorator

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")

def dinheiro(valor):
    try:
        numero = Decimal(str(valor))
        if not numero.is_finite() or abs(numero) > Decimal("999999999999.99"):
            raise ValueError("Valor monetário inválido.")
        return numero.quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError("Valor monetário inválido.") from None

class Dinheiro(TypeDecorator):
    impl = Numeric(14, 2)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(BigInteger() if dialect.name == "sqlite" else Numeric(14, 2))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        value = dinheiro(value)
        return int(value * 100) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return dinheiro(Decimal(str(value)) / 100 if dialect.name == "sqlite" else value)
