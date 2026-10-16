"""Validación del dígito de control de NIF, NIE y CIF españoles.

Solo comprueba el formato y el carácter de control; no consulta el censo de la AEAT.
"""

from __future__ import annotations

import re

__all__ = ["validar_nif", "es_nif_valido", "tipo_nif"]

_LETRAS = "TRWAGMYFPDXBNJZSQVHLCKE"
_DNI = re.compile(r"^(\d{8})([A-Z])$")
_NIE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")
_KLM = re.compile(r"^([KLM])(\d{7})([A-Z])$")
_CIF = re.compile(r"^([ABCDEFGHJNPQRSUVW])(\d{7})([0-9A-J])$")


def _normalizar(nif: str) -> str:
    return re.sub(r"[\s\-.]", "", nif).upper()


def _control_cif(digitos: str) -> int:
    suma = 0
    for i, c in enumerate(digitos):
        n = int(c)
        if i % 2 == 0:  # posiciones impares (1, 3, 5, 7)
            n *= 2
            n = n // 10 + n % 10
        suma += n
    return (10 - suma % 10) % 10


def tipo_nif(nif: str) -> str | None:
    """``"DNI"``, ``"NIE"``, ``"KLM"`` o ``"CIF"`` si el NIF es válido; ``None`` si no."""
    s = _normalizar(nif)
    if m := _DNI.match(s):
        return "DNI" if _LETRAS[int(m[1]) % 23] == m[2] else None
    if m := _NIE.match(s):
        n = int(str("XYZ".index(m[1])) + m[2])
        return "NIE" if _LETRAS[n % 23] == m[3] else None
    if m := _KLM.match(s):
        return "KLM" if _LETRAS[int(m[2]) % 23] == m[3] else None
    if m := _CIF.match(s):
        letra, digitos, control = m[1], m[2], m[3]
        d = _control_cif(digitos)
        como_letra, como_digito = "JABCDEFGHI"[d], str(d)
        if letra in "PQRSNW":
            validos = {como_letra}
        elif letra in "ABEH":
            validos = {como_digito}
        else:
            validos = {como_letra, como_digito}
        return "CIF" if control in validos else None
    return None


def es_nif_valido(nif: str) -> bool:
    return tipo_nif(nif) is not None


def validar_nif(nif: str) -> str:
    """Devuelve el NIF normalizado (sin espacios ni guiones, en mayúsculas) o lanza ``ValueError``."""
    if tipo_nif(nif) is None:
        raise ValueError(f"NIF no válido: {nif!r}")
    return _normalizar(nif)
