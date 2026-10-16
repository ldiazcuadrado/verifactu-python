"""Línea de comandos: ``verifactu huella | qr | validar | nif``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import hashing
from .models import Entorno, formatear_fecha, formatear_importe
from .nif import tipo_nif
from .qr import qr_png, qr_svg, url_qr
from .xml import ErrorValidacionXSD, validar


def _huella(a: argparse.Namespace) -> int:
    if a.tipo_registro == "alta":
        cadena = hashing.cadena_alta(
            id_emisor=a.nif,
            num_serie=a.numserie,
            fecha_expedicion=formatear_fecha(a.fecha),
            tipo_factura=a.tipo,
            cuota_total=formatear_importe(a.cuota),
            importe_total=formatear_importe(a.importe),
            huella_anterior=a.anterior,
            fecha_hora_huso_gen=a.fechahora,
        )
    else:
        cadena = hashing.cadena_anulacion(
            id_emisor=a.nif,
            num_serie=a.numserie,
            fecha_expedicion=formatear_fecha(a.fecha),
            huella_anterior=a.anterior,
            fecha_hora_huso_gen=a.fechahora,
        )
    if a.verbose:
        print(cadena, file=sys.stderr)
    print(hashing.huella(cadena))
    return 0


def _qr(a: argparse.Namespace) -> int:
    url = url_qr(
        nif=a.nif,
        num_serie=a.numserie,
        fecha_expedicion=a.fecha,
        importe_total=a.importe,
        entorno=Entorno.PRODUCCION if a.produccion else Entorno.PRUEBAS,
        verifactu=not a.no_verifactu,
    )
    print(url)
    if a.png:
        Path(a.png).write_bytes(qr_png(url))
    if a.svg:
        Path(a.svg).write_text(qr_svg(url), encoding="utf-8")
    return 0


def _validar(a: argparse.Namespace) -> int:
    codigo = 0
    for fichero in a.ficheros:
        try:
            validar(Path(fichero).read_bytes())
            print(f"OK  {fichero}")
        except ErrorValidacionXSD as e:
            codigo = 1
            print(f"KO  {fichero}")
            for err in e.errores:
                print(f"    {err}")
    return codigo


def _nif(a: argparse.Namespace) -> int:
    codigo = 0
    for n in a.nifs:
        t = tipo_nif(n)
        print(f"{'OK' if t else 'KO'}  {n}" + (f"  ({t})" if t else ""))
        codigo |= t is None
    return codigo


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="verifactu", description="Utilidades VERI*FACTU (AEAT).")
    sub = p.add_subparsers(dest="comando", required=True)

    h = sub.add_parser("huella", help="Calcula la huella SHA-256 de un registro")
    h.add_argument("tipo_registro", choices=["alta", "anulacion"])
    h.add_argument("--nif", required=True, help="NIF del emisor")
    h.add_argument("--numserie", required=True, help="Serie y número de la factura")
    h.add_argument("--fecha", required=True, help="Fecha de expedición (DD-MM-AAAA o AAAA-MM-DD)")
    h.add_argument("--tipo", default="F1", help="TipoFactura (solo alta)")
    h.add_argument("--cuota", default="0", help="CuotaTotal (solo alta)")
    h.add_argument("--importe", default="0", help="ImporteTotal (solo alta)")
    h.add_argument("--anterior", default=None, help="Huella del registro anterior")
    h.add_argument("--fechahora", required=True, help="FechaHoraHusoGenRegistro, ISO 8601")
    h.add_argument("-v", "--verbose", action="store_true", help="Muestra la cadena en stderr")
    h.set_defaults(func=_huella)

    q = sub.add_parser("qr", help="Genera la URL (y la imagen) del QR tributario")
    q.add_argument("--nif", required=True)
    q.add_argument("--numserie", required=True)
    q.add_argument("--fecha", required=True)
    q.add_argument("--importe", required=True)
    q.add_argument("--produccion", action="store_true", help="URL de producción")
    q.add_argument("--no-verifactu", action="store_true", help="Sistema no VERI*FACTU")
    q.add_argument("--png", help="Guarda el QR en PNG (requiere extra qr)")
    q.add_argument("--svg", help="Guarda el QR en SVG (requiere extra qr)")
    q.set_defaults(func=_qr)

    v = sub.add_parser("validar", help="Valida XML contra el XSD oficial de la AEAT")
    v.add_argument("ficheros", nargs="+")
    v.set_defaults(func=_validar)

    n = sub.add_parser("nif", help="Comprueba el dígito de control de NIF/NIE/CIF")
    n.add_argument("nifs", nargs="+")
    n.set_defaults(func=_nif)
    return p


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
