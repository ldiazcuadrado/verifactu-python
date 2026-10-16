"""Cliente SOAP del servicio VERI*FACTU de la AEAT (``RegFactuSistemaFacturacion``).

Autenticación con certificado electrónico cualificado (PEM o PKCS#12) y control de flujo según
el art. 16.2 de la orden: espera ``TiempoEsperaEnvio`` segundos entre envíos (60 por defecto) o
hasta acumular 1000 registros.
"""

from __future__ import annotations

import os
import ssl
import tempfile
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from lxml import etree

from .models import Cabecera, Entorno, RegistroAlta, RegistroAnulacion
from .xml import NS_SOAP, construir_peticion, sobre_soap, validar

__all__ = [
    "ENDPOINTS",
    "ClienteVerifactu",
    "ErrorAEAT",
    "RespuestaEnvio",
    "RespuestaLinea",
    "parsear_respuesta",
]

ENDPOINTS: dict[tuple[Entorno, bool], str] = {
    (
        Entorno.PRUEBAS,
        False,
    ): "https://prewww1.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (
        Entorno.PRUEBAS,
        True,
    ): "https://prewww10.aeat.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (
        Entorno.PRODUCCION,
        False,
    ): "https://www1.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
    (
        Entorno.PRODUCCION,
        True,
    ): "https://www10.agenciatributaria.gob.es/wlpl/TIKE-CONT/ws/SistemaFacturacion/VerifactuSOAP",
}
"""Endpoints del WSDL oficial. El segundo elemento de la clave indica certificado de sello."""


class ErrorAEAT(Exception):
    """La AEAT respondió con un SOAP Fault (el envío completo se rechaza).

    ``reintentable`` es ``True`` para ``soapenv:Server``: la AEAT indica reenviar el mensaje.
    """

    def __init__(self, faultcode: str, faultstring: str) -> None:
        super().__init__(f"{faultcode}: {faultstring}")
        self.faultcode = faultcode
        self.faultstring = faultstring
        self.reintentable = faultcode.endswith("Server")


@dataclass(frozen=True)
class RespuestaLinea:
    id_emisor: str
    num_serie: str
    fecha_expedicion: str
    tipo_operacion: str
    estado: str  # Correcto, AceptadoConErrores, Incorrecto
    codigo_error: int | None = None
    descripcion_error: str | None = None
    ref_externa: str | None = None

    @property
    def aceptado(self) -> bool:
        return self.estado in ("Correcto", "AceptadoConErrores")


@dataclass(frozen=True)
class RespuestaEnvio:
    estado: str  # Correcto, ParcialmenteCorrecto, Incorrecto
    tiempo_espera: int
    csv: str | None
    lineas: list[RespuestaLinea] = field(default_factory=list)
    xml: bytes = b""

    @property
    def correcto(self) -> bool:
        return self.estado == "Correcto"

    @property
    def errores(self) -> list[RespuestaLinea]:
        return [ln for ln in self.lineas if ln.estado != "Correcto"]


def _local(el: etree._Element) -> str:
    return etree.QName(el).localname


def _hijo(el: etree._Element, nombre: str) -> etree._Element | None:
    for h in el:
        if isinstance(h.tag, str) and _local(h) == nombre:
            return h
    return None


def _texto(el: etree._Element, *ruta: str) -> str | None:
    actual: etree._Element | None = el
    for nombre in ruta:
        if actual is None:
            return None
        actual = _hijo(actual, nombre)
    return actual.text.strip() if actual is not None and actual.text else None


def parsear_respuesta(contenido: bytes) -> RespuestaEnvio:
    """Interpreta la respuesta SOAP de la AEAT. Lanza :class:`ErrorAEAT` ante un Fault."""
    raiz = etree.fromstring(contenido, etree.XMLParser(resolve_entities=False, no_network=True))
    cuerpo = raiz.find(f"{{{NS_SOAP}}}Body")
    if cuerpo is None or len(cuerpo) == 0:
        raise ErrorAEAT("Client", "Respuesta sin cuerpo SOAP")
    resp = cuerpo[0]
    if _local(resp) == "Fault":
        raise ErrorAEAT(_texto(resp, "faultcode") or "", _texto(resp, "faultstring") or "")
    lineas = []
    for ln in resp:
        if not isinstance(ln.tag, str) or _local(ln) != "RespuestaLinea":
            continue
        codigo = _texto(ln, "CodigoErrorRegistro")
        lineas.append(
            RespuestaLinea(
                id_emisor=_texto(ln, "IDFactura", "IDEmisorFactura") or "",
                num_serie=_texto(ln, "IDFactura", "NumSerieFactura") or "",
                fecha_expedicion=_texto(ln, "IDFactura", "FechaExpedicionFactura") or "",
                tipo_operacion=_texto(ln, "Operacion", "TipoOperacion") or "",
                estado=_texto(ln, "EstadoRegistro") or "",
                codigo_error=int(codigo) if codigo else None,
                descripcion_error=_texto(ln, "DescripcionErrorRegistro"),
                ref_externa=_texto(ln, "RefExterna"),
            )
        )
    return RespuestaEnvio(
        estado=_texto(resp, "EstadoEnvio") or "",
        tiempo_espera=int(_texto(resp, "TiempoEsperaEnvio") or 60),
        csv=_texto(resp, "CSV"),
        lineas=lineas,
        xml=contenido,
    )


