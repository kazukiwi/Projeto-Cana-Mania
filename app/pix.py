"""Geração local de BR Code Pix estático, sem confirmação bancária."""
import base64
from binascii import crc_hqx
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import os
import re
import unicodedata


def campo(identificador: str, valor: str) -> str:
    if not valor.isascii() or not 1 <= len(valor) <= 99:
        raise ValueError("Campo Pix inválido.")
    return f"{identificador}{len(valor):02d}{valor}"


def texto_recebedor(valor: str, limite: int) -> str:
    texto = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode().upper()
    texto = " ".join(re.sub(r"[^A-Z0-9 ]", " ", texto).split())[:limite]
    if not texto:
        raise ValueError("Configure o nome e a cidade do recebedor Pix.")
    return texto


def gerar_payload(chave: str, nome: str, cidade: str, valor) -> str:
    chave = chave.strip()
    formatos = (
        r"[0-9]{11}", r"[A-Z0-9]{12}[0-9]{2}", r"\+[1-9][0-9]{7,14}",
        r"[^\s@]+@[^\s@]+\.[^\s@]+",
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
    )
    if not chave.isascii() or len(chave) > 77 or not any(re.fullmatch(p, chave) for p in formatos):
        raise ValueError("Configure PIX_CHAVE com uma chave válida, sem espaços ou máscara.")
    try:
        total = Decimal(str(valor))
        if not total.is_finite() or not Decimal("0.01") <= total <= Decimal("9999999999.99"):
            raise ValueError("O valor Pix deve estar entre R$ 0,01 e R$ 9.999.999.999,99.")
        total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError):
        raise ValueError("Valor Pix inválido.") from None
    conta = campo("00", "br.gov.bcb.pix") + campo("01", chave)
    payload = (
        campo("00", "01") + campo("26", conta) + campo("52", "0000")
        + campo("53", "986") + campo("54", f"{total:.2f}") + campo("58", "BR")
        + campo("59", texto_recebedor(nome, 25)) + campo("60", texto_recebedor(cidade, 15))
        + campo("62", campo("05", "***")) + "6304"
    )
    return payload + f"{crc_hqx(payload.encode('ascii'), 0xFFFF):04X}"


def gerar_pix(valor) -> dict:
    import qrcode
    from qrcode.image.svg import SvgPathImage

    payload = gerar_payload(
        os.getenv("PIX_CHAVE", ""), os.getenv("PIX_NOME_RECEBEDOR", ""),
        os.getenv("PIX_CIDADE", ""), valor,
    )
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=4, box_size=8)
    qr.add_data(payload)
    qr.make(fit=True)
    arquivo = BytesIO()
    qr.make_image(image_factory=SvgPathImage).save(arquivo)
    return {
        "copia_cola": payload,
        "qr_code": "data:image/svg+xml;base64," + base64.b64encode(arquivo.getvalue()).decode("ascii"),
        "valor": f"{Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):.2f}",
    }
