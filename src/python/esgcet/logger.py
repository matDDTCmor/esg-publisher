import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

_file_handler_installed = False


def add_file_handler(path):
    """Mirror all logging (from every ESGPubLogger-named logger) into a
    file, in addition to the existing console StreamHandler.

    Attached to the root logger: every named logger created via
    return_logger() propagates to root by default, so this is a single
    process-wide hook rather than something each of the ~30 call sites
    needs to repeat. Safe to call more than once -- only the first call
    installs the handler.
    """
    global _file_handler_installed
    if _file_handler_installed:
        return
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT))
    root = logging.getLogger()
    root.addHandler(handler)
    # Root's own level defaults to WARNING; each named logger already
    # enforces its own silent/verbose level before a record is emitted,
    # so this only needs to not filter anything out again on the way
    # through the root handler.
    root.setLevel(logging.DEBUG)
    _file_handler_installed = True


class ESGPubLogger:
    """
    Logger wrapper class
    """
    def __init__(self):
        """ Constructor
        """
        self._log = None


    def return_logger(self, name, silent=False, verbose=False):
        """
        Logger 'factory' method allows for the naming and level specification.
        """
        if self._log:
            return self._log
        
        publog = logging.getLogger(name)
        if silent:
            publog.setLevel(logging.WARNING)
        elif verbose:
            publog.setLevel(logging.DEBUG)
        else:
            publog.setLevel(logging.INFO)
        formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATEFMT)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        publog.addHandler(handler)
        self._log = publog
        return publog
