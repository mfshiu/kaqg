import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import agentflow


LOGGING_LEVEL = logging.DEBUG
LOGGING_LEVEL = agentflow.LOGGING_LEVEL_VERBOSE


# 初始化 logging，設置格式和 handler
def _init_logging(logger, log_path: str, log_level):
    # 檔案夾生成
    Path(os.path.dirname(log_path)).mkdir(parents=True, exist_ok=True)

    # 設定 Formatter
    formatter = logging.Formatter(
        '%(levelname)1.1s %(asctime)s.%(msecs)03d %(module)15s:%(lineno)03d %(funcName)15s) %(message)s',
        datefmt='%H:%M:%S')

    # File handler
    file_handler = TimedRotatingFileHandler(log_path, when="d")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # 避免重複添加 handler
    if not logger.hasHandlers():
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    logger.setLevel(log_level)

    return logger


logger_name = os.getenv("LOGGER_NAME", agentflow.LOGGER_NAME)
__logger = _init_logging(logging.getLogger(logger_name), 
                         f'./_log/{logger_name}.log', 
                         LOGGING_LEVEL)
__logger.info(f"Logger initialized, name: {__logger.name}")


def get_logger():
    return __logger
