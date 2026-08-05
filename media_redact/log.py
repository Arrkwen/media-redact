"""loguru 日志配置。"""

from __future__ import annotations

import sys

from loguru import logger

DEFAULT_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{extra[component]}</cyan> - "
    "<level>{message}</level>"
)

_configured = False


def setup_logging(level: str = "INFO", *, component: str = "media-redact") -> None:
    """配置 stderr 日志输出。"""
    global _configured
    logger.remove()
    logger.configure(extra={"component": component})
    logger.add(
        sys.stderr,
        level=level.upper(),
        format=DEFAULT_FORMAT,
        colorize=True,
    )
    _configured = True


def ensure_logging(level: str = "INFO", *, component: str = "media-redact") -> None:
    """API 调用时若尚未配置，则使用默认日志级别。"""
    if not _configured:
        setup_logging(level, component=component)


class PrintfLogger:
    """兼容 ``logger.info("x %s", value)`` 写法。"""

    def debug(self, message: str, *args) -> None:
        logger.debug(message % args if args else message)

    def info(self, message: str, *args) -> None:
        logger.info(message % args if args else message)

    def warning(self, message: str, *args) -> None:
        logger.warning(message % args if args else message)

    def error(self, message: str, *args) -> None:
        logger.error(message % args if args else message)


__all__ = ["logger", "setup_logging", "ensure_logging", "PrintfLogger"]
