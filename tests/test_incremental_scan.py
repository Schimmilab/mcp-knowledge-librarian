"""Tests for incremental directory scanning."""

import os

from mcp_knowledge_librarian.catalog import PDFCatalog


def _touch_pdf(path, content=b"%PDF-1.4 fake"):
    path.write_bytes(content)
    return path


def test_discover_files_stats_only(tmp_path):
    _touch_pdf(tmp_path / "a.pdf")
    (tmp_path / "sub").mkdir()
    _touch_pdf(tmp_path / "sub" / "b.pdf")
    (tmp_path / "not_a_pdf.txt").write_text("x")

    catalog = PDFCatalog()
    found = catalog.discover_files([str(tmp_path)])

    paths = sorted(str(p) for p, _, _ in found)
    assert len(found) == 2
    assert paths[0].endswith("a.pdf")
    assert paths[1].endswith("b.pdf")
    for _, size, mtime in found:
        assert size > 0
        assert mtime > 0


def test_select_changed(tmp_path):
    a = _touch_pdf(tmp_path / "a.pdf")
    b = _touch_pdf(tmp_path / "b.pdf")

    catalog = PDFCatalog()
    found = catalog.discover_files([str(tmp_path)])

    # a is known and unchanged, b is unknown
    a_stat = a.stat()
    known = {str(a): (a_stat.st_size, a_stat.st_mtime)}

    changed = catalog.select_changed(found, known)
    assert [str(p) for p, _, _ in changed] == [str(b)]

    # modify a -> both are pending now
    _touch_pdf(a, b"%PDF-1.4 fake but longer content")
    os.utime(a, (a_stat.st_atime, a_stat.st_mtime + 100))
    found = catalog.discover_files([str(tmp_path)])
    changed = catalog.select_changed(found, known)
    assert len(changed) == 2


def test_select_changed_null_mtime_compares_size_only(tmp_path):
    # Migrated legacy documents have no stored mtime. They must NOT all be
    # re-extracted (would re-download the whole cloud library) — size match
    # counts as unchanged.
    a = _touch_pdf(tmp_path / "a.pdf")
    a_stat = a.stat()

    catalog = PDFCatalog()
    found = catalog.discover_files([str(tmp_path)])

    known = {str(a): (a_stat.st_size, None)}
    assert catalog.select_changed(found, known) == []

    known = {str(a): (a_stat.st_size + 1, None)}
    assert len(catalog.select_changed(found, known)) == 1
