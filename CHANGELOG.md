# Changelog

## 0.1.0 — 2026-10-16

Primera versión.

- Huella SHA-256 de registros de alta, anulación y evento (verificada con los ejemplos oficiales).
- `Cadena` para encadenar registros y persistir el último eslabón.
- XML `RegFactuSistemaFacturacion` validado contra los XSD oficiales `tikeV1.0` incluidos.
- URL y código QR tributario (PNG/SVG), entornos de pruebas y producción, sistemas no VERI*FACTU.
- `ClienteVerifactu`: envío SOAP con certificado PEM o PKCS#12, certificado de sello, control de flujo.
- Interpretación de respuestas y SOAP Fault.
- Validación de NIF/NIE/CIF.
- CLI `verifactu` y servidor MCP `verifactu-sdk-mcp`.
