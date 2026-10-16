"""verifactu-sdk: VERI*FACTU (AEAT) para Python.

Huella SHA-256 encadenada, XML validado contra el XSD oficial, URL y código QR, y cliente SOAP
con certificado para enviar los registros de facturación a la Agencia Tributaria.
"""

from .client import ClienteVerifactu, ErrorAEAT, RespuestaEnvio, RespuestaLinea, parsear_respuesta
from .hashing import huella, huella_alta, huella_anulacion, huella_evento
from .models import (
    Cabecera,
    Cadena,
    Entorno,
    IDFactura,
    IDOtro,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnterior,
    RegistroAnulacion,
    SistemaInformatico,
    TipoFactura,
)
from .nif import es_nif_valido, validar_nif
from .qr import LEYENDA_VERIFACTU, TEXTO_QR, qr_png, qr_svg, url_qr
from .xml import ErrorValidacionXSD, construir_peticion, sobre_soap, validar

__version__ = "0.1.0"

__all__ = [
    "Cabecera",
    "Cadena",
    "ClienteVerifactu",
    "Entorno",
    "ErrorAEAT",
    "ErrorValidacionXSD",
    "IDFactura",
    "IDOtro",
    "LEYENDA_VERIFACTU",
    "LineaDesglose",
    "Persona",
    "RegistroAlta",
    "RegistroAnterior",
    "RegistroAnulacion",
    "RespuestaEnvio",
    "RespuestaLinea",
    "SistemaInformatico",
    "TEXTO_QR",
    "TipoFactura",
    "construir_peticion",
    "es_nif_valido",
    "huella",
    "huella_alta",
    "huella_anulacion",
    "huella_evento",
    "parsear_respuesta",
    "qr_png",
    "qr_svg",
    "sobre_soap",
    "url_qr",
    "validar",
    "validar_nif",
]
