"""Vector PDF reports for the Modeling Lab, built with ReportLab only."""

from io import BytesIO
import os
import re

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle,
    )
    from reportlab.platypus.flowables import Flowable
except ImportError as error:
    _IMPORT_ERROR = error
else:
    _IMPORT_ERROR = None

from xml.sax.saxutils import escape


PDF_LABELS = {
    "fr": {
        "title": "Rapport d'optimisation",
        "subtitle": "Modélisation guidée, résolution exacte et interprétation",
        "problem": "Énoncé du problème",
        "model": "Modélisation pas à pas",
        "graph": "Résolution graphique (tracé vectoriel)",
        "simplex": "Tableaux du simplexe",
        "iteration": "Itération",
        "basis": "Base",
        "cb": "Cb",
        "rhs": "b",
        "zj": "Zj",
        "delta": "Δj",
        "page": "Page",
        "missing": ("ReportLab n'est pas installé. Ajoutez `reportlab` à "
                    "requirements.txt puis réinstallez les dépendances."),
        "font": ("Aucune police Unicode (≥, ≤, accents) n'est disponible pour "
                 "générer le PDF."),
        "glyphs": "Cette police ne contient pas tous les symboles ≥, ≤ et les accents.",
    },
    "en": {
        "title": "Optimization report",
        "subtitle": "Guided modeling, exact solving and interpretation",
        "problem": "Problem statement",
        "model": "Step-by-step model",
        "graph": "Graphical solution (vector drawing)",
        "simplex": "Simplex tableaux",
        "iteration": "Iteration",
        "basis": "Basis",
        "cb": "Cb",
        "rhs": "b",
        "zj": "Zj",
        "delta": "Δj",
        "page": "Page",
        "missing": ("ReportLab is not installed. Add `reportlab` to "
                    "requirements.txt and reinstall dependencies."),
        "font": "No Unicode font (≥, ≤, accents) is available to generate the PDF.",
        "glyphs": "This font is missing some of the symbols ≥, ≤ or accented letters.",
    },
}

FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\segoeui.ttf", "SegoeUI"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "LiberationSans"),
    ("/Library/Fonts/Arial Unicode.ttf", "ArialUnicode"),
]
REQUIRED_GLYPHS = "éàçÉÀÇ≥≤«»"
_FONT_NAME = None


class PdfDependencyError(RuntimeError):
    """A clear, localized error when ReportLab or a Unicode font is missing."""


def page_count(pdf_bytes):
    """Count the `/Type /Page` objects written by ReportLab."""
    return len(re.findall(rb"/Type\s*/Page(?!s)", pdf_bytes))


def _require_reportlab(lang):
    """Raise a friendly error when the optional dependency is unavailable."""
    if _IMPORT_ERROR is not None:
        raise PdfDependencyError(PDF_LABELS[lang]["missing"]) from _IMPORT_ERROR


def _find_font(lang):
    """Return the first installed Unicode font and its ReportLab name."""
    for path, name in FONT_CANDIDATES:
        if os.path.exists(path):
            return path, name
    raise PdfDependencyError(PDF_LABELS[lang]["font"])


def check_glyphs(path, lang):
    """Verify that the chosen font contains accents and inequality symbols."""
    face = TTFont("_GlyphProbe", path).face
    missing = [letter for letter in REQUIRED_GLYPHS if ord(letter) not in face.charToGlyph]
    if missing:
        raise PdfDependencyError(PDF_LABELS[lang]["glyphs"])


def _register_font(path, name):
    """Register one font family once for all paragraphs and canvas labels."""
    global _FONT_NAME
    if _FONT_NAME is None:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, path))
        pdfmetrics.registerFontFamily(name, normal=name, bold=name,
                                      italic=name, boldItalic=name)
        _FONT_NAME = name
    return _FONT_NAME


