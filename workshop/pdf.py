import io
import os
from xml.sax.saxutils import escape

import qrcode
from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONT_DIRS = [
    os.path.join(settings.BASE_DIR, "workshop", "static", "fonts"),
    "/usr/share/fonts/truetype/dejavu",
    r"C:\Windows\Fonts",
]
FONT_CANDIDATES = {
    "regular": ["DejaVuSans.ttf", "arial.ttf"],
    "bold": ["DejaVuSans-Bold.ttf", "arialbd.ttf"],
}


def _find_font(kind):
    for directory in FONT_DIRS:
        for filename in FONT_CANDIDATES[kind]:
            path = os.path.join(directory, filename)
            if os.path.exists(path):
                return path
    return None


def _register_fonts():
    regular, bold = _find_font("regular"), _find_font("bold") or _find_font("regular")
    if not regular:
        return "Helvetica", "Helvetica-Bold"
    if "AppFont" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("AppFont", regular))
        pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
    return "AppFont", "AppFont-Bold"


def build_receipt_pdf(repair_request):
    """Акт приёма-передачи и квитанция с QR-кодом на публичную страницу статуса."""
    regular, bold = _register_fonts()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Квитанция {repair_request.number}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TitleRu", parent=styles["Title"], fontName=bold, fontSize=16, leading=20
    )
    subtitle = ParagraphStyle(
        "SubRu", parent=styles["Normal"], fontName=regular, fontSize=9.5, leading=13,
        alignment=TA_CENTER, textColor=colors.HexColor("#555555"),
    )
    normal = ParagraphStyle(
        "NormalRu", parent=styles["Normal"], fontName=regular, fontSize=10, leading=14,
        alignment=TA_LEFT,
    )
    small = ParagraphStyle(
        "SmallRu", parent=styles["Normal"], fontName=regular, fontSize=8, leading=10,
        textColor=colors.HexColor("#666666"),
    )
    heading = ParagraphStyle(
        "HeadingRu", parent=styles["Heading2"], fontName=bold, fontSize=11, leading=14,
        spaceBefore=8, spaceAfter=4,
    )

    qr_content = f"{settings.SITE_URL}/status/{repair_request.public_token}/"
    qr_image = qrcode.make(qr_content)
    qr_buffer = io.BytesIO()
    qr_image.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    story = [
        Paragraph("Ремонтная мастерская «Мастер+»", title),
        Paragraph(
            "АКТ ПРИЁМА-ПЕРЕДАЧИ И КВИТАНЦИЯ<br/>"
            "г. Москва · +7 (495) 000-00-00 · info@masterplus.local",
            subtitle,
        ),
        Spacer(1, 7 * mm),
    ]

    header_data = [
        [
            Paragraph(f"<b>Заявка:</b> {repair_request.number}", normal),
            Paragraph(
                f"<b>Дата:</b> {timezone.localtime(repair_request.created_at):%d.%m.%Y %H:%M}",
                normal,
            ),
        ],
        [
            Paragraph(f"<b>Статус:</b> {escape(repair_request.get_status_display())}", normal),
            Paragraph(
                f"<b>Мастер:</b> "
                f"{escape(repair_request.master.full_name) if repair_request.master else 'не назначен'}",
                normal,
            ),
        ],
        [
            Paragraph(f"<b>Клиент:</b> {escape(repair_request.client.full_name)}", normal),
            Paragraph(
                f"<b>Телефон:</b> {escape(repair_request.client.phone or 'не указан')}", normal
            ),
        ],
    ]
    header = Table(header_data, colWidths=[90 * mm, 84 * mm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 4 * mm))

    device = (
        f"{repair_request.get_device_type_display()}"
        + (f" · {escape(repair_request.device_model)}" if repair_request.device_model else "")
    )
    details = Table(
        [
            [Paragraph("<b>Устройство</b>", normal), Paragraph(device, normal)],
            [
                Paragraph("<b>Неисправность</b>", normal),
                Paragraph(escape(repair_request.description).replace("\n", "<br/>"), normal),
            ],
            [
                Paragraph("<b>Услуга</b>", normal),
                Paragraph(
                    escape(repair_request.service.name) if repair_request.service else "—", normal
                ),
            ],
            [
                Paragraph("<b>Предварительная стоимость</b>", normal),
                Paragraph(
                    f"{repair_request.estimated_cost:,.2f} ₽".replace(",", " ")
                    if repair_request.estimated_cost is not None
                    else "Уточняется после диагностики",
                    normal,
                ),
            ],
        ],
        colWidths=[50 * mm, 124 * mm],
    )
    details.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d5d9e0")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f3f5f8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(details)
    story.append(Paragraph("Использованные запчасти и работы", heading))

    parts_rows = [[
        Paragraph("<b>Наименование</b>", normal),
        Paragraph("<b>Кол-во</b>", normal),
        Paragraph("<b>Цена, ₽</b>", normal),
        Paragraph("<b>Сумма, ₽</b>", normal),
    ]]
    for used in repair_request.used_parts.select_related("part"):
        parts_rows.append([
            Paragraph(escape(used.part.name), normal),
            Paragraph(str(used.quantity), normal),
            Paragraph(f"{used.price:,.2f}".replace(",", " "), normal),
            Paragraph(f"{used.total:,.2f}".replace(",", " "), normal),
        ])
    if len(parts_rows) == 1:
        parts_rows.append([Paragraph("Запчасти не использовались", normal), "", "", ""])
    parts_rows.append([
        Paragraph("<b>Работы</b>", normal), "", "",
        Paragraph(f"<b>{repair_request.work_cost:,.2f}</b>".replace(",", " "), normal),
    ])
    parts_rows.append([
        Paragraph("<b>Итого</b>", normal), "", "",
        Paragraph(f"<b>{repair_request.total_cost:,.2f}</b>".replace(",", " "), normal),
    ])
    parts = Table(parts_rows, colWidths=[90 * mm, 22 * mm, 31 * mm, 31 * mm])
    parts.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d5d9e0")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f5f8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("SPAN", (0, -2), (2, -2)),
                ("SPAN", (0, -1), (2, -1)),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(parts)
    story.append(Spacer(1, 5 * mm))

    qr = Image(qr_buffer, width=32 * mm, height=32 * mm)
    qr_block = Table(
        [[qr, Paragraph(
            "Наведите камеру телефона на QR-код, чтобы открыть актуальный статус заявки "
            "без входа в личный кабинет.",
            small,
        )]],
        colWidths=[36 * mm, 138 * mm],
    )
    qr_block.setStyle(
        TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)])
    )
    story.append(qr_block)
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Устройство принято без разборки. Окончательная стоимость определяется после "
            "диагностики и согласуется с клиентом. Гарантия на выполненные работы — 90 дней. "
            "Клиент подтверждает, что ознакомлен с правилами обслуживания.",
            small,
        )
    )
    story.append(Spacer(1, 10 * mm))
    signatures = Table(
        [
            ["____________________ / Клиент", "____________________ / Мастер"],
            [escape(repair_request.client.full_name), escape(
                repair_request.master.full_name if repair_request.master else "—"
            )],
        ],
        colWidths=[87 * mm, 87 * mm],
    )
    signatures.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), regular),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#555555")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(signatures)
    doc.build(story)
    return buffer.getvalue()
