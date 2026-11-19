# -*- coding: utf-8 -*-
"""Сборка rup.pdf: страницы 1–2 берутся ИЗ ИСХОДНОГО РУП (Word-оригинал),
на них поверх накладывается только замена названия дисциплины,
страницы 3+ — сгенерированное тело (Golang) из eumk/rup.pdf."""
import io
import os

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIG = os.path.join(ROOT, "rup_orig.pdf")          # исходный РУП (Анализ данных в Python)
BODY = os.path.join(ROOT, "eumk", "rup.pdf")       # сгенерированное тело (страницы 3+)
OUT = os.path.join(ROOT, "eumk", "rup.pdf")

FDIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("TNR", os.path.join(FDIR, "times.ttf")))
pdfmetrics.registerFont(TTFont("TNRB", os.path.join(FDIR, "timesbd.ttf")))

# (номер страницы оригинала, начало строки-якоря, старый текст, новый текст, шрифт)
REPLACEMENTS = [
    (0, "Б1.О.15", "Б1.О.15 «АНАЛИЗ ДАННЫХ В PYTHON»",
     "Б1.О.15 «GOLANG-РАЗРАБОТКА»", "TNRB", True),
    (1, "Рабочая программа дисциплины «Анализ данных в python» составлена",
     "«Анализ данных в python»", "«Golang-разработка»", "TNR", False),
    (1, "Рабочая программа дисциплины «Анализ данных в python» утверждена",
     "«Анализ данных в python»", "«Golang-разработка»", "TNR", False),
    (1, "Рабочая программа дисциплины «Анализ данных в python» обсуждена",
     "«Анализ данных в python»", "«Golang-разработка»", "TNR", False),
]


def dev_xy(cm, tm):
    """Позиция текста в координатах страницы (tm, затем cm)."""
    x = cm[0] * tm[4] + cm[2] * tm[5] + cm[4]
    y = cm[1] * tm[4] + cm[3] * tm[5] + cm[5]
    scale = abs(cm[3]) if cm[3] else 1.0
    return x, y, scale


def find_line(reader, page_no, anchor):
    """Вернуть (x, y, size) строки, начинающейся с anchor."""
    result = {}

    def vis(text, cm, tm, fd, fs):
        line = " ".join(text.split())
        if line.startswith(" ".join(anchor.split())) and "res" not in result:
            x, y, scale = dev_xy(cm, tm)
            result["res"] = (x, y, fs * scale)

    reader.pages[page_no].extract_text(visitor_text=vis)
    return result.get("res")


def make_overlay(page_size, patches):
    """patches: [(x, y, size, old_text, new_text, font, center)]"""
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=page_size)
    for x, y, size, old_t, new_t, font, center in patches:
        w_old = pdfmetrics.stringWidth(old_t, font, size)
        w_new = pdfmetrics.stringWidth(new_t, font, size)
        # белая заплатка с запасом поверх старого текста
        # (для одинокой титульной строки — шире, для строки внутри абзаца — меньше)
        ml = 15 if center else 6
        mr = 15 if center else 5
        c.setFillColorRGB(1, 1, 1)
        c.rect(x - ml, y - size * 0.32, w_old + ml + mr, size * 1.32, fill=1, stroke=0)
        # новый текст на том же базлайне (для титульной строки — по центру старой)
        nx = x + (w_old - w_new) / 2 if center else x
        c.setFillColorRGB(0, 0, 0)
        c.setFont(font, size)
        c.drawString(nx, y, new_t)
    c.save()
    buf.seek(0)
    return PdfReader(buf).pages[0]


def main():
    orig = PdfReader(ORIG)
    body = PdfReader(BODY)

    # собираем заплатки по страницам оригинала
    per_page = {}
    for page_no, anchor, old_t, new_t, font, center in REPLACEMENTS:
        found = find_line(orig, page_no, anchor)
        if not found:
            raise SystemExit(f"НЕ НАЙДЕНА строка: {anchor!r}")
        x, y, size = found
        # для строк на стр.2 заменяемая фраза начинается не от начала строки:
        if old_t.startswith("«") and not anchor.startswith("Б1.О"):
            prefix = anchor[: anchor.index(old_t)]
            x += pdfmetrics.stringWidth(prefix, font, size)
        per_page.setdefault(page_no, []).append(
            (x, y, size, old_t, new_t, font, center))
        print(f"p{page_no+1}: {old_t!r} -> {new_t!r} @ ({x:.1f},{y:.1f}) {size:.1f}pt")

    writer = PdfWriter()
    for page_no in sorted(per_page):
        src = orig.pages[page_no]
        w = float(src.mediabox.width)
        h = float(src.mediabox.height)
        overlay = make_overlay((w, h), per_page[page_no])
        page = writer.add_page(src)   # pypdf 7: сначала в writer
        page.merge_page(overlay)
        print(f"page {page_no+1}: оригинал + заплатка")

    # тело: страницы 3.. конца сгенерированного файла
    for page in body.pages[2:]:
        writer.add_page(page)

    with open(OUT, "wb") as f:
        writer.write(f)
    print(f"OK: {OUT} ({len(writer.pages)} страниц)")


if __name__ == "__main__":
    main()
