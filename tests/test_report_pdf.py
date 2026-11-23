"""Plain-assert tests for the M2 vector PDF report."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import solver.report_pdf as report_pdf
from solver.modeling import analyze, get_modeling_example
from solver.report_pdf import (
    PdfDependencyError, build_pdf, check_glyphs, page_count, simplex_table,
)


def reports():
    """Build the three sample reports plus the English athlete variant."""
    for example in ("athlete", "furniture"):
        specification = get_modeling_example(example)
        yield specification, analyze(specification), specification["lang"]
        english = dict(specification, lang="en")
        yield english, analyze(english), "en"


def test_pdf_builds_for_all_examples_and_languages():
    """M2: each report is a valid multi-page PDF in both languages."""
    for specification, analysis, lang in reports():
        pdf = build_pdf(specification, analysis, lang)
        assert pdf.startswith(b"%PDF-")
        assert page_count(pdf) >= 3
        assert pdf.endswith(b"%%EOF\n")


def test_pdf_keeps_accents_and_inequality_symbols():
    """M2: the embedded font really carries accents and ≥ / ≤."""
    specification = get_modeling_example("athlete")
    path, name = report_pdf._find_font("fr")
    check_glyphs(path, "fr")
    pdf = build_pdf(specification, analyze(specification), "fr")
    assert name.encode("ascii") in pdf
    assert b"00E9" in pdf
    assert b"2265" in pdf
    assert b"2264" in pdf


def test_pdf_graph_is_vector_not_an_image():
    """M2: the feasibility graph is drawn with vector path commands."""
    specification = get_modeling_example("athlete")
    pdf = build_pdf(specification, analyze(specification), "fr")
    assert b"/Subtype /Image" not in pdf
    assert b" m\n" in pdf
    assert b" l" in pdf
    assert b" c\n" in pdf


def test_simplex_tables_repeat_their_header():
    """M2: long simplex tables are LongTable objects with a repeated header."""
    analysis = analyze(get_modeling_example("athlete"))
    styles = report_pdf._styles("SegoeUI")
    table = simplex_table(analysis.simplex.steps[0], styles, report_pdf.PDF_LABELS["fr"])
    assert isinstance(table, report_pdf.LongTable)
    assert table.repeatRows == 1
    assert table._cellvalues[0][0] == "Base"


def test_missing_reportlab_has_a_friendly_error():
    """M2: a missing dependency is reported clearly instead of crashing."""
    previous = report_pdf._IMPORT_ERROR
    try:
        for lang in ("fr", "en"):
            report_pdf._IMPORT_ERROR = RuntimeError("import failed")
            try:
                build_pdf(get_modeling_example("athlete"),
                          analyze(get_modeling_example("athlete")), lang)
            except PdfDependencyError as error:
                assert "ReportLab" in str(error)
            else:
                raise AssertionError("PdfDependencyError was not raised")
    finally:
        report_pdf._IMPORT_ERROR = previous


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} PDF tests passed.")
