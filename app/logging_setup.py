import logging

from app import config


def configure_logging() -> None:
    """Shared by the web app (on startup) and cli.py, so both write to the
    same download_log.txt/stdout format the original script used."""
    config.ensure_data_dirs()
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (e.g. --reload re-import)
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s")

    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)
