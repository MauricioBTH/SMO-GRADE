"""Helpers para geracao e verificacao de TOTP e QR code.

Usa pyotp para o algoritmo padrao e `qrcode` para renderizar PNG inline.
"""
from __future__ import annotations

import base64
import io

import pyotp
import qrcode
from qrcode.image.pil import PilImage

_ISSUER: str = "SMO-GRADE"
_TOTP_DIGITS: int = 6
_TOTP_INTERVALO_SEG: int = 30
_TOTP_JANELA_VALIDACAO: int = 1  # aceita codigo do intervalo atual +/- 1


def gerar_secret() -> str:
    return pyotp.random_base32()


def uri_provisionamento(secret: str, email: str) -> str:
    return pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_INTERVALO_SEG).provisioning_uri(
        name=email, issuer_name=_ISSUER
    )


def verificar_codigo(secret: str, codigo: str) -> bool:
    codigo_limpo: str = codigo.strip().replace(" ", "")
    if len(codigo_limpo) != _TOTP_DIGITS or not codigo_limpo.isdigit():
        return False
    totp = pyotp.TOTP(secret, digits=_TOTP_DIGITS, interval=_TOTP_INTERVALO_SEG)
    return bool(totp.verify(codigo_limpo, valid_window=_TOTP_JANELA_VALIDACAO))


def qr_png_base64(uri: str) -> str:
    """Retorna PNG do QR como data URI para uso em <img src>."""
    img: PilImage = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded: str = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
