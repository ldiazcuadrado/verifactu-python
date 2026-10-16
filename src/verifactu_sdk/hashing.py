"""Huella (hash) de los registros VERI*FACTU.

Implementa el documento de la AEAT «Detalle de las especificaciones técnicas para
generación de la huella o hash de los registros de facturación» (v0.1.2):

* Campos concatenados como ``nombre=valor`` separados por ``&``, en orden fijo.
* Valores sin espacios al inicio ni al final; un campo ausente se escribe ``nombre=``.
* SHA-256 sobre la cadena en UTF-8, en hexadecimal y mayúsculas (64 caracteres).
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from decimal import Decimal

__all__ = [
    "cadena_alta",
    "cadena_anulacion",
    "cadena_evento",
    "huella",
    "huella_alta",
    "huella_anulacion",
    "huella_evento",
]

Valor = str | Decimal | int | float | None


def _valor(v: Valor) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return format(v, "f")
    return str(v).strip()


def _cadena(pares: Iterable[tuple[str, Valor]]) -> str:
    return "&".join(f"{nombre}={_valor(valor)}" for nombre, valor in pares)


def huella(cadena: str) -> str:
    """SHA-256 de ``cadena`` en UTF-8, en hexadecimal mayúsculas."""
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper()


def cadena_alta(
    *,
    id_emisor: str,
    num_serie: str,
    fecha_expedicion: str,
    tipo_factura: str,
    cuota_total: Valor,
    importe_total: Valor,
    huella_anterior: str | None,
    fecha_hora_huso_gen: str,
) -> str:
    """Cadena de entrada para un registro de alta (sección 3.a de la especificación)."""
    return _cadena(
        [
            ("IDEmisorFactura", id_emisor),
            ("NumSerieFactura", num_serie),
            ("FechaExpedicionFactura", fecha_expedicion),
            ("TipoFactura", tipo_factura),
            ("CuotaTotal", cuota_total),
            ("ImporteTotal", importe_total),
            ("Huella", huella_anterior),
            ("FechaHoraHusoGenRegistro", fecha_hora_huso_gen),
        ]
    )


def cadena_anulacion(
    *,
    id_emisor: str,
    num_serie: str,
    fecha_expedicion: str,
    huella_anterior: str | None,
    fecha_hora_huso_gen: str,
) -> str:
    """Cadena de entrada para un registro de anulación (sección 3.b)."""
    return _cadena(
        [
            ("IDEmisorFacturaAnulada", id_emisor),
            ("NumSerieFacturaAnulada", num_serie),
            ("FechaExpedicionFacturaAnulada", fecha_expedicion),
            ("Huella", huella_anterior),
            ("FechaHoraHusoGenRegistro", fecha_hora_huso_gen),
        ]
    )


def cadena_evento(
    *,
    nif_sistema: str | None,
    id_otro_sistema: str | None,
    id_sistema_informatico: str,
    version: str,
    numero_instalacion: str,
    nif_obligado: str,
    tipo_evento: str,
    huella_evento_anterior: str | None,
    fecha_hora_huso_gen_evento: str,
) -> str:
    """Cadena de entrada para un registro de evento (sección 3.c)."""
    return _cadena(
        [
            ("NIF", nif_sistema),
            ("ID", id_otro_sistema),
            ("IdSistemaInformatico", id_sistema_informatico),
            ("Version", version),
            ("NumeroInstalacion", numero_instalacion),
            ("NIF", nif_obligado),
            ("TipoEvento", tipo_evento),
            ("HuellaEvento", huella_evento_anterior),
            ("FechaHoraHusoGenEvento", fecha_hora_huso_gen_evento),
        ]
    )


def huella_alta(**campos: Valor) -> str:
    """Huella de un registro de alta. Acepta los mismos argumentos que :func:`cadena_alta`."""
    return huella(cadena_alta(**campos))  # type: ignore[arg-type]


def huella_anulacion(**campos: Valor) -> str:
    """Huella de un registro de anulación. Mismos argumentos que :func:`cadena_anulacion`."""
    return huella(cadena_anulacion(**campos))  # type: ignore[arg-type]


def huella_evento(**campos: Valor) -> str:
    """Huella de un registro de evento. Mismos argumentos que :func:`cadena_evento`."""
    return huella(cadena_evento(**campos))  # type: ignore[arg-type]
