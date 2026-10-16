from datetime import date, datetime, timedelta, timezone

import pytest

from verifactu_sdk.models import (
    Cabecera,
    Cadena,
    IDFactura,
    IDOtro,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnulacion,
    SistemaInformatico,
)
from verifactu_sdk.xml import (
    NS_SF,
    ErrorValidacionXSD,
    construir_peticion,
    sobre_soap,
    validar,
)

CET = timezone(timedelta(hours=1))
SISTEMA = SistemaInformatico("ACME SL", "B12345674", "Facturador", "01", "1.0.0", "1")
EMISOR = Persona("Empresa de prueba SL", nif="89890001K")


def _alta(num: str = "A-1", **kw) -> RegistroAlta:
    datos = dict(
        emisor=EMISOR,
        num_serie=num,
        fecha_expedicion=date(2026, 10, 1),
        descripcion="Servicios de consultoría",
        desglose=[
            LineaDesglose(base_imponible="100", tipo_impositivo="21"),
            LineaDesglose(base_imponible="10", tipo_impositivo="4"),
        ],
        sistema=SISTEMA,
        destinatarios=[Persona("Cliente SA", nif="A84532509")],
    )
    datos.update(kw)
    return RegistroAlta(**datos)


def _texto(el, nombre):
    return el.find(f".//{{{NS_SF}}}{nombre}").text


def test_totales_calculados():
    r = _alta()
    assert r.cuota_total_str() == "21.40"
    assert r.importe_total_str() == "131.40"


def test_alta_valida_contra_xsd_oficial():
    cadena = Cadena()
    r1 = cadena.encadenar(_alta("A-1"), datetime(2026, 10, 1, 10, 0, 0, tzinfo=CET))
    r2 = cadena.encadenar(_alta("A-2"), datetime(2026, 10, 1, 10, 0, 5, tzinfo=CET))
    peticion = construir_peticion(Cabecera(EMISOR), [r1, r2])
    validar(peticion)
    validar(sobre_soap(peticion))
    assert _texto(peticion, "PrimerRegistro") == "S"
    assert _texto(peticion, "Huella") == r1.huella
    assert r2.anterior is not None and r2.anterior.huella == r1.huella


def test_anulacion_y_extranjero_validan():
    cadena = Cadena()
    extranjero = Persona("Foreign Ltd", id_otro=IDOtro("GB123456789", "02", "GB"))
    r1 = cadena.encadenar(_alta(destinatarios=[extranjero]))
    anul = cadena.encadenar(RegistroAnulacion(IDFactura("89890001K", "A-1", "2026-10-01"), SISTEMA))
    validar(construir_peticion(Cabecera(EMISOR), [r1, anul]))


def test_rectificativa_valida():
    r = Cadena().encadenar(
        _alta(
            "R-1",
            tipo_factura="R1",
            tipo_rectificativa="I",
            facturas_rectificadas=[IDFactura("89890001K", "A-1", "01-10-2026")],
            desglose=[LineaDesglose(base_imponible="-10", tipo_impositivo="21")],
        )
    )
    assert r.importe_total_str() == "-12.10"
    validar(construir_peticion(Cabecera(EMISOR), [r]))


def test_exenta_sin_cuota_valida():
    r = Cadena().encadenar(
        _alta(
            desglose=[LineaDesglose(base_imponible="50", operacion_exenta="E1", calificacion=None)]
        )
    )
    assert r.cuota_total_str() == "0.00"
    validar(construir_peticion(Cabecera(EMISOR), [r]))


def test_xml_invalido_lanza_error():
    r = Cadena().encadenar(_alta(descripcion="x" * 501))
    with pytest.raises(ErrorValidacionXSD):
        validar(construir_peticion(Cabecera(EMISOR), [r]))


def test_sin_encadenar_falla():
    with pytest.raises(ValueError):
        construir_peticion(Cabecera(EMISOR), [_alta()])