def _contexto_ssl(
    certificado: str | os.PathLike[str],
    clave: str | os.PathLike[str] | None,
    password: str | bytes | None,
) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ruta = Path(certificado)
    if ruta.suffix.lower() in (".p12", ".pfx"):
        try:
            from cryptography.hazmat.primitives.serialization import (
                Encoding,
                NoEncryption,
                PrivateFormat,
                pkcs12,
            )
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Para certificados .p12/.pfx instala: pip install 'verifactu-sdk[pkcs12]'"
            ) from exc
        pw = password.encode() if isinstance(password, str) else password
        key, cert, extra = pkcs12.load_key_and_certificates(ruta.read_bytes(), pw)
        if key is None or cert is None:
            raise ValueError("El fichero PKCS#12 no contiene clave y certificado")
        pem = key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        pem += cert.public_bytes(Encoding.PEM)
        for c in extra or []:
            pem += c.public_bytes(Encoding.PEM)
        fd, tmp = tempfile.mkstemp(suffix=".pem")
        try:
            os.chmod(tmp, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(pem)
            ctx.load_cert_chain(tmp)
        finally:
            os.unlink(tmp)
    else:
        ctx.load_cert_chain(str(ruta), str(clave) if clave else None, password)
    return ctx


class ClienteVerifactu:
    """Envía registros de facturación a la AEAT.

    >>> cliente = ClienteVerifactu("certificado.p12", password="...", entorno=Entorno.PRUEBAS)
    >>> respuesta = cliente.enviar(Cabecera(emisor), [registro])
    """

    def __init__(
        self,
        certificado: str | os.PathLike[str],
        *,
        clave: str | os.PathLike[str] | None = None,
        password: str | bytes | None = None,
        entorno: Entorno = Entorno.PRUEBAS,
        sello: bool = False,
        timeout: float = 60.0,
        validar_xsd: bool = True,
        url: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.url = url or ENDPOINTS[(Entorno(entorno), sello)]
        self.validar_xsd = validar_xsd
        self.tiempo_espera = 0
        self._ultimo_envio: float | None = None
        verify: ssl.SSLContext | bool = (
            True if transport is not None else _contexto_ssl(certificado, clave, password)
        )
        self._http = httpx.Client(verify=verify, timeout=timeout, transport=transport)

    def __enter__(self) -> ClienteVerifactu:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def segundos_hasta_siguiente_envio(self) -> float:
        if self._ultimo_envio is None:
            return 0.0
        return max(0.0, self._ultimo_envio + self.tiempo_espera - time.monotonic())

    def enviar(
        self,
        cabecera: Cabecera,
        registros: Sequence[RegistroAlta | RegistroAnulacion],
        *,
        esperar: bool = True,
    ) -> RespuestaEnvio:
        """Envía hasta 1000 registros respetando el control de flujo.

        Con ``esperar=False`` lanza ``RuntimeError`` si aún no ha pasado ``TiempoEsperaEnvio``
        y el lote tiene menos de 1000 registros.
        """
        restante = self.segundos_hasta_siguiente_envio()
        if restante > 0 and len(registros) < 1000:
            if not esperar:
                raise RuntimeError(f"Control de flujo: espera {restante:.0f} s antes de enviar")
            time.sleep(restante)
        peticion = construir_peticion(cabecera, registros)
        if self.validar_xsd:
            validar(peticion)
        resp = self._http.post(
            self.url,
            content=sobre_soap(peticion),
            headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '""'},
        )
        self._ultimo_envio = time.monotonic()
        if resp.status_code >= 400 and b"Fault" not in resp.content:
            resp.raise_for_status()
        resultado = parsear_respuesta(resp.content)
        self.tiempo_espera = resultado.tiempo_espera
        return resultado
