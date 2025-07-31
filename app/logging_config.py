# app/logging_config.py
import logging
import sys

logger = logging.getLogger("ledger")
logger.setLevel(logging.INFO)

# Clear any default handlers
logger.handlers.clear()

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)
