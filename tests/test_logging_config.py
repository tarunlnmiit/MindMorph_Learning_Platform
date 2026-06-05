"""Logging setup: idempotent root configuration that writes to a rotating file + console."""
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.append(ROOT)

import logging_config


def _reset():
    """Force a clean reconfigure for each test (module caches a one-shot flag)."""
    logging_config._configured = False
    logging.getLogger().handlers.clear()


def test_setup_logging_attaches_console_and_file_handlers():
    _reset()
    logging_config.setup_logging("INFO")
    handlers = logging.getLogger().handlers
    kinds = {type(h).__name__ for h in handlers}
    assert "StreamHandler" in kinds
    assert "RotatingFileHandler" in kinds


def test_setup_logging_is_idempotent():
    _reset()
    logging_config.setup_logging("INFO")
    count = len(logging.getLogger().handlers)
    logging_config.setup_logging("INFO")  # second call must not add handlers
    assert len(logging.getLogger().handlers) == count


def test_setup_logging_writes_to_file(tmp_path, monkeypatch):
    _reset()
    log_file = tmp_path / "test.log"
    monkeypatch.setattr(logging_config, "LOG_FILE", str(log_file))
    monkeypatch.setattr(logging_config, "LOG_DIR", str(tmp_path))

    logging_config.setup_logging("INFO")
    logging.getLogger("agents.unit").info("hello from a module")
    for h in logging.getLogger().handlers:
        h.flush()

    assert log_file.exists()
    assert "hello from a module" in log_file.read_text()
    assert "agents.unit" in log_file.read_text()
