import asyncio
import json

import pytest

pytest.importorskip("mcp")

from verifactu_sdk.mcp_server import _servidor  # noqa: E402


def _llamar(nombre, args):
    resultado = asyncio.run(_servidor().call_tool(nombre, args))
    estructurado = getattr(resultado, "structured_content", None) or getattr(
        resultado, "structuredContent", None
    )
    if estructurado is not None:  # mcp >= 2
        return estructurado.get("result", estructurado)
    contenido = resultado[0] if isinstance(resultado, tuple) else resultado  # mcp 1.x
    return json.loads(contenido[0].text)


def test_herramientas_registradas():
    nombres = {t.name for t in asyncio.run(_servidor().list_tools())}
    assert {
        "calcular_huella_alta",
        "calcular_huella_anulacion",
        "generar_url_qr",
        "validar_nif",
        "construir_registro_alta",
        "validar_xml_verifactu",
    } <= nombres


def test_huella_por_mcp():
    r = _llamar(
        "calcular_huella_alta",
        {
            "nif_emisor": "89890001K",
            "num_serie": "12345678/G33",
            "fecha_expedicion": "01-01-2024",
            "tipo_factura": "F1",
            "cuota_total": "12.35",
            "importe_total": "123.45",
            "fecha_hora_huso_gen": "2024-01-01T19:20:30+01:00",
        },
    )
    assert r["huella"] == "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"


def test_construir_registro_por_mcp():
    r = _llamar(
        "construir_registro_alta",
        {
            "nif_emisor": "89890001K",
            "nombre_emisor": "Empresa",
            "num_serie": "A-1",
            "fecha_expedicion": "01-10-2026",
            "descripcion": "Servicios",
            "lineas": [{"base_imponible": "100", "tipo_impositivo": "21"}],
            "sistema": {
                "nombre_razon": "ACME SL",
                "nif": "B12345674",
                "nombre_sistema": "Facturador",
                "id_sistema": "01",
                "version": "1.0",
                "numero_instalacion": "1",
            },
            "fecha_hora_huso_gen": "2026-10-01T10:00:00+02:00",
        },
    )
    assert r["valido_xsd"], r["errores_xsd"]
    assert r["siguiente_anterior"]["huella"] == r["huella"]
    assert "<sum1:PrimerRegistro>S</sum1:PrimerRegistro>" in r["xml"]
