import pytest

from verifactu_sdk.cli import main
from verifactu_sdk.models import Entorno
from verifactu_sdk.nif import es_nif_valido, tipo_nif, validar_nif
from verifactu_sdk.qr import qr_png, qr_svg, url_qr


# --- QR: ejemplos del documento de la AEAT (v0.5.0, apartados 4 y 8) ---------------------------
def test_url_qr_codifica_parametros():
    assert url_qr(
        nif="89890001K",
        num_serie="12345678&G33",
        fecha_expedicion="01-01-2024",
        importe_total="241.4",
    ) == (
        "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?nif=89890001K"
        "&numserie=12345678%26G33&fecha=01-01-2024&importe=241.40"
    )


@pytest.mark.parametrize(
    ("entorno", "verifactu", "base"),
    [
        (Entorno.PRUEBAS, True, "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?"),
        (Entorno.PRUEBAS, False, "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu?"),
        (
            Entorno.PRODUCCION,
            True,
            "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?",
        ),
        (
            Entorno.PRODUCCION,
            False,
            "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQRNoVerifactu?",
        ),
    ],
)
def test_url_qr_entornos(entorno, verifactu, base):
    url = url_qr(
        nif="89890001K",
        num_serie="12345678-G33",
        fecha_expedicion="2024-09-01",
        importe_total=241.4,
        entorno=entorno,
        verifactu=verifactu,
    )
    assert url == base + "nif=89890001K&numserie=12345678-G33&fecha=01-09-2024&importe=241.40"


def test_url_qr_rechaza_no_ascii():
    with pytest.raises(ValueError):
        url_qr(nif="89890001K", num_serie="Nº1", fecha_expedicion="01-01-2024", importe_total=1)


def test_qr_imagenes():
    url = url_qr(nif="89890001K", num_serie="A-1", fecha_expedicion="01-01-2024", importe_total=1)
    assert qr_png(url).startswith(b"\x89PNG")
    assert qr_svg(url).lstrip().startswith("<svg")


# --- NIF ---------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("nif", "tipo"),
    [
        ("89890001K", "DNI"),  # NIF de pruebas de la AEAT
        ("12345678Z", "DNI"),
        ("X1234567L", "NIE"),
        ("Y1234567X", "NIE"),
        ("B12345674", "CIF"),
        ("Q2826000H", "CIF"),
        ("12345678-z", "DNI"),
    ],
)
def test_nif_validos(nif, tipo):
    assert tipo_nif(nif) == tipo


@pytest.mark.parametrize("nif", ["12345678A", "X1234567A", "B12345675", "Q2826000A", "", "123"])
def test_nif_invalidos(nif):
    assert not es_nif_valido(nif)


def test_validar_nif_normaliza():
    assert validar_nif(" 12345678-z ") == "12345678Z"
    with pytest.raises(ValueError):
        validar_nif("12345678A")


# --- CLI ---------------------------------------------------------------------------------------
def test_cli_huella_caso1(capsys):
    assert (
        main(
            [
                "huella",
                "alta",
                "--nif",
                "89890001K",
                "--numserie",
                "12345678/G33",
                "--fecha",
                "01-01-2024",
                "--cuota",
                "12.35",
                "--importe",
                "123.45",
                "--fechahora",
                "2024-01-01T19:20:30+01:00",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == (
        "3C464DAF61ACB827C65FDA19F352A4E3BDC2C640E9E9FC4CC058073F38F12F60"
    )


def test_cli_nif(capsys):
    assert main(["nif", "89890001K"]) == 0
    assert main(["nif", "12345678A"]) == 1


def test_cli_qr(capsys, tmp_path):
    png = tmp_path / "qr.png"
    main(
        [
            "qr",
            "--nif",
            "89890001K",
            "--numserie",
            "A-1",
            "--fecha",
            "01-01-2024",
            "--importe",
            "10",
            "--png",
            str(png),
        ]
    )
    assert "ValidarQR?nif=89890001K" in capsys.readouterr().out
    assert png.read_bytes().startswith(b"\x89PNG")