def _styles(font):
    """Build compact A4 styles that all use the Unicode font."""
    common = {"fontName": font, "fontSize": 9, "leading": 13, "spaceAfter": 5}
    return {
        "title": ParagraphStyle("title", fontName=font, fontSize=17,
                                leading=21, spaceAfter=4, alignment=TA_CENTER,
                                textColor=colors.HexColor("#1f3a5f")),
        "subtitle": ParagraphStyle("subtitle", fontName=font, fontSize=9,
                                   leading=12, spaceAfter=10, alignment=TA_CENTER,
                                   textColor=colors.HexColor("#5a6b7d")),
        "heading": ParagraphStyle("heading", fontName=font, fontSize=11.5,
                                  leading=15, spaceBefore=8, spaceAfter=5,
                                  textColor=colors.HexColor("#1f3a5f")),
        "body": ParagraphStyle("body", **common),
        "small": ParagraphStyle("small", fontName=font, fontSize=7.5,
                                leading=10, spaceAfter=3),
        "code": ParagraphStyle("code", fontName=font, fontSize=8, leading=11,
                               backColor=colors.HexColor("#f2f5f9"),
                               borderPadding=5, spaceAfter=6),
    }


def _rich(text, style):
    """Escape report text while keeping interpretation line breaks."""
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def _section(title, text, styles):
    """Return a heading and its wrapped body as separate flowables."""
    return [Paragraph(escape(title), styles["heading"]),
            _rich(text, styles["body"]), Spacer(1, 3)]


def _decorate(canvas, doc, title, labels):
    """Draw the running header and footer on every page."""
    canvas.setPageCompression(0)
    canvas.saveState()
    canvas.setFont(_FONT_NAME, 7)
    canvas.setFillColor(colors.HexColor("#5a6b7d"))
    canvas.drawString(18 * mm, A4[1] - 12 * mm, title)
    canvas.drawRightString(A4[0] - 18 * mm, 12 * mm,
                           f"{labels['page']} {doc.page}")
    canvas.setStrokeColor(colors.HexColor("#d7dee7"))
    canvas.line(18 * mm, A4[1] - 14 * mm, A4[0] - 18 * mm, A4[1] - 14 * mm)
    canvas.restoreState()


class GraphFlowable(Flowable):
    """Draw the feasible region, constraint lines and optimum as vectors."""

    def __init__(self, graphical, font, labels, width=470, height=250):
        self.graphical, self.font, self.labels = graphical, font, labels
        self.width, self.height = width, height

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def _limit(self, values):
        return max(1.0, max([0.0] + list(values)) * 1.08)

    def _project(self, x, y, x_limit, y_limit):
        pad = 30
        return (pad + float(x) / x_limit * (self.width - 2 * pad),
                pad + float(y) / y_limit * (self.height - 2 * pad))

    def _endpoints(self, line, x_limit, y_limit):
        a, b, rhs = float(line["a"]), float(line["b"]), float(line["rhs"])
        points = []
        if b:
            y = rhs / b
            if 0 <= y <= y_limit:
                points.append((0.0, y))
            y = (rhs - a * x_limit) / b
            if 0 <= y <= y_limit:
                points.append((x_limit, y))
        if a:
            x = rhs / a
            if 0 <= x <= x_limit:
                points.append((x, 0.0))
            x = (rhs - b * y_limit) / a
            if 0 <= x <= x_limit:
                points.append((x, y_limit))
        unique = sorted({(round(x, 6), round(y, 6)) for x, y in points})
        return unique[:2]

    def _limits(self, graph):
        x = self._limit([line.get("x_intercept") or 0 for line in graph["lines"]] +
                        [point["x"] for point in graph["polygon"]])
        y = self._limit([line.get("y_intercept") or 0 for line in graph["lines"]] +
                        [point["y"] for point in graph["polygon"]])
        return x, y

    def _draw_lines(self, canvas, graph, x_limit, y_limit):
        canvas.setStrokeColor(colors.HexColor("#8ba3bd"))
        for line in graph["lines"]:
            ends = self._endpoints(line, x_limit, y_limit)
            if len(ends) == 2:
                first = self._project(*ends[0], x_limit, y_limit)
                second = self._project(*ends[1], x_limit, y_limit)
                canvas.line(*first, *second)

    def _draw_region(self, canvas, graph, x_limit, y_limit):
        points = [self._project(point["x"], point["y"], x_limit, y_limit)
                  for point in graph["polygon"]]
        if len(points) < 3:
            return
        path = canvas.beginPath()
        path.moveTo(*points[0])
        for point in points[1:]:
            path.lineTo(*point)
        path.close()
        canvas.setFillColor(colors.HexColor("#dceaf7"))
        canvas.drawPath(path, fill=1, stroke=0)

    def _draw_points(self, canvas, graph, x_limit, y_limit):
        for point in graph["polygon"]:
            position = self._project(point["x"], point["y"], x_limit, y_limit)
            color = "#c0392b" if point["optimal"] else "#1f3a5f"
            canvas.setFillColor(colors.HexColor(color))
            canvas.circle(position[0], position[1], 3 if point["optimal"] else 2,
                          stroke=0, fill=1)
            canvas.drawString(position[0] + 4, position[1] + 4,
                              f"({point['x_text']}; {point['y_text']})")

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setFont(self.font, 7)
        graph = self.graphical or {"lines": [], "polygon": []}
        x_limit, y_limit = self._limits(graph)
        self._draw_lines(canvas, graph, x_limit, y_limit)
        self._draw_region(canvas, graph, x_limit, y_limit)
        self._draw_points(canvas, graph, x_limit, y_limit)
        canvas.setFillColor(colors.HexColor("#5a6b7d"))
        canvas.drawString(30, self.height - 12, self.labels["graph"])
        canvas.restoreState()


