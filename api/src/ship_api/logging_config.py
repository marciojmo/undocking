import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configures root logging for the application.

    Args:
        level: Minimum level to emit. Defaults to ``logging.INFO``.
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
