import os
import sys

try:
    from loguru import logger as _logger

    def setup_logger(log_dir="debug/custom", console_level="INFO"):
        """设置 loguru logger"""
        os.makedirs(log_dir, exist_ok=True)
        _logger.remove()

        def format_level(record):
            level_map = {
                "INFO": "info",
                "ERROR": "err",
                "WARNING": "warn",
                "DEBUG": "debug",
            }
            record["extra"]["level_short"] = level_map.get(
                record["level"].name, record["level"].name.lower()
            )
            return True

        _logger.add(
            sys.stderr,
            format="<level>{extra[level_short]}</level>:<level>{message}</level>",
            colorize=True,
            level=console_level,
            filter=format_level,
        )
        _logger.add(
            f"{log_dir}/{{time:YYYY-MM-DD}}.log",
            rotation="00:00",
            retention="2 weeks",
            compression="zip",
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
            encoding="utf-8",
        )
        return _logger

    logger = setup_logger()

except ImportError:
    import logging

    class ShortLevelFormatter(logging.Formatter):
        level_map = {
            "INFO": "info",
            "ERROR": "err",
            "WARNING": "warn",
            "DEBUG": "debug",
        }

        def format(self, record):
            record.level_short = self.level_map.get(
                record.levelname, record.levelname.lower()
            )
            return super().format(record)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ShortLevelFormatter("%(level_short)s:%(message)s"))
    logging.root.addHandler(handler)
    logging.root.setLevel(logging.INFO)
    logger = logging
