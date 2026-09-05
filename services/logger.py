import logging
import os
#create the paths for log
LOG_DIR = "logs"
LOG_PATH = os.path.join(LOG_DIR,"app.log")
os.makedirs(LOG_DIR,exist_ok=True)
logger = logging.getLogger("AgriSubsidyAI")
logger.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | %(message)s "

)

file_handler = logging.FileHandler(
    LOG_PATH,
    encoding='utf-8'
)

file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)