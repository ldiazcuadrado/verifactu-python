"""Vectores oficiales del documento de la AEAT sobre la huella (v0.1.2, sección 6)."""

from datetime import datetime, timedelta, timezone

from verifactu_sdk import hashing
from verifactu_sdk.models import (
    Cadena,
    IDFactura,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnulacion,
    SistemaInformatico,
)

CASO1 = "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
CASO2 = "F7B94CFD8924EDFF273501B01EE5153E4CE8F259766F88CF6ACB8935802A2B97"
CASO3 = "177547C0D57AC74748561D054A9CEC14B4C4EA23D1BEFD6F2E69E3A388F90C68"

CET = timezone(timedelta(hours=1))


def test_caso1_primer_registro_alta():
    cadena = hashing.cadena_alta(
        id_emisor="89890001K",
        num_serie="12345678/G33",
        fecha_expedicion="01-01-2024",
        tipo_factura="F1",
        cuota_total="12.35",
        importe_total="123.45",
        huella_anterior=None,
        fecha_hora_huso_gen="2024-01-01T19:20:30+01:00",
    )
    assert cadena == (
        "IDEmisorFactura=89890001K&NumSerieFactura=12345678/G33&FechaExpedicionFactura=01-01-2024"
        "&TipoFactura=F1&CuotaTotal=12.35&ImporteTotal=123.45&Huella="
        "&FechaHoraHusoGenRegistro=2024-01-01T19:20:30+01:00"
    )
    assert hashing.huella(cadena) == CASO1


def test_caso2_alta_encadenada():
    assert (
        hashing.huella_alta(
            id_emisor="89890001K",
            num_serie="12345679/G34",
            fecha_expedicion="01-01-2024",
            tipo_factura="F1",
            cuota_total="12.35",
            importe_total="123.45",
            huella_anterior=CASO1,
            fecha_hora_huso_gen="2024-01-01T19:20:35+01:00",
        )
        == CASO2
    )


def test_caso3_anulacion_encadenada():
    assert (
        hashing.huella_anulacion(
            id_emisor="89890001K",
            num_serie="12345679/G34",
            fecha_expedicion="01-01-2024",
            huella_anterior=CASO2,
            fecha_hora_huso_gen="2024-01-01T19:20:40+01:00",
        )
        == CASO3
    )


def test_espacios_al_inicio_y_final_se_eliminan():
    a = hashing.cadena_alta(
        id_emisor=" 89890001K ",
        num_serie="    12345678 / G33  ",
        fecha_expedicion="01-01-2024",
        tipo_factura="F1",
        cuota_total="1",
        importe_total="2",
        huella_anterior=None,
        fecha_hora_huso_gen="2024-01-01T19:20:30+01:00",
    )
    assert "NumSerieFactura=12345678 / G33&" in a
    assert a.startswith("IDEmisorFactura=89890001K&")


def test_cadena_reproduce_los_tres_casos_con_modelos():
    sistema = SistemaInformatico("ACME SL", "89890001K", "Facturador", "01", "1.0", "1")
    emisor = Persona("Empresa de prueba", nif="89890001K")
    cadena = Cadena()

    def alta(num: str, seg: int) -> RegistroAlta:
        r = RegistroAlta(
            emisor=emisor,
            num_serie=num,
            fecha_expedicion="01-01-2024",
            descripcion="Prueba",
            desglose=[LineaDesglose(base_imponible="111.10", cuota_repercutida="12.35")],
            sistema=sistema,
            cuota_total="12.35",
            importe_total="123.45",
        )
        cadena.encadenar(r, datetime(2024, 1, 1, 19, 20, seg, tzinfo=CET))
        return r

    assert alta("12345678/G33", 30).huella == CASO1
    assert alta("12345679/G34", 35).huella == CASO2
    anul = RegistroAnulacion(IDFactura("89890001K", "12345679/G34", "01-01-2024"), sistema)
    cadena.encadenar(anul, datetime(2024, 1, 1, 19, 20, 40, tzinfo=CET))
    assert anul.huella == CASO3
    assert cadena.ultimo is not None and cadena.ultimo.huella == CASO3
