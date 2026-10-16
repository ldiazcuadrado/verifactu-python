# verifactu-python · Python library for Spain's VERI\*FACTU (AEAT)

**Make your invoicing software compliant with Spain's VERI\*FACTU e-invoicing rules in Python.**
It covers the chained SHA-256 record hash (*huella*), XML validated against the official AEAT XSD,
the tax QR code, and SOAP submission to the Spanish Tax Agency with a client certificate. A CLI
and an **MCP server** for Claude, Cursor and other AI agents are included.

[Versión en español](README.md)

```bash
pip install verifactu-sdk          # core: hash, XML, submission
pip install "verifactu-sdk[qr]"    # + PNG/SVG QR images
pip install "verifactu-sdk[all]"   # + .p12 certificates and MCP server
```

## Features

- Record hash for invoice registration, cancellation and event records. It is tested against the
  three official AEAT examples.
- Hash chaining through `Cadena`: persist `cadena.ultimo.to_dict()` and restore it later.
- `RegFactuSistemaFacturacion` XML for invoices, credit notes (*rectificativas*), cancellations,
  exempt operations and foreign customers. It is validated offline against the bundled official
  XSD (`tikeV1.0`).
- QR URL and image (ISO 18004, error-correction level M) for the test and production
  environments.
- `ClienteVerifactu` accepts PEM or PKCS#12 certificates, including *sello* (company seal)
  certificates. It enforces the mandatory flow control (`TiempoEsperaEnvio`, at most 1000 records
  per request) and parses AEAT responses and SOAP faults.
- Spanish NIF/NIE/CIF checksum validation.
- The CLI provides `verifactu huella | qr | validar | nif`.
- The MCP server is `verifactu-sdk-mcp`. Its tools have no side effects and never submit to the
  AEAT.

```python
from datetime import date
from verifactu_sdk import Cadena, LineaDesglose, Persona, RegistroAlta, SistemaInformatico

invoice = RegistroAlta(
    emisor=Persona("My Company SL", nif="B12345674"),
    num_serie="2026-A-0001",
    fecha_expedicion=date.today(),
    descripcion="Consulting services",
    desglose=[LineaDesglose(base_imponible="100.00", tipo_impositivo="21")],
    sistema=SistemaInformatico("My Company SL", "B12345674", "MyBilling", "01", "1.0.0", "1"),
)
Cadena().encadenar(invoice)
print(invoice.huella)
```

The API uses the Spanish field names from the official AEAT schema, so you can map it one to one
to the government documentation. See [README.md](README.md) for the full guide.

```bash
claude mcp add verifactu -- uvx --from "verifactu-sdk[mcp]" verifactu-sdk-mcp
```

This is **not an official AEAT project**. MIT licensed.
