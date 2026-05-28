from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import traceback
from pathlib import Path

_log_file_path: Path | None = None
_initialized = False


def _log_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    elif system == "Darwin":
        base = Path.home() / "Library" / "Logs"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "coralX"


def log_path() -> Path:
    """Return the path to the active log file."""
    return _log_file_path if _log_file_path is not None else _log_dir() / "coralX.log"


def setup_logging(level: int = logging.DEBUG) -> None:
    """Configure root logger with a rotating file handler plus a stderr handler for WARNING+."""
    global _initialized, _log_file_path
    if _initialized:
        return

    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    _log_file_path = log_dir / "coralX.log"

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    fh = logging.handlers.RotatingFileHandler(
        _log_file_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def install_excepthook() -> None:
    """Log unhandled exceptions and show an error dialog before the app terminates."""
    _orig = sys.excepthook
    _crash_log = logging.getLogger("coralX.crash")

    def _hook(exc_type: type[BaseException], exc_value: BaseException, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _orig(exc_type, exc_value, exc_tb)
            return

        _crash_log.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))

        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
                msg = QMessageBox()
                msg.setWindowTitle("coralX — Unexpected Error")
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.setText(
                    "An unexpected error occurred.\n\n"
                    f"<b>{exc_type.__name__}:</b> {exc_value}"
                )
                msg.setInformativeText(f"Full details saved to:\n{log_path()}")
                msg.setDetailedText(tb_text)
                msg.exec()
        except Exception:  # noqa: BLE001
            pass

        _orig(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def install_qt_message_handler() -> None:
    """Forward Qt debug/warning/critical messages into the Python logger."""
    from PyQt6.QtCore import QtMsgType, qInstallMessageHandler

    _qt_log = logging.getLogger("coralX.qt")
    _level_map = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def _handler(msg_type: QtMsgType, context, message: str) -> None:
        level = _level_map.get(msg_type, logging.WARNING)
        loc = f"{context.file or '?'}:{context.line or 0}"
        _qt_log.log(level, "%s  (%s)", message, loc)

    qInstallMessageHandler(_handler)
