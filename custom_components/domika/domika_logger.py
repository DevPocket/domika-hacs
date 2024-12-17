import logging
from .const import DOMIKA_LOG_LEVEL

DOMIKA_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,     # default
    'VERBOSE': 9,               # log main actions and calls
    'TRACE': 8,                 # also log all Domika actions, HA events, some parameters
    'FINE': 7,                  # also log all parameters
    'FINER': 6,                 # also enable logs showing interim states
    'FINEST': 5                 # super-detailed
}


class DomikaLogger:
    _logger = logging.getLogger(__package__)

    def __init__(self, log_level):
        self.LOG_LEVEL = log_level if log_level else 'DEBUG'

    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)

    def fatal(self, msg, *args, **kwargs):
        self._logger.fatal(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self._logger.log(level, msg, *args, **kwargs)

    def verbose(self, msg, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG) and DOMIKA_LOG_LEVELS['VERBOSE'] >= DOMIKA_LOG_LEVELS[self.LOG_LEVEL]:
            self._logger.debug(msg, *args, **kwargs)

    def trace(self, msg, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG) and DOMIKA_LOG_LEVELS['TRACE'] >= DOMIKA_LOG_LEVELS[self.LOG_LEVEL]:
            self._logger.debug(msg, *args, **kwargs)

    def fine(self, msg, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG) and DOMIKA_LOG_LEVELS['FINE'] >= DOMIKA_LOG_LEVELS[self.LOG_LEVEL]:
            self._logger.debug(msg, *args, **kwargs)

    def finer(self, msg, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG) and DOMIKA_LOG_LEVELS['FINER'] >= DOMIKA_LOG_LEVELS[self.LOG_LEVEL]:
            self._logger.debug(msg, *args, **kwargs)

    def finest(self, msg, *args, **kwargs):
        if self._logger.isEnabledFor(logging.DEBUG) and DOMIKA_LOG_LEVELS['FINEST'] >= DOMIKA_LOG_LEVELS[self.LOG_LEVEL]:
            self._logger.debug(msg, *args, **kwargs)


LOGGER = DomikaLogger(DOMIKA_LOG_LEVEL)
