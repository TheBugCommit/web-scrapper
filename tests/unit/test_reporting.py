"""Unit tests for scraper.utils.reporting."""

from __future__ import annotations

from scraper import PageResult, ScrapeResult, format_result_summary, print_result_summary


def test_format_result_summary() -> None:
    page = PageResult(
        url="https://example.com/export",
        status_code=200,
        data={"_downloads": ["downloads/test/Balfeg.xls"]},
    )
    result = ScrapeResult(
        pages=[page],
        errors=[],
        duration_seconds=5.25,
    )

    summary = format_result_summary(result, title="Test Export Summary")
    assert "Test Export Summary" in summary
    assert "Finished - pages=1  errors=0" in summary
    assert "Duration: 5.2s" in summary
    assert "Downloaded files:" in summary
    assert "downloads/test/Balfeg.xls" in summary


def test_print_result_summary(capsys) -> None:
    result = ScrapeResult(pages=[], errors=[], duration_seconds=1.0)
    print_result_summary(result, title="My Title")
    captured = capsys.readouterr()
    assert "My Title" in captured.out
    assert "Finished - pages=0  errors=0" in captured.out
