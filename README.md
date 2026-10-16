# verifactu-python · Librería Python para VERI\*FACTU (AEAT)

[![PyPI](https://img.shields.io/pypi/v/verifactu-sdk.svg)](https://pypi.org/project/verifactu-sdk/)
[![Python](https://img.shields.io/pypi/pyversions/verifactu-sdk.svg)](https://pypi.org/project/verifactu-sdk/)
[![CI](https://github.com/ldiazcuadrado/verifactu-python/actions/workflows/ci.yml/badge.svg)](https://github.com/ldiazcuadrado/verifactu-python/actions/workflows/ci.yml)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-blue.svg)](LICENSE)

**Implementa VERI\*FACTU en tu software de facturación con Python**: huella SHA-256 encadenada,
XML validado contra el XSD oficial de la Agencia Tributaria, código QR tributario y envío SOAP
con certificado a la AEAT. Incluye CLI y **servidor MCP** para usarlo desde Claude, Cursor y otros
agentes de IA.

[English version](README.en.md)

```bash
pip install verifactu-sdk          # núcleo: huella, XML, envío
pip install "verifactu-sdk[qr]"    # + imágenes PNG/SVG del QR
pip install "verifactu-sdk[all]"   # + certificados .p12 y servidor MCP
```

## Qué incluye

| Requisito VERI\*FACTU | Módulo | Estado |
| --- | --- | --- |
| Huella o *hash* SHA-256 de alta, anulación y evento | `verifactu_sdk.hashing` | ✅ Verificado con los 3 ejemplos oficiales de la AEAT |
| Encadenamiento de registros (`RegistroAnterior`, `PrimerRegistro`) | `Cadena` | ✅ |
| XML `RegFactuSistemaFacturacion` (alta, anulación, rectificativas, exentas, extranjeros) | `verifactu_sdk.xml` | ✅ Validado contra `SuministroLR.xsd` |
| URL y código QR tributario (ISO 18004, corrección M) | `verifactu_sdk.qr` | ✅ Ejemplos oficiales |
| Envío SOAP con certificado (PEM o `.p12`), entornos de pruebas y producción, certificado de sello | `ClienteVerifactu` | ✅ |
| Control de flujo (`TiempoEsperaEnvio`, 1000 registros por envío) | `ClienteVerifactu` | ✅ |
| Respuesta de la AEAT: CSV, estado por registro, códigos de error, SOAP Fault | `parsear_respuesta` | ✅ |
| Validación de NIF / NIE / CIF | `verifactu_sdk.nif` | ✅ |
| Consulta de registros (`ConsultaFactuSistemaFacturacion`) | | 🔜 |
| Firma XAdES para sistemas no VERI\*FACTU | | 🔜 |

Sin dependencias pesadas: `lxml` y `httpx`. Python 3.10 o superior. Con tipado (`py.typed`).

## Ejemplo rápido

```python
from datetime import date
from verifactu_sdk import (
    Cabecera,
    Cadena,
    ClienteVerifactu,
    Entorno,
    LineaDesglose,
    Persona,
    RegistroAlta,
    SistemaInformatico,
    url_qr,
)

emisor = Persona("Mi Empresa SL", nif="B12345674")
sistema = SistemaInformatico(
    nombre_razon="Mi Empresa SL",
    nif="B12345674",
    nombre_sistema="MiFacturador",
    id_sistema="01",
    version="1.0.0",
    numero_instalacion="1",
)

factura = RegistroAlta(
    emisor=emisor,
    num_serie="2026-A-0001",
    fecha_expedicion=date.today(),
    descripcion="Servicios de consultoría",
    destinatarios=[Persona("Cliente SA", nif="A28015865")],
    desglose=[LineaDesglose(base_imponible="100.00", tipo_impositivo="21")],  # cuota 21.00
    sistema=sistema,
)

# 1. Encadena: calcula la huella usando la del registro anterior.
cadena = Cadena(ultimo=None)  # recupera aquí el último eslabón guardado en tu BD
cadena.encadenar(factura)
print(factura.huella)  # 64 caracteres hexadecimales en mayúsculas
guardar_en_bd(cadena.ultimo.to_dict())

# 2. QR para imprimir en la factura.
print(
    url_qr(
        nif=emisor.nif,
        num_serie=factura.num_serie,
        fecha_expedicion=factura.fecha_expedicion,
        importe_total=factura.importe_total_str(),
    )
)

# 3. Envío a la AEAT (entorno de pruebas).
with ClienteVerifactu("certificado.p12", password="****", entorno=Entorno.PRUEBAS) as aeat:
    respuesta = aeat.enviar(Cabecera(emisor), [factura])
    print(respuesta.estado, respuesta.csv)
    for linea in respuesta.errores:
        print(linea.num_serie, linea.codigo_error, linea.descripcion_error)
```

Encontrarás más casos en [`examples/`](examples/): rectificativas, anulaciones, operaciones
exentas y destinatarios extranjeros.

### Solo la huella

```python
from verifactu_sdk import huella_alta

huella_alta(
    id_emisor="89890001K",
    num_serie="12345678/G33",
    fecha_expedicion="01-01-2024",
    tipo_factura="F1",
    cuota_total="12.35",
    importe_total="123.45",
    huella_anterior=None,
    fecha_hora_huso_gen="2024-01-01T19:20:30+01:00",
)
# '3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60'  (ejemplo oficial AEAT)
```

### Validar un XML que ya generas

```python
from verifactu_sdk import validar, ErrorValidacionXSD

try:
    validar(open("registro.xml", "rb").read())  # petición o sobre SOAP completo
except ErrorValidacionXSD as e:
    print(e.errores)
```

## Línea de comandos

```bash
verifactu huella alta --nif 89890001K --numserie 12345678/G33 --fecha 01-01-2024 \
  --cuota 12.35 --importe 123.45 --fechahora 2024-01-01T19:20:30+01:00
verifactu qr --nif 89890001K --numserie A-1 --fecha 2026-10-01 --importe 121 --png qr.png
verifactu validar registro.xml
verifactu nif B12345674 X1234567L
```

## Servidor MCP para Claude, Cursor y otros agentes

Sirve para pedirle a tu asistente de IA que calcule huellas, genere el XML de un registro, lo
valide contra el XSD o construya la URL del QR. El servidor no envía nada a la AEAT.

```bash
# Claude Code
claude mcp add verifactu -- uvx --from "verifactu-sdk[mcp]" verifactu-sdk-mcp
```

```json
// Claude Desktop / Cursor (mcpServers)
{ "verifactu": { "command": "uvx", "args": ["--from", "verifactu-sdk[mcp]", "verifactu-sdk-mcp"] } }
```

Herramientas: `calcular_huella_alta`, `calcular_huella_anulacion`, `generar_url_qr`,
`validar_nif`, `construir_registro_alta`, `validar_xml_verifactu`.

## Preguntas frecuentes

### ¿Qué es VERI\*FACTU?
Es el sistema de la Agencia Tributaria que desarrolla el Reglamento de requisitos de los sistemas
informáticos de facturación (Real Decreto 1007/2023, la llamada «ley antifraude»). Cada factura
genera un registro con una huella encadenada a la anterior. El registro se envía a la AEAT y la
factura impresa lleva un código QR que el cliente puede verificar.

### ¿Cómo se calcula la huella (hash) de VERI\*FACTU en Python?
Se concatenan los campos `IDEmisorFactura`, `NumSerieFactura`, `FechaExpedicionFactura`,
`TipoFactura`, `CuotaTotal`, `ImporteTotal`, `Huella` (la del registro anterior) y
`FechaHoraHusoGenRegistro` con el formato `campo=valor&...`. Sobre esa cadena se aplica SHA-256 y
el resultado se expresa en hexadecimal y mayúsculas. `huella_alta()` lo hace por ti, y
`verifactu huella -v` muestra la cadena intermedia para depurar.

### ¿Cómo genero el código QR de la factura?
Con `url_qr()` obtienes la URL de cotejo (`ValidarQR?nif=…&numserie=…&fecha=…&importe=…`) ya
codificada. Con `qr_png()` o `qr_svg()` obtienes la imagen con nivel de corrección M. Encima del
QR debe ir el texto `TEXTO_QR` y debajo la leyenda `LEYENDA_VERIFACTU`.

### ¿Qué certificado necesito para enviar a la AEAT?
Un certificado electrónico cualificado: de persona física, de representante de entidad o de
sello. Puedes cargarlo en PEM (`clave=`) o en `.p12`/`.pfx` (extra `pkcs12`). Para el certificado
de sello usa `sello=True`.

### ¿Hay un entorno de pruebas?
Sí. `Entorno.PRUEBAS` apunta al portal de pruebas externas de la AEAT (`prewww1.aeat.es`) y es el
valor por defecto. Cambia a `Entorno.PRODUCCION` solo cuando todo funcione.

### ¿Funciona con Django, FastAPI, Flask u Odoo?
Sí. Es una librería pura, sin framework. Guarda `cadena.ultimo.to_dict()` en tu base de datos
dentro de la misma transacción que la factura, para que la cadena nunca se rompa.

### ¿Cuándo es obligatorio?
El calendario lo fija la normativa vigente: hoy, el Real Decreto 1007/2023 con sus
modificaciones posteriores. Consulta siempre la
[sede de la AEAT](https://sede.agenciatributaria.gob.es/Sede/iva/sistemas-informaticos-facturacion-verifactu.html).

## Documentación oficial que implementa

- Detalle de las especificaciones técnicas para la generación de la huella o hash (v0.1.2)
- Detalle de las especificaciones técnicas del código QR de la factura (v0.5.0)
- Descripción del servicio web de VERI\*FACTU y esquemas XSD/WSDL (`tikeV1.0`), incluidos en
  `verifactu_sdk/schemas/`

## Aviso

Este proyecto **no es oficial** y no está vinculado a la Agencia Tributaria. Cumplir el
reglamento, incluida la declaración responsable del productor del software, es responsabilidad
de quien lo integra. Prueba siempre en el entorno de pruebas antes de pasar a producción.

## Contribuir

Se agradecen issues y PRs, sobre todo los casos reales que rechace la AEAT (con los datos
anonimizados). Para desarrollar:

```bash
uv sync && uv run pytest
```

Licencia [MIT](LICENSE).
