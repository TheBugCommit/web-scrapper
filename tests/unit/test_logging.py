"""Unit tests for scraper.utils.logging.get_portal_logger.

configure_logging() is a process-wide singleton: once any portal calls it,
later calls with a different log_dir are silent no-ops, so running more than
one portal in the same process (sequentially or concurrently) silently loses
all but the first portal's logs. get_portal_logger() attaches handlers to a
named per-portal logger instead, giving each portal a genuinely isolated,
rotated log file regardless of how many other portals run in the same
process.

Test names use distinct portal keys per test — logging.getLogger() caches
loggers by name for the process lifetime, so reusing a key across tests
would make the second call return the already-configured logger and ignore
its (different) tmp_path.
"""

from __future__ import annotations

from pathlib import Path

from scraper.utils.logging import get_portal_logger


def test_get_portal_logger_creates_isolated_rotating_files(tmp_path: Path) -> None:
    logger = get_portal_logger("test_portal_a", tmp_path, debug=False)
    logger.info("hello from portal a")
    logger.error("boom")

    for handler in logger.handlers:
        handler.flush()

    general_log = tmp_path / "scraper.log"
    error_log = tmp_path / "error.log"
    assert general_log.exists()
    assert error_log.exists()

    general_content = general_log.read_text(encoding="utf-8")
    assert "hello from portal a" in general_content
    assert "boom" in general_content

    error_content = error_log.read_text(encoding="utf-8")
    assert "hello from portal a" not in error_content
    assert "boom" in error_content


def test_get_portal_logger_is_isolated_per_portal(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    logger_a = get_portal_logger("isolated_a", dir_a)
    logger_b = get_portal_logger("isolated_b", dir_b)

    logger_a.info("only in a")
    logger_b.info("only in b")
    for h in list(logger_a.handlers) + list(logger_b.handlers):
        h.flush()

    a_content = (dir_a / "scraper.log").read_text(encoding="utf-8")
    b_content = (dir_b / "scraper.log").read_text(encoding="utf-8")

    assert "only in a" in a_content
    assert "only in b" not in a_content
    assert "only in b" in b_content
    assert "only in a" not in b_content


def test_get_portal_logger_is_idempotent(tmp_path: Path) -> None:
    logger1 = get_portal_logger("idempotent_portal", tmp_path)
    handler_count = len(logger1.handlers)
    logger2 = get_portal_logger("idempotent_portal", tmp_path)

    assert logger1 is logger2
    assert len(logger2.handlers) == handler_count


def test_get_portal_logger_does_not_propagate_to_root(tmp_path: Path) -> None:
    logger = get_portal_logger("no_propagate_portal", tmp_path)
    assert logger.propagate is False
