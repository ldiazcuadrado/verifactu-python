"""Servidor MCP de VERI*FACTU para Claude, Cursor y otros agentes.

Expone herramientas sin efectos externos: calcular huellas, generar la URL del QR, validar NIF,
construir el XML de un registro de alta y validarlo contra el XSD oficial. No envía nada a la AEAT.

Uso: ``pip install 'verifactu-sdk[mcp]'`` y registra el comando ``verifactu-sdk-mcp``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from lxml import etree

from . import hashing
from .models import (
    Cabecera,
    Cadena,
    Entorno,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnterior,
    SistemaInformatico,
    formatear_fecha,
    formatear_importe,
)
from .nif import tipo_nif
from .qr import url_qr
from .xml import ErrorValidacionXSD, construir_peticion, validar


def _servidor():
    try:  # mcp >= 2
        from mcp.server.mcpserver import MCPServer as Servidor
    except ImportError:
        try:  # mcp 1.x
            from mcp.server.fastmcp import FastMCP as Servidor
        except ImportError as exc:  # pragma: no cover
            raise SystemExit("Instala el extra MCP: pip install 'verifactu-sdk[mcp]'") from exc

    mcp = Servidor("verifactu")

    @mcp.tool()
    def calcular_huella_alta(
        nif_emisor: str,
        num_serie: str,
        fecha_expedicion: str,
        tipo_factura: str,
        cuota_total: str,
        importe_total: str,
        fecha_hora_huso_gen: str,
        huella_anterior: str | None = None,
    ) -> dict[str, str]:
        """Huella SHA-256 de un registro de alta VERI*FACTU (y la cadena usada para calcularla).

        Fechas: fecha_expedicion DD-MM-AAAA; fecha_hora_huso_gen ISO 8601 con huso, p. ej.
        2024-01-01T19:20:30+01:00. Omite huella_anterior en el primer registro.
        """
        cadena = hashing.cadena_alta(
            id_emisor=nif_emisor,
            num_serie=num_serie,
            fecha_expedicion=formatear_fecha(fecha_expedicion),
            tipo_factura=tipo_factura,
            cuota_total=formatear_importe(cuota_total),
            importe_total=formatear_importe(importe_total),
            huella_anterior=huella_anterior,
            fecha_hora_huso_gen=fecha_hora_huso_gen,
        )
        return {"cadena": cadena, "huella": hashing.huella(cadena)}

    @mcp.tool()
    def calcular_huella_anulacion(
        nif_emisor: str,
        num_serie: str,
        fecha_expedicion: str,
        fecha_hora_huso_gen: str,
        huella_anterior: str | None = None,
    ) -> dict[str, str]:
        """Huella SHA-256 de un registro de anulación VERI*FACTU."""
        cadena = hashing.cadena_anulacion(
            id_emisor=nif_emisor,
            num_serie=num_serie,
            fecha_expedicion=formatear_fecha(fecha_expedicion),
            huella_anterior=huella_anterior,
            fecha_hora_huso_gen=fecha_hora_huso_gen,
        )
        return {"cadena": cadena, "huella": hashing.huella(cadena)}

    @mcp.tool()
    def generar_url_qr(
        nif_emisor: str,
        num_serie: str,
        fecha_expedicion: str,
        importe_total: str,
        produccion: bool = False,
        verifactu: bool = True,
    ) -> str:
        """URL de cotejo de la AEAT que debe ir dentro del QR tributario de la factura."""
        return url_qr(
            nif=nif_emisor,
            num_serie=num_serie,
            fecha_expedicion=fecha_expedicion,
            importe_total=importe_total,
            entorno=Entorno.PRODUCCION if produccion else Entorno.PRUEBAS,
            verifactu=verifactu,
        )

    @mcp.tool()
    def validar_nif(nif: str) -> dict[str, Any]:
        """Comprueba el carácter de control de un NIF, NIE o CIF español (no consulta el censo)."""
        t = tipo_nif(nif)
        return {"valido": t is not None, "tipo": t}

    @mcp.tool()
    def construir_registro_alta(
        nif_emisor: str,
        nombre_emisor: str,
        num_serie: str,
        fecha_expedicion: str,
        descripcion: str,
        lineas: list[dict[str, str]],
        sistema: dict[str, str],
        destinatario_nombre: str | None = None,
        destinatario_nif: str | None = None,
        tipo_factura: str = "F1",
        anterior: dict[str, str] | None = None,
        fecha_hora_huso_gen: str | None = None,
    ) -> dict[str, Any]:
        """Construye el XML RegFactuSistemaFacturacion de un registro de alta y lo valida.

        lineas: [{"base_imponible": "100", "tipo_impositivo": "21"}, ...] (también admite
        cuota_repercutida, clave_regimen, calificacion, operacion_exenta, impuesto).
        sistema: {nombre_razon, nif, nombre_sistema, id_sistema, version, numero_instalacion}.
        anterior: {id_emisor, num_serie, fecha_expedicion, huella} del registro previo, o nada
        si es el primero. Devuelve el XML, la huella y el eslabón a guardar para el siguiente.
        """
        reg = RegistroAlta(
            emisor=Persona(nombre_emisor, nif=nif_emisor),
            num_serie=num_serie,
            fecha_expedicion=fecha_expedicion,
            descripcion=descripcion,
            desglose=[LineaDesglose(**ln) for ln in lineas],
            sistema=SistemaInformatico(**sistema),
            tipo_factura=tipo_factura,
            destinatarios=(
                [Persona(destinatario_nombre, nif=destinatario_nif)]
                if destinatario_nombre and destinatario_nif
                else []
            ),
        )
        cadena = Cadena(RegistroAnterior.from_dict(anterior) if anterior else None)
        momento = datetime.fromisoformat(fecha_hora_huso_gen) if fecha_hora_huso_gen else None
        cadena.encadenar(reg, momento)
        peticion = construir_peticion(Cabecera(reg.emisor), [reg])
        errores: list[str] = []
        try:
            validar(peticion)
        except ErrorValidacionXSD as e:
            errores = e.errores
        return {
            "xml": etree.tostring(peticion, pretty_print=True, encoding="unicode"),
            "huella": reg.huella,
            "valido_xsd": not errores,
            "errores_xsd": errores,
            "siguiente_anterior": cadena.ultimo.to_dict() if cadena.ultimo else None,
        }

    @mcp.tool()
    def validar_xml_verifactu(xml: str) -> dict[str, Any]:
        """Valida un XML RegFactuSistemaFacturacion (o el sobre SOAP) contra el XSD de la AEAT."""
        try:
            validar(xml)
            return {"valido": True, "errores": []}
        except ErrorValidacionXSD as e:
            return {"valido": False, "errores": e.errores}

    return mcp


def main() -> None:
    _servidor().run()


if __name__ == "__main__":  # pragma: no cover
    main()