def simplex_table(step, styles, labels):
    """Build one simplex tableau with a header repeated when it splits."""
    header = [labels["basis"], labels["cb"], *step["col_names"], labels["rhs"]]
    rows = [[basis, cb, *values, rhs] for basis, cb, values, rhs in zip(
        step["basis"], step["cb"], step["rows"], step["b"])]
    rows.append([labels["zj"], "", *step["zj"], step["z"]])
    rows.append([labels["delta"], "", *step["delta"], ""])
    width = 383 / max(len(header) - 2, 1)
    table = LongTable([header] + rows, colWidths=[52, 30] + [width] * (len(header) - 2),
                      repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), styles["small"].fontName),
        ("FONTSIZE", (0, 0), (-1, -1), 5.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c4d1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, -2), (-1, -1), colors.HexColor("#eef3f8")),
    ]))
    return table


def _overview_story(spec, analysis, styles, labels):
    """Build the title, statement and interpretation sections."""
    title = f"{labels['title']} — {spec['title']}"
    story = [Paragraph(escape(title), styles["title"]),
             Paragraph(escape(labels["subtitle"]), styles["subtitle"]),
             Paragraph(escape(labels["problem"]), styles["heading"]),
             _rich(spec["statement"], styles["body"]), Spacer(1, 4)]
    for section in analysis.interpretation["sections"].values():
        story.extend(_section(section["title"], section["text"], styles))
    return story


def _model_story(analysis, styles, labels):
    """Build the modeling steps, complete model and vector graph."""
    story = [Paragraph(escape(labels["model"]), styles["heading"])]
    for step in analysis.model.steps:
        story.extend(_section(f"{step['number']}. {step['title']}", step["text"], styles))
    story.append(_rich(analysis.model.lp_text, styles["code"]))
    if analysis.graphical:
        story.append(Spacer(1, 6))
        story.append(GraphFlowable(analysis.graphical, styles["body"].fontName, labels))
    return story


def _simplex_story(analysis, styles, labels):
    """Build the tableau appendix in reading order."""
    story = [PageBreak(), Paragraph(escape(labels["simplex"]), styles["heading"])]
    for step in analysis.simplex.steps:
        story.append(_rich(f"{labels['iteration']} {step['iteration']}: {step['message']}",
                           styles["small"]))
        story.append(simplex_table(step, styles, labels))
        story.append(Spacer(1, 10))
    return story


def build_pdf(spec, analysis, lang="fr"):
    """Return a complete A4 PDF report as bytes for one Modeling Lab analysis."""
    lang = lang if lang in PDF_LABELS else spec["lang"]
    _require_reportlab(lang)
    path, name = _find_font(lang)
    check_glyphs(path, lang)
    font = _register_font(path, name)
    labels = PDF_LABELS[lang]
    styles = _styles(font)
    title = f"{labels['title']} — {spec['title']}"
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm,
                                 rightMargin=18 * mm, topMargin=20 * mm,
                                 bottomMargin=18 * mm, title=title)
    story = _overview_story(spec, analysis, styles, labels)
    story.append(PageBreak())
    story.extend(_model_story(analysis, styles, labels))
    story.extend(_simplex_story(analysis, styles, labels))
    document.build(story, onFirstPage=lambda canvas, doc: _decorate(canvas, doc, title, labels),
                   onLaterPages=lambda canvas, doc: _decorate(canvas, doc, title, labels))
    return buffer.getvalue()
