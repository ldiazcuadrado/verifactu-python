"""URL y código QR tributario de la factura.

Implementa «Detalle de las especificaciones técnicas del código QR de la factura» (AEAT v0.5.0):
cuatro parámetros (``nif``, ``numserie``, ``fecha``, ``importe``) codificados como URL en UTF-8,
QR ISO/IEC 18004 con nivel de corrección M.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from .models import Entorno, formatear_fecha, formatear_importe

__all__ = ["TEXTO_QR", "LEYENDA_VERIFACTU", "url_qr", "qr_png", "qr_svg"]

TEXTO_QR = "QR tributario:"
"""Texto que debe ir encima del código QR."""

LEYENDA_VERIFACTU = "Factura verificable en la sede electrónica de la AEAT"
"""Frase obligatoria bajo el QR en sistemas VERI*FACTU (también vale «VERI*FACTU»)."""

_BASES = {
    Entorno.PRUEBAS: "https://prewww2.aeat.es/wlpl/TIKE-CONT/",
    Entorno.PRODUCCION: "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/",
}


def url_qr(
    *,
    nif: str,
    num_serie: str,
    fecha_expedicion: date | str,
    importe_total: Decimal | int | float | str,
    entorno: Entorno = Entorno.PRUEBAS,
    verifactu: bool = True,
) -> str:
    """URL de cotejo que va dentro del QR.

    ``verifactu=False`` genera la URL de los sistemas que emiten facturas no verificables
    (``ValidarQRNoVerifactu``).
    """
    if len(num_serie) > 60:
        raise ValueError("numserie admite como máximo 60 caracteres")
    if any(not 32 <= ord(c) <= 126 for c in num_serie):
        raise ValueError("numserie solo admite caracteres ASCII imprimibles (32-126)")
    servicio = "ValidarQR" if verifactu else "ValidarQRNoVerifactu"
    params = {
        "nif": nif.strip().upper(),
        "numserie": num_serie,
        "fecha": formatear_fecha(fecha_expedicion),
        "importe": formatear_importe(importe_total),
    }
    return f"{_BASES[Entorno(entorno)]}{servicio}?{urlencode(params)}"


def _qr(url: str):
    try:
        import segno
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise ImportError(
            "Para generar la imagen del QR instala el extra: pip install 'verifactu-sdk[qr]'"
        ) from exc
    return segno.make(url, error="m", micro=False)


def qr_png(url: str, *, scale: int = 8, border: int = 4) -> bytes:
    """Imagen PNG del QR (requiere el extra ``qr``)."""
    import io

    buf = io.BytesIO()
    _qr(url).save(buf, kind="png", scale=scale, border=border)
    return buf.getvalue()


def qr_svg(url: str, *, scale: int = 8, border: int = 4) -> str:
    """Imagen SVG del QR (requiere el extra ``qr``)."""
    import io

    buf = io.BytesIO()
    _qr(url).save(buf, kind="svg", scale=scale, border=border, xmldecl=False)
    return buf.getvalue().decode("utf-8")
