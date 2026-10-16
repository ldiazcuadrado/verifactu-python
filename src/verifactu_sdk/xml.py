"""Generación y validación del XML ``RegFactuSistemaFacturacion``.

El orden de los elementos sigue ``SuministroInformacion.xsd`` de la AEAT, que se distribuye
con el paquete para poder validar sin conexión.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache
from importlib import resources

from lxml import etree

from .models import (
    Cabecera,
    IDFactura,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnulacion,
    SistemaInformatico,
    formatear_fecha,
    formatear_fecha_hora,
    formatear_importe,
)

__all__ = [
    "NS_SF",
    "NS_LR",
    "NS_SOAP",
    "MAX_REGISTROS",
    "construir_peticion",
    "sobre_soap",
    "validar",
    "ErrorValidacionXSD",
]

_BASE = "https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/tike/cont/ws/"
NS_SF = _BASE + "SuministroInformacion.xsd"
NS_LR = _BASE + "SuministroLR.xsd"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
MAX_REGISTROS = 1000
_NSMAP = {"sum": NS_LR, "sum1": NS_SF}


class ErrorValidacionXSD(ValueError):
    """El XML no cumple el esquema oficial. ``errores`` contiene los mensajes de libxml2."""

    def __init__(self, errores: list[str]) -> None:
        super().__init__("XML no válido según el XSD de la AEAT:\n" + "\n".join(errores))
        self.errores = errores


def _sf(padre: etree._Element, nombre: str, texto: str | None = None) -> etree._Element:
    el = etree.SubElement(padre, f"{{{NS_SF}}}{nombre}")
    if texto is not None:
        el.text = texto
    return el


def _sn(valor: bool) -> str:
    return "S" if valor else "N"


def _persona(padre: etree._Element, nombre: str, p: Persona) -> None:
    el = _sf(padre, nombre)
    _sf(el, "NombreRazon", p.nombre)
    if p.nif is not None:
        _sf(el, "NIF", p.nif)
    else:
        assert p.id_otro is not None
        otro = _sf(el, "IDOtro")
        if p.id_otro.codigo_pais:
            _sf(otro, "CodigoPais", p.id_otro.codigo_pais)
        _sf(otro, "IDType", p.id_otro.id_type)
        _sf(otro, "ID", p.id_otro.id)


def _id_factura(padre: etree._Element, nombre: str, f: IDFactura) -> None:
    el = _sf(padre, nombre)
    _sf(el, "IDEmisorFactura", f.id_emisor)
    _sf(el, "NumSerieFactura", f.num_serie)
    _sf(el, "FechaExpedicionFactura", formatear_fecha(f.fecha_expedicion))


def _sistema(padre: etree._Element, s: SistemaInformatico) -> None:
    el = _sf(padre, "SistemaInformatico")
    _sf(el, "NombreRazon", s.nombre_razon)
    _sf(el, "NIF", s.nif)
    _sf(el, "NombreSistemaInformatico", s.nombre_sistema)
    _sf(el, "IdSistemaInformatico", s.id_sistema)
    _sf(el, "Version", s.version)
    _sf(el, "NumeroInstalacion", s.numero_instalacion)
    _sf(el, "TipoUsoPosibleSoloVerifactu", _sn(s.solo_verifactu))
    _sf(el, "TipoUsoPosibleMultiOT", _sn(s.multi_ot))
    _sf(el, "IndicadorMultiplesOT", _sn(s.indicador_multiples_ot))


def _encadenamiento(padre: etree._Element, registro: RegistroAlta | RegistroAnulacion) -> None:
    enc = _sf(padre, "Encadenamiento")
    if registro.anterior is None:
        _sf(enc, "PrimerRegistro", "S")
        return
    ant = _sf(enc, "RegistroAnterior")
    _sf(ant, "IDEmisorFactura", registro.anterior.id_emisor)
    _sf(ant, "NumSerieFactura", registro.anterior.num_serie)
    _sf(ant, "FechaExpedicionFactura", registro.anterior.fecha_expedicion)
    _sf(ant, "Huella", registro.anterior.huella)


def _detalle(padre: etree._Element, ln: LineaDesglose) -> None:
    el = _sf(padre, "DetalleDesglose")
    if ln.impuesto:
        _sf(el, "Impuesto", ln.impuesto)
    if ln.clave_regimen:
        _sf(el, "ClaveRegimen", ln.clave_regimen)
    if ln.operacion_exenta:
        _sf(el, "OperacionExenta", ln.operacion_exenta)
    else:
        _sf(el, "CalificacionOperacion", ln.calificacion or "S1")
    if ln.tipo_impositivo is not None and ln.lleva_cuota():
        _sf(el, "TipoImpositivo", formatear_importe(ln.tipo_impositivo))
    _sf(el, "BaseImponibleOimporteNoSujeto", formatear_importe(ln.base_imponible))
    if ln.base_imponible_a_coste is not None:
        _sf(el, "BaseImponibleACoste", formatear_importe(ln.base_imponible_a_coste))
    if ln.lleva_cuota():
        _sf(el, "CuotaRepercutida", format(ln.cuota(), "f"))
        if ln.tipo_recargo_equivalencia is not None:
            _sf(el, "TipoRecargoEquivalencia", formatear_importe(ln.tipo_recargo_equivalencia))
        if ln.tipo_recargo_equivalencia is not None or ln.cuota_recargo_equivalencia is not None:
            _sf(el, "CuotaRecargoEquivalencia", format(ln.recargo(), "f"))


def _registro_alta(padre: etree._Element, r: RegistroAlta) -> None:
    if r.fecha_hora_huso_gen is None:
        raise ValueError("Encadena el registro (Cadena.encadenar) antes de generar el XML")
    el = _sf(padre, "RegistroAlta")
    _sf(el, "IDVersion", "1.0")
    idf = _sf(el, "IDFactura")
    _sf(idf, "IDEmisorFactura", r.id_emisor)
    _sf(idf, "NumSerieFactura", r.num_serie)
    _sf(idf, "FechaExpedicionFactura", r.fecha_expedicion_str)
    if r.ref_externa:
        _sf(el, "RefExterna", r.ref_externa)
    _sf(el, "NombreRazonEmisor", r.emisor.nombre)
    if r.subsanacion:
        _sf(el, "Subsanacion", "S")
    if r.rechazo_previo:
        _sf(el, "RechazoPrevio", r.rechazo_previo)
    _sf(el, "TipoFactura", r.tipo_factura_str)
    if r.tipo_rectificativa:
        _sf(el, "TipoRectificativa", r.tipo_rectificativa)
    if r.facturas_rectificadas:
        cont = _sf(el, "FacturasRectificadas")
        for f in r.facturas_rectificadas:
            _id_factura(cont, "IDFacturaRectificada", f)
    if r.facturas_sustituidas:
        cont = _sf(el, "FacturasSustituidas")
        for f in r.facturas_sustituidas:
            _id_factura(cont, "IDFacturaSustituida", f)
    if r.base_rectificada is not None or r.cuota_rectificada is not None:
        imp = _sf(el, "ImporteRectificacion")
        _sf(imp, "BaseRectificada", formatear_importe(r.base_rectificada or 0))
        _sf(imp, "CuotaRectificada", formatear_importe(r.cuota_rectificada or 0))
        if r.cuota_recargo_rectificado is not None:
            _sf(imp, "CuotaRecargoRectificado", formatear_importe(r.cuota_recargo_rectificado))
    if r.fecha_operacion is not None:
        _sf(el, "FechaOperacion", formatear_fecha(r.fecha_operacion))
    _sf(el, "DescripcionOperacion", r.descripcion)
    if r.simplificada_art7273:
        _sf(el, "FacturaSimplificadaArt7273", "S")
    if r.sin_destinatario_art61d:
        _sf(el, "FacturaSinIdentifDestinatarioArt61d", "S")
    if r.macrodato:
        _sf(el, "Macrodato", "S")
    if r.emitida_por_tercero_o_destinatario:
        _sf(el, "EmitidaPorTerceroODestinatario", r.emitida_por_tercero_o_destinatario)
    if r.tercero is not None:
        _persona(el, "Tercero", r.tercero)
    if r.destinatarios:
        dest = _sf(el, "Destinatarios")
        for p in r.destinatarios:
            _persona(dest, "IDDestinatario", p)
    if r.cupon:
        _sf(el, "Cupon", "S")
    desg = _sf(el, "Desglose")
    for ln in r.desglose:
        _detalle(desg, ln)
    _sf(el, "CuotaTotal", r.cuota_total_str())
    _sf(el, "ImporteTotal", r.importe_total_str())
    _encadenamiento(el, r)
    _sistema(el, r.sistema)
    _sf(el, "FechaHoraHusoGenRegistro", formatear_fecha_hora(r.fecha_hora_huso_gen))
    if r.num_registro_acuerdo:
        _sf(el, "NumRegistroAcuerdoFacturacion", r.num_registro_acuerdo)
    if r.id_acuerdo_sistema:
        _sf(el, "IdAcuerdoSistemaInformatico", r.id_acuerdo_sistema)
    _sf(el, "TipoHuella", "01")
    _sf(el, "Huella", r.huella)


def _registro_anulacion(padre: etree._Element, r: RegistroAnulacion) -> None:
    if r.fecha_hora_huso_gen is None:
        raise ValueError("Encadena el registro (Cadena.encadenar) antes de generar el XML")
    el = _sf(padre, "RegistroAnulacion")
    _sf(el, "IDVersion", "1.0")
    idf = _sf(el, "IDFactura")
    _sf(idf, "IDEmisorFacturaAnulada", r.factura.id_emisor)
    _sf(idf, "NumSerieFacturaAnulada", r.factura.num_serie)
    _sf(idf, "FechaExpedicionFacturaAnulada", r.fecha_expedicion_str)
    if r.ref_externa:
        _sf(el, "RefExterna", r.ref_externa)
    if r.sin_registro_previo:
        _sf(el, "SinRegistroPrevio", "S")
    if r.rechazo_previo:
        _sf(el, "RechazoPrevio", "S")
    if r.generado_por:
        _sf(el, "GeneradoPor", r.generado_por)
    if r.generador is not None:
        _persona(el, "Generador", r.generador)
    _encadenamiento(el, r)
    _sistema(el, r.sistema)
    _sf(el, "FechaHoraHusoGenRegistro", formatear_fecha_hora(r.fecha_hora_huso_gen))
    _sf(el, "TipoHuella", "01")
    _sf(el, "Huella", r.huella)


def construir_peticion(
    cabecera: Cabecera, registros: Sequence[RegistroAlta | RegistroAnulacion]
) -> etree._Element:
    """Elemento ``sum:RegFactuSistemaFacturacion`` con la cabecera y hasta 1000 registros."""
    if not registros:
        raise ValueError("Un envío necesita al menos un registro")
    if len(registros) > MAX_REGISTROS:
        raise ValueError(f"Un envío admite como máximo {MAX_REGISTROS} registros")
    raiz = etree.Element(f"{{{NS_LR}}}RegFactuSistemaFacturacion", nsmap=_NSMAP)
    cab = etree.SubElement(raiz, f"{{{NS_LR}}}Cabecera")
    _persona(cab, "ObligadoEmision", cabecera.obligado)
    if cabecera.representante is not None:
        _persona(cab, "Representante", cabecera.representante)
    if cabecera.fecha_fin_verifactu is not None or cabecera.incidencia:
        vol = _sf(cab, "RemisionVoluntaria")
        if cabecera.fecha_fin_verifactu is not None:
            _sf(vol, "FechaFinVeriFactu", formatear_fecha(cabecera.fecha_fin_verifactu))
        if cabecera.incidencia:
            _sf(vol, "Incidencia", "S")
    for r in registros:
        cont = etree.SubElement(raiz, f"{{{NS_LR}}}RegistroFactura")
        if isinstance(r, RegistroAlta):
            _registro_alta(cont, r)
        else:
            _registro_anulacion(cont, r)
    return raiz


def sobre_soap(peticion: etree._Element) -> bytes:
    """Envuelve la petición en un sobre SOAP 1.1 listo para enviar."""
    env = etree.Element(f"{{{NS_SOAP}}}Envelope", nsmap={"soapenv": NS_SOAP, **_NSMAP})
    etree.SubElement(env, f"{{{NS_SOAP}}}Header")
    body = etree.SubElement(env, f"{{{NS_SOAP}}}Body")
    body.append(peticion)
    return etree.tostring(env, xml_declaration=True, encoding="UTF-8")


@lru_cache(maxsize=1)
def _esquema() -> etree.XMLSchema:
    ruta = resources.files("verifactu_sdk") / "schemas" / "SuministroLR.xsd"
    with resources.as_file(ruta) as fichero:
        parser = etree.XMLParser(no_network=True, load_dtd=False, resolve_entities=False)
        return etree.XMLSchema(etree.parse(str(fichero), parser))


def validar(xml: etree._Element | bytes | str) -> None:
    """Valida contra el XSD oficial. Acepta la petición o un sobre SOAP completo.

    Lanza :class:`ErrorValidacionXSD` si no es válido.
    """
    if isinstance(xml, str):
        xml = xml.encode("utf-8")
    if isinstance(xml, bytes):
        xml = etree.fromstring(xml, etree.XMLParser(resolve_entities=False, no_network=True))
    if xml.tag == f"{{{NS_SOAP}}}Envelope":
        cuerpo = xml.find(f"{{{NS_SOAP}}}Body")
        if cuerpo is None or len(cuerpo) == 0:
            raise ErrorValidacionXSD(["El sobre SOAP no tiene cuerpo"])
        xml = cuerpo[0]
    esquema = _esquema()
    if not esquema.validate(xml):
        raise ErrorValidacionXSD([f"línea {e.line}: {e.message}" for e in esquema.error_log])
