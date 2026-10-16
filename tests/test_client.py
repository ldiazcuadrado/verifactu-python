from datetime import date

import httpx
import pytest
from lxml import etree

from verifactu_sdk import (
    Cabecera,
    Cadena,
    ClienteVerifactu,
    ErrorAEAT,
    LineaDesglose,
    Persona,
    RegistroAlta,
    SistemaInformatico,
    parsear_respuesta,
)
from verifactu_sdk.client import ENDPOINTS
from verifactu_sdk.models import Entorno

_WS = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/"

RESPUESTA = f"""<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/">
 <env:Header/>
 <env:Body Id="Body">
  <tikR:RespuestaRegFactuSistemaFacturacion
      xmlns:tikR="{_WS}RespuestaSuministro.xsd" xmlns:tik="{_WS}SuministroInformacion.xsd">
   <tikR:CSV>A-YDSW8NLFLANWPM</tikR:CSV>
   <tikR:DatosPresentacion>
    <tik:NIFPresentador>89890001K</tik:NIFPresentador>
    <tik:TimestampPresentacion>2026-10-01T10:00:05+02:00</tik:TimestampPresentacion>
   </tikR:DatosPresentacion>
   <tikR:Cabecera>
    <tik:ObligadoEmision><tik:NombreRazon>Empresa</tik:NombreRazon><tik:NIF>89890001K</tik:NIF></tik:ObligadoEmision>
   </tikR:Cabecera>
   <tikR:TiempoEsperaEnvio>60</tikR:TiempoEsperaEnvio>
   <tikR:EstadoEnvio>ParcialmenteCorrecto</tikR:EstadoEnvio>
   <tikR:RespuestaLinea>
    <tikR:IDFactura>
     <tik:IDEmisorFactura>89890001K</tik:IDEmisorFactura>
     <tik:NumSerieFactura>A-1</tik:NumSerieFactura>
     <tik:FechaExpedicionFactura>01-10-2026</tik:FechaExpedicionFactura>
    </tikR:IDFactura>
    <tikR:Operacion><tik:TipoOperacion>Alta</tik:TipoOperacion></tikR:Operacion>
    <tikR:EstadoRegistro>Correcto</tikR:EstadoRegistro>
   </tikR:RespuestaLinea>
   <tikR:RespuestaLinea>
    <tikR:IDFactura>
     <tik:IDEmisorFactura>89890001K</tik:IDEmisorFactura>
     <tik:NumSerieFactura>A-2</tik:NumSerieFactura>
     <tik:FechaExpedicionFactura>01-10-2026</tik:FechaExpedicionFactura>
    </tikR:IDFactura>
    <tikR:Operacion><tik:TipoOperacion>Alta</tik:TipoOperacion></tikR:Operacion>
    <tikR:EstadoRegistro>Incorrecto</tikR:EstadoRegistro>
    <tikR:CodigoErrorRegistro>1100</tikR:CodigoErrorRegistro>
    <tikR:DescripcionErrorRegistro>Valor o tipo incorrecto del campo</tikR:DescripcionErrorRegistro>
   </tikR:RespuestaLinea>
  </tikR:RespuestaRegFactuSistemaFacturacion>
 </env:Body>
</env:Envelope>""".encode()

FAULT = b"""<?xml version="1.0" encoding="UTF-8"?>
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"><env:Body><env:Fault>
<faultcode>env:Client</faultcode>
<faultstring>Codigo[4104].El NIF del titular en la cabecera no esta identificado.</faultstring>
</env:Fault></env:Body></env:Envelope>"""


def test_respuesta_de_ejemplo_cumple_xsd_oficial():
    """La respuesta usada en los tests valida contra RespuestaSuministro.xsd."""
    from importlib import resources

    ruta = resources.files("verifactu_sdk") / "schemas" / "RespuestaSuministro.xsd"
    with resources.as_file(ruta) as f:
        esquema = etree.XMLSchema(etree.parse(str(f)))
    cuerpo = etree.fromstring(RESPUESTA).find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
    esquema.assertValid(cuerpo[0])


def test_parsear_respuesta():
    r = parsear_respuesta(RESPUESTA)
    assert r.estado == "ParcialmenteCorrecto"
    assert r.csv == "A-YDSW8NLFLANWPM"
    assert r.tiempo_espera == 60
    assert [ln.num_serie for ln in r.lineas] == ["A-1", "A-2"]
    assert r.lineas[0].aceptado and not r.lineas[1].aceptado
    assert r.errores[0].codigo_error == 1100


def test_fault():
    with pytest.raises(ErrorAEAT) as exc:
        parsear_respuesta(FAULT)
    assert "4104" in exc.value.faultstring
    assert not exc.value.reintentable


def _registro():
    return RegistroAlta(
        emisor=Persona("Empresa", nif="89890001K"),
        num_serie="A-1",
        fecha_expedicion=date(2026, 10, 1),
        descripcion="Servicios",
        desglose=[LineaDesglose(base_imponible="100", tipo_impositivo="21")],
        sistema=SistemaInformatico("ACME SL", "B12345674", "Facturador", "01", "1.0", "1"),
    )


def test_enviar_y_control_de_flujo():
    recibido: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recibido.append(request)
        return httpx.Response(200, content=RESPUESTA)

    with ClienteVerifactu(
        "no-usado.pem", transport=httpx.MockTransport(handler), entorno=Entorno.PRUEBAS
    ) as cliente:
        assert cliente.url == ENDPOINTS[(Entorno.PRUEBAS, False)]
        reg = Cadena().encadenar(_registro())
        r = cliente.enviar(Cabecera(reg.emisor), [reg])
        assert r.csv == "A-YDSW8NLFLANWPM"
        assert cliente.tiempo_espera == 60
        assert cliente.segundos_hasta_siguiente_envio() > 59
        with pytest.raises(RuntimeError):
            cliente.enviar(Cabecera(reg.emisor), [reg], esperar=False)

    cuerpo = recibido[0].content
    assert b"RegFactuSistemaFacturacion" in cuerpo
    assert recibido[0].headers["content-type"].startswith("text/xml")


def test_enviar_fault_lanza_error():
    transport = httpx.MockTransport(lambda req: httpx.Response(500, content=FAULT))
    with ClienteVerifactu("x.pem", transport=transport) as cliente:
        reg = Cadena().encadenar(_registro())
        with pytest.raises(ErrorAEAT):
            cliente.enviar(Cabecera(reg.emisor), [reg])
