"""Synthetic standard-table PDF with out-of-order labels and VAT/net prices."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def make_pdf(
    *,
    trade_vt=3180,
    capacity=0,
    territory="ČEZ Distribuce",
    duplicate=False,
    missing=False,
    inconsistent=False,
    effective="30. 1. 2026",
):
    """Amounts are test data; no customer PDF is bundled or uploaded by tests."""
    labels = {
        1: "Vysoký tarif Kč/MWh",
        2: "Nízký tarif Kč/MWh",
        3: "Stálá platba Kč/měsíc",
        4: "Vysoký tarif Kč/MWh",
        5: "Nízký tarif Kč/MWh",
        6: "do 3× 10 A a do 1× 25 A včetně Kč/měsíc",
        7: "nad 3× 10 A do 3× 16 A včetně Kč/měsíc",
        8: "nad 3× 16 A do 3× 20 A včetně Kč/měsíc",
        9: "nad 3× 20 A do 3× 25 A včetně Kč/měsíc",
        10: "nad 3× 25 A do 3× 32 A včetně Kč/měsíc",
        11: "nad 3× 32 A do 3× 40 A včetně Kč/měsíc",
        12: "nad 3× 40 A do 3× 50 A včetně Kč/měsíc",
        13: "nad 3× 50 A do 3× 63 A včetně Kč/měsíc",
        14: "nad 3× 63 A do 3× 80 A včetně Kč/měsíc",
        15: "nad 3× 80 A do 3× 100 A včetně Kč/měsíc",
        16: "nad 3× 100 A do 3× 125 A včetně Kč/měsíc",
        17: "nad 3× 125 A do 3× 160 A včetně Kč/měsíc",
        18: "nad 3× 160 A za každý 1 A Kč/měsíc",
        19: "nad 3× 63 A za každý 1 A Kč/měsíc",
        20: "nad 1× 25 A za každý 1 A Kč/měsíc",
        21: "Daň z elektřiny Kč/MWh",
        22: "Cena za systémové služby Kč/MWh",
        23: "Cena za provoz nesíťové infrastruktury Kč/měsíc",
        24: "Podle jističe Kč/A/počet fází",
        25: "Podle spotřeby Kč/MWh",
        26: "Vysoký tarif (řádky 1 + 4 + 21 + 22) Kč/MWh",
        27: "Nízký tarif (řádky 2 + 5 + 21 + 22) Kč/MWh",
    }
    values = {
        1: [2890, trade_vt, 3020],
        2: [None, 3050, 2770],
        3: [163.35] * 3,
        4: [3226.66, 913.27, 2725.46],
        5: [None, 140.97, 140.97],
        6: [60.50, 268.62, 129.47],
        7: [95.59, 429.55, 208.12],
        8: [119.79, 537.24, 260.15],
        9: [150.04, 671.55, 325.49],
        10: [191.18, 859.10, 416.24],
        11: [239.58, 1084.16, 520.30],
        12: [300.08, 1559.69, 649.77],
        13: [377.52, 2358.29, 819.17],
        14: [None, 3742.53, None],
        15: [None, 6455.35, None],
        16: [None, 12669.91, None],
        17: [None, 23713.58, None],
        18: [None, 148.21, None],
        19: [5.99, None, 13.00],
        20: [2, 49.40, 4.33],
        21: [34.24] * 3,
        22: [198.73] * 3,
        23: [15.57] * 3,
        24: [capacity] * 3,
        25: [598.95] * 3,
        26: [
            6349.63,
            trade_vt + 913.27 + 34.24 + 198.73 + (100 if inconsistent else 0.01),
            5978.44,
        ],
        27: [None, 3423.94, 3143.94],
    }

    def item(x, y, text):
        encoded = text.encode("cp1250").hex()
        return f"BT /F1 6 Tf 1 0 0 1 {x} {y} Tm <{encoded}> Tj ET\n"

    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=1000)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Encoding"),
                    NameObject("/BaseEncoding"): NameObject("/WinAnsiEncoding"),
                }
            ),
        }
    )
    # Use a ToUnicode map so Czech labels are extracted independently of fonts.
    cmap = DecodedStreamObject()
    cmap.set_data(
        (
            "/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /Test def /CMapType 2 def 1 begincodespacerange <00> <FF> endcodespacerange 256 beginbfchar\n"
            + "\n".join(
                f"<{i:02x}> <{bytes([i]).decode('cp1250', errors='replace').encode('utf-16-be').hex()}>"
                for i in range(256)
            )
            + "\nendbfchar endcmap CMapName currentdict /CMap defineresource pop end end"
        ).encode()
    )
    font[NameObject("/ToUnicode")] = writer._add_object(cmap)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    content = item(28, 980, "ČEZ Prodej Ceník elektřiny pro domácnosti")
    content += item(28, 965, f"Účinnost obchodních cen: od {effective}")
    content += item(28, 950, "Účinnost distribučních cen: od 1. 1. 2026")
    content += item(28, 935, f"Distribuční území: {territory}")
    content += item(28, 910, "Distribuční sazba D01d D57d D25d")
    for row, label in labels.items():
        y = 880 - row * 25
        content += item(28, y, str(row)) + item(40, y, label)
    for row, nums in reversed(list(values.items())):
        if missing and row == 22:
            continue
        y = 880 - row * 25
        text = " ".join(
            "–" if n is None else f"{n:,.2f}".replace(",", " ").replace(".", ",")
            for n in nums
        )
        content += item(220, y + 3.5, text)
        content += item(
            220,
            y - 4,
            " ".join(f"({(n or 0) / 1.21:.2f})".replace(".", ",") for n in nums),
        )
    content += item(
        28, 80, "Tučně uvedené ceny jsou s 21% DPH a ceny v závorce bez DPH."
    )
    stream = DecodedStreamObject()
    stream.set_data(content.encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    if duplicate:
        writer.add_page(page)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()
