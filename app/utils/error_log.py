"""Records errors in a log file.

The packaged app has no console, so without this a traceback goes nowhere. Only
the traceback is written, never field values, so passwords cannot reach the log.
"""
import logging
import threading
from logging.handlers import RotatingFileHandler

from app.config import LOG_PATH

LOGGER_NAME = "scryfall"
MAX_LOG_BYTES = 1_000_000  # one old file is kept, so the log cannot grow forever


# a log that cannot be opened must never stop the app from starting, so this
# gives up quietly and errors are then just not recorded
def setup_logging(path=LOG_PATH):
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    close_logging()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # delay leaves the file uncreated until there is something to record
        handler = RotatingFileHandler(path, maxBytes=MAX_LOG_BYTES, backupCount=1,
                                      encoding="utf-8", delay=True)
    except OSError:
        logger.addHandler(logging.NullHandler())
        return
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)


def close_logging():
    logger = logging.getLogger(LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def log_error(message, error):
    logging.getLogger(LOGGER_NAME).error(
        message, exc_info=(type(error), error, error.__traceback__))


# tk's error handler only sees the main thread, so anything a background thread
# leaves uncaught comes here. it can only be logged: threads must not touch tk
def log_thread_errors():
    def on_thread_error(args):
        if args.exc_value is not None:
            log_error(f"Unhandled error on thread {args.thread.name}", args.exc_value)

    threading.excepthook = on_thread_error
