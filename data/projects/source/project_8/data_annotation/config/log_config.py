import os
from loguru import logger as loguru_logger


class Logger:
    def __init__(self):
        self.logger = loguru_logger
        self._setup()

    def _setup(self):
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)

        self.logger.remove()

        self.logger.add(
            os.path.join(log_dir, "info_{time:YYYY-MM-DD}.log"),
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            rotation="1 day",
            retention="7 days",
            compression="zip",
            encoding="utf-8"
        )

        self.logger.add(
            os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}",
            rotation="1 day",
            retention="7 days",
            compression="zip",
            encoding="utf-8"
        )

        self.logger.add(
            sink=lambda msg: print(msg),
            level="DEBUG",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
        )

    def debug(self, message: str, *args, **kwargs):
        self.logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self.logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self.logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self.logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self.logger.critical(message, *args, **kwargs)


logger = Logger()
