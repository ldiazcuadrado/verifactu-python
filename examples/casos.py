"""Casos habituales de VERI*FACTU sin enviar nada a la AEAT.

Ejecuta: python examples/casos.py
Genera el XML de cada caso, lo valida contra el XSD oficial y muestra la huella.
"""

from datetime import date

from lxml import etree

from verifactu_sdk import (
    Cabecera,
    Cadena,
    IDFactura,
    IDOtro,
    LineaDesglose,
    Persona,
    RegistroAlta,
    RegistroAnulacion,
    SistemaInformatico,
    construir_peticion,
    url_qr,
    validar,
)

EMISOR = Persona("Mi Empresa SL", nif="B12345674")
SISTEMA = SistemaInformatico(
    nombre_razon="Mi Empresa SL",
    nif="B12345674",
    nombre_sistema="MiFacturador",
    id_sistema="01",
    version="1.0.0",
    numero_instalacion="1",
)
HOY = date.today()

cadena = Cadena()  # en tu aplicación: Cadena(RegistroAnterior.from_dict(lo_guardado))

# 1. Factura ordinaria con dos tipos de IVA (21 % y 10 %).
ordinaria = RegistroAlta(
    emisor=EMISOR,
    num_serie="2026-A-0001",
    fecha_expedicion=HOY,
    descripcion="Material de oficina y servicio de montaje",
    destinatarios=[Persona("Cliente SA", nif="A28015865")],
    desglose=[
        LineaDesglose(base_imponible="200.00", tipo_impositivo="21"),
        LineaDesglose(base_imponible="50.00", tipo_impositivo="10"),
    ],
    sistema=SISTEMA,
)

# 2. Cliente extranjero (NIF-IVA de la UE) con operación exenta (art. 25 LIVA → E5).
extranjero = RegistroAlta(
    emisor=EMISOR,
    num_serie="2026-A-0002",
    fecha_expedicion=HOY,
    descripcion="Entrega intracomunitaria de bienes",
    destinatarios=[Persona("Kunde GmbH", id_otro=IDOtro("DE123456789", "02", "DE"))],
    desglose=[LineaDesglose(base_imponible="1000.00", operacion_exenta="E5", calificacion=None)],
    sistema=SISTEMA,
)

# 3. Rectificativa por diferencias de la factura 1 (devolución de 50 € + IVA).
rectificativa = RegistroAlta(
    emisor=EMISOR,
    num_serie="2026-R-0001",
    fecha_expedicion=HOY,
    tipo_factura="R1",
    tipo_rectificativa="I",
    facturas_rectificadas=[IDFactura(EMISOR.nif, "2026-A-0001", HOY)],
    descripcion="Devolución parcial",
    destinatarios=[Persona("Cliente SA", nif="A28015865")],
    desglose=[LineaDesglose(base_imponible="-50.00", tipo_impositivo="21")],
    sistema=SISTEMA,
)

# 4. Anulación de la factura 2 (emitida por error).
anulacion = RegistroAnulacion(IDFactura(EMISOR.nif, "2026-A-0002", HOY), SISTEMA)

registros = [ordinaria, extranjero, rectificativa, anulacion]
for r in registros:
    cadena.encadenar(r)

peticion = construir_peticion(Cabecera(EMISOR), registros)
validar(peticion)  # lanza ErrorValidacionXSD si algo no cuadra

for r in registros:
    nombre = r.num_serie if isinstance(r, RegistroAlta) else f"anulación {r.factura.num_serie}"
    print(f"{nombre:<24} {r.huella}")

print("\nQR de la factura 1:")
print(
    url_qr(
        nif=EMISOR.nif,
        num_serie=ordinaria.num_serie,
        fecha_expedicion=ordinaria.fecha_expedicion,
        importe_total=ordinaria.importe_total_str(),
    )
)
print("\nÚltimo eslabón a guardar:", cadena.ultimo.to_dict())
print("\n" + etree.tostring(peticion, pretty_print=True, encoding="unicode")[:1500] + "…")
