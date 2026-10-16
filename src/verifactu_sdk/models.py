"""Modelos de datos de los registros de facturación VERI*FACTU.

Los nombres siguen el diseño de registro de la AEAT (``SuministroInformacion.xsd``) en
castellano, para que sea fácil cruzarlos con la documentación oficial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum
from zoneinfo import ZoneInfo

from . import hashing

__all__ = [
    "Entorno",
    "TipoFactura",
    "Persona",
    "IDOtro",
    "SistemaInformatico",
    "LineaDesglose",
    "IDFactura",
    "RegistroAnterior",
    "RegistroAlta",
    "RegistroAnulacion",
    "Cabecera",
    "Cadena",
    "formatear_fecha",
    "formatear_fecha_hora",
    "formatear_importe",
    "ahora",
]

MADRID = ZoneInfo("Europe/Madrid")
_CENTIMO = Decimal("0.01")


class Entorno(str, Enum):
    PRUEBAS = "pruebas"
    PRODUCCION = "produccion"


class TipoFactura(str, Enum):
    F1 = "F1"  # Factura (art. 6, 7.2 y 7.3 del RD 1619/2012)
    F2 = "F2"  # Factura simplificada y facturas sin identificación del destinatario
    F3 = "F3"  # Factura emitida en sustitución de facturas simplificadas
    R1 = "R1"  # Rectificativa (art. 80.1, 80.2 y error fundado en derecho)
    R2 = "R2"  # Rectificativa (art. 80.3)
    R3 = "R3"  # Rectificativa (art. 80.4)
    R4 = "R4"  # Rectificativa (resto)
    R5 = "R5"  # Rectificativa de facturas simplificadas


def formatear_importe(valor: Decimal | int | float | str) -> str:
    """Importe con dos decimales y punto decimal, redondeo ROUND_HALF_UP."""
    d = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    return format(d.quantize(_CENTIMO, rounding=ROUND_HALF_UP), "f")


def formatear_fecha(valor: date | str) -> str:
    """Fecha en formato ``DD-MM-AAAA``. Acepta ``date``, ``AAAA-MM-DD`` o ``DD-MM-AAAA``."""
    if isinstance(valor, datetime):
        valor = valor.date()
    if isinstance(valor, date):
        return valor.strftime("%d-%m-%Y")
    s = valor.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s).strftime("%d-%m-%Y")
    datetime.strptime(s, "%d-%m-%Y")  # valida
    return s


def formatear_fecha_hora(valor: datetime) -> str:
    """Fecha y hora con huso horario (ISO 8601, sin fracciones): ``2024-01-01T19:20:30+01:00``."""
    if valor.tzinfo is None:
        raise ValueError("FechaHoraHusoGenRegistro necesita una fecha con zona horaria")
    return valor.replace(microsecond=0).isoformat()


def ahora() -> datetime:
    """Momento actual en hora peninsular española."""
    return datetime.now(MADRID).replace(microsecond=0)


@dataclass(frozen=True)
class IDOtro:
    """Identificación de una persona o entidad sin NIF español."""

    id: str
    id_type: str = "02"  # 02 NIF-IVA, 03 pasaporte, 04 documento oficial, 05 residencia, 06 otro, 07 no censado
    codigo_pais: str | None = None


@dataclass(frozen=True)
class Persona:
    """Persona física o jurídica. Debe llevar ``nif`` o ``id_otro``."""

    nombre: str
    nif: str | None = None
    id_otro: IDOtro | None = None

    def __post_init__(self) -> None:
        if (self.nif is None) == (self.id_otro is None):
            raise ValueError("Una persona debe identificarse con nif o con id_otro (solo uno)")


@dataclass(frozen=True)
class SistemaInformatico:
    """Datos del sistema informático de facturación (SIF) que genera los registros."""

    nombre_razon: str
    nif: str
    nombre_sistema: str
    id_sistema: str
    version: str
    numero_instalacion: str
    solo_verifactu: bool = True
    multi_ot: bool = False
    indicador_multiples_ot: bool = False


@dataclass(frozen=True)
class LineaDesglose:
    """Una línea del desglose de la factura (``DetalleDesglose``).

    Si se indica ``tipo_impositivo`` y no ``cuota_repercutida``, la cuota se calcula como
    ``base × tipo / 100`` redondeada al céntimo.
    """

    base_imponible: Decimal | int | float | str
    tipo_impositivo: Decimal | int | float | str | None = None
    cuota_repercutida: Decimal | int | float | str | None = None
    impuesto: str = "01"  # 01 IVA, 02 IPSI, 03 IGIC, 05 otros
    clave_regimen: str | None = "01"
    calificacion: str | None = "S1"  # S1, S2, N1, N2 (excluyente con operacion_exenta)
    operacion_exenta: str | None = None  # E1..E8
    base_imponible_a_coste: Decimal | int | float | str | None = None
    tipo_recargo_equivalencia: Decimal | int | float | str | None = None
    cuota_recargo_equivalencia: Decimal | int | float | str | None = None

    def cuota(self) -> Decimal:
        if self.cuota_repercutida is not None:
            return Decimal(formatear_importe(self.cuota_repercutida))
        if self.tipo_impositivo is not None and self.calificacion == "S1":
            base = Decimal(str(self.base_imponible))
            tipo = Decimal(str(self.tipo_impositivo))
            return Decimal(formatear_importe(base * tipo / 100))
        return Decimal("0.00")

    def recargo(self) -> Decimal:
        if self.cuota_recargo_equivalencia is not None:
            return Decimal(formatear_importe(self.cuota_recargo_equivalencia))
        if self.tipo_recargo_equivalencia is not None:
            base = Decimal(str(self.base_imponible))
            tipo = Decimal(str(self.tipo_recargo_equivalencia))
            return Decimal(formatear_importe(base * tipo / 100))
        return Decimal("0.00")

    def lleva_cuota(self) -> bool:
        return self.calificacion == "S1" and self.operacion_exenta is None


@dataclass(frozen=True)
class IDFactura:
    """Identificación de una factura (emisor, número y fecha)."""

    id_emisor: str
    num_serie: str
    fecha_expedicion: date | str


@dataclass(frozen=True)
class RegistroAnterior:
    """Eslabón de la cadena: lo que hay que guardar del último registro generado."""

    id_emisor: str
    num_serie: str
    fecha_expedicion: str
    huella: str

    def to_dict(self) -> dict[str, str]:
        return {
            "id_emisor": self.id_emisor,
            "num_serie": self.num_serie,
            "fecha_expedicion": self.fecha_expedicion,
            "huella": self.huella,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> RegistroAnterior:
        return cls(**data)


@dataclass
class RegistroAlta:
    """Registro de facturación de alta (``RegistroAlta``)."""

    emisor: Persona
    num_serie: str
    fecha_expedicion: date | str
    descripcion: str
    desglose: list[LineaDesglose]
    sistema: SistemaInformatico
    tipo_factura: TipoFactura | str = TipoFactura.F1
    destinatarios: list[Persona] = field(default_factory=list)
    cuota_total: Decimal | int | float | str | None = None
    importe_total: Decimal | int | float | str | None = None
    fecha_operacion: date | str | None = None
    tipo_rectificativa: str | None = None  # S (sustitución) o I (diferencias)
    facturas_rectificadas: list[IDFactura] = field(default_factory=list)
    facturas_sustituidas: list[IDFactura] = field(default_factory=list)
    base_rectificada: Decimal | int | float | str | None = None
    cuota_rectificada: Decimal | int | float | str | None = None
    cuota_recargo_rectificado: Decimal | int | float | str | None = None
    ref_externa: str | None = None
    subsanacion: bool = False
    rechazo_previo: str | None = None  # N, S, X
    simplificada_art7273: bool = False
    sin_destinatario_art61d: bool = False
    macrodato: bool = False
    emitida_por_tercero_o_destinatario: str | None = None  # T o D
    tercero: Persona | None = None
    cupon: bool = False
    num_registro_acuerdo: str | None = None
    id_acuerdo_sistema: str | None = None
    # Encadenamiento: lo rellena Cadena.encadenar() (o a mano).
    anterior: RegistroAnterior | None = None
    fecha_hora_huso_gen: datetime | None = None

    def __post_init__(self) -> None:
        if not self.desglose:
            raise ValueError("El registro de alta necesita al menos una línea de desglose")
        if len(self.desglose) > 12:
            raise ValueError("El desglose admite como máximo 12 líneas")
        if self.emisor.nif is None:
            raise ValueError("El emisor debe tener NIF español")

    # --- importes -----------------------------------------------------------------------------
    def cuota_total_str(self) -> str:
        if self.cuota_total is not None:
            return formatear_importe(self.cuota_total)
        return formatear_importe(
            sum((ln.cuota() + ln.recargo() for ln in self.desglose), Decimal())
        )

    def importe_total_str(self) -> str:
        if self.importe_total is not None:
            return formatear_importe(self.importe_total)
        total = sum(
            (Decimal(str(ln.base_imponible)) + ln.cuota() + ln.recargo() for ln in self.desglose),
            Decimal(),
        )
        return formatear_importe(total)

    # --- identificación y huella --------------------------------------------------------------
    @property
    def id_emisor(self) -> str:
        return self.emisor.nif  # type: ignore[return-value]

    @property
    def fecha_expedicion_str(self) -> str:
        return formatear_fecha(self.fecha_expedicion)

    @property
    def tipo_factura_str(self) -> str:
        return TipoFactura(self.tipo_factura).value

    def cadena_huella(self) -> str:
        if self.fecha_hora_huso_gen is None:
            raise ValueError("Falta fecha_hora_huso_gen: usa Cadena.encadenar() antes de generar")
        return hashing.cadena_alta(
            id_emisor=self.id_emisor,
            num_serie=self.num_serie,
            fecha_expedicion=self.fecha_expedicion_str,
            tipo_factura=self.tipo_factura_str,
            cuota_total=self.cuota_total_str(),
            importe_total=self.importe_total_str(),
            huella_anterior=self.anterior.huella if self.anterior else None,
            fecha_hora_huso_gen=formatear_fecha_hora(self.fecha_hora_huso_gen),
        )

    @property
    def huella(self) -> str:
        return hashing.huella(self.cadena_huella())

    def como_anterior(self) -> RegistroAnterior:
        return RegistroAnterior(
            self.id_emisor, self.num_serie, self.fecha_expedicion_str, self.huella
        )


@dataclass
class RegistroAnulacion:
    """Registro de facturación de anulación (``RegistroAnulacion``)."""

    factura: IDFactura
    sistema: SistemaInformatico
    ref_externa: str | None = None
    sin_registro_previo: bool = False
    rechazo_previo: bool = False
    generado_por: str | None = None  # E emisor, D destinatario, T tercero
    generador: Persona | None = None
    anterior: RegistroAnterior | None = None
    fecha_hora_huso_gen: datetime | None = None

    @property
    def fecha_expedicion_str(self) -> str:
        return formatear_fecha(self.factura.fecha_expedicion)

    def cadena_huella(self) -> str:
        if self.fecha_hora_huso_gen is None:
            raise ValueError("Falta fecha_hora_huso_gen: usa Cadena.encadenar() antes de generar")
        return hashing.cadena_anulacion(
            id_emisor=self.factura.id_emisor,
            num_serie=self.factura.num_serie,
            fecha_expedicion=self.fecha_expedicion_str,
            huella_anterior=self.anterior.huella if self.anterior else None,
            fecha_hora_huso_gen=formatear_fecha_hora(self.fecha_hora_huso_gen),
        )

    @property
    def huella(self) -> str:
        return hashing.huella(self.cadena_huella())

    def como_anterior(self) -> RegistroAnterior:
        return RegistroAnterior(
            self.factura.id_emisor, self.factura.num_serie, self.fecha_expedicion_str, self.huella
        )


@dataclass(frozen=True)
class Cabecera:
    """Cabecera del envío: obligado a expedir y, opcionalmente, representante."""

    obligado: Persona
    representante: Persona | None = None
    fecha_fin_verifactu: date | str | None = None
    incidencia: bool = False


class Cadena:
    """Mantiene el encadenamiento de huellas de un SIF.

    Guarda ``cadena.ultimo`` (``RegistroAnterior.to_dict()``) en tu base de datos tras cada
    registro y reconstruye la cadena con ``Cadena(RegistroAnterior.from_dict(...))``.
    """

    def __init__(self, ultimo: RegistroAnterior | None = None) -> None:
        self.ultimo = ultimo

    def encadenar(
        self, registro: RegistroAlta | RegistroAnulacion, momento: datetime | None = None
    ) -> RegistroAlta | RegistroAnulacion:
        registro.anterior = self.ultimo
        registro.fecha_hora_huso_gen = momento or ahora()
        self.ultimo = registro.como_anterior()
        return registro
