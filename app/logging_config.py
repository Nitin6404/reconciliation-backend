import logging
from pathlib import Path

LOG_FILE = Path(__file__).parent / "app.log"

logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
