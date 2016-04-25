"""
Common logging setup for Nest WFH.
"""
import logging
import logging.handlers

LOG_FILENAME = '/var/log/nest-wfh/nest-wfh.INFO'


def Log(name):
  """Create a logger for the requesting module.

  Args:
    name: (str) Name of logger.

  Returns:
    Logger object.
  """
  fmt = '%(asctime)-15s %(threadName)s %(filename)s:%(lineno)d %(message)s'
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)
  # Rotate at 1M bytes, store 5 old versions
  handler = logging.handlers.RotatingFileHandler(
      LOG_FILENAME, maxBytes=1>>20, backupCount=5)
  handler.setFormatter(logging.Formatter(fmt))
  logger.addHandler(handler)
  return logger
