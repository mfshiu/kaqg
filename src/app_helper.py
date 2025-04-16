from datetime import datetime
import json
from pathlib import Path
import os
import re
import signal
import time

# for GVFS
import shutil
import subprocess
import platform
import tempfile
from contextlib import contextmanager

# Logging setting
import logging 
from logging.handlers import TimedRotatingFileHandler

LOGGING_LEVEL_VERBOSE = int(logging.DEBUG / 2)
logging.addLevelName(LOGGING_LEVEL_VERBOSE, "VERBOSE")

def verbose(self, message, *args, **kwargs):
    if self.isEnabledFor(LOGGING_LEVEL_VERBOSE):
        self._log(LOGGING_LEVEL_VERBOSE, message, args, **kwargs, stacklevel=2)
logging.Logger.verbose = verbose


_logger:logging.Logger = None
config = {}


def initialize(module_name=None):
    global _logger
    if _logger:
        # _logger.warning(f"Initialized.")
        return
    
    config_path = get_config_path()
    print(f'Config path: {config_path}')
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")

    global config
    print(f"config_path: {config_path}")
    config = __import__('toml').load(config_path)
    
    if module_name:
        log_path = config['logging']['path']
        base_name = os.path.splitext(os.path.basename(log_path))[0]
        config['logging']['path'] = log_path.replace(base_name, f"{base_name}_{module_name}")
        
    _logger = _init_logging(config)    
    _logger.debug(f'Config: {config}')


def _init_logging(config):
    log_name = "wastepro"
    log_path = os.path.join(os.getcwd(), '_log', f'{log_name}.log')
    log_level = logging.DEBUG    

    if cfg := config.get('logging'):
        log_name = cfg.get("name", log_name)
        log_path = cfg.get("path", log_path)
        log_level = get_log_level(cfg.get("level", "DEBUG"))
    
    os.environ['LOGGER_NAME'] = log_name
    config['LOGGER_NAME'] = log_name
    config['LOG_PATH'] = log_path
    config['LOG_LEVEL'] = str(log_level)
    
    Path(os.path.dirname(log_path)).mkdir(parents=True, exist_ok=True)

    # 設定 Formatter
    fmt = '%(levelname)1.1s %(asctime)s.%(msecs)03d %(module)15s:%(lineno)03d %(funcName)15s) %(message)s'
    datefmt = '%m-%d %H:%M:%S'
    console_formatter = ColorFormatter(fmt, datefmt)
    file_formatter = logging.Formatter(fmt, datefmt)

    # File handler
    file_handler = TimedRotatingFileHandler(
        log_path,
        when="d",
        encoding="utf-8",
        backupCount=0,
        delay=True,                 # 延遲寫入，避免程式啟動時就創建檔案
        errors='backslashreplace'   # 防止特殊字元寫入錯誤
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # 設定 logger
    logger = logging.getLogger(log_name)
    logger.handlers.clear()
    logger.propagate = False
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.setLevel(log_level)

    logger.info(f"Log name: {logger.name}, Level: {logger.level}, Path: {log_path}")

    return logger


@contextmanager
def ensure_local_copy(gvfs_path):
    """自動處理 GVFS WebDAV 檔案，確保複製到本地後讀取，並在 with 結束後刪除暫存檔案"""
    is_linux = platform.system() == "Linux"
    # is_windows = platform.system() == "Windows"

    # 取得正確的暫存目錄
    local_tmp_dir = tempfile.gettempdir()
    local_pdf_path = os.path.join(local_tmp_dir, os.path.basename(gvfs_path))

    # Linux: 取得使用者 UID（避免 Windows 執行 os.getuid()）
    gvfs_base_path = f"/run/user/{os.getuid()}/gvfs/" if is_linux else None

    try:
        if is_linux and gvfs_base_path and gvfs_path.startswith(gvfs_base_path):
            # Linux GVFS WebDAV 使用 `gio copy`
            subprocess.run(["gio", "copy", gvfs_path, local_pdf_path], check=True)
        else:
            # Windows 或一般 Linux 檔案使用 `shutil.copy`
            shutil.copy(gvfs_path, local_pdf_path)

        yield local_pdf_path  # `with` 內部使用 local_pdf_path

    finally:
        if os.path.exists(local_pdf_path):
            os.remove(local_pdf_path)


def fix_json_keys(obj):
    if isinstance(obj, dict):
        new_obj = {}
        for key, value in obj.items():
            new_key = re.sub(r'\s+', '_', key)       # replace spaces with underscores
            new_key = new_key[0].lower() + new_key[1:] if new_key else new_key  # lowercase first letter
            new_obj[new_key] = fix_json_keys(value)
        return new_obj
    elif isinstance(obj, list):
        return [fix_json_keys(item) for item in obj]
    else:
        return obj


def fix_json(json_text):
    # Remove Markdown wrapping (if present)
    if json_text.startswith("```json") or json_text.startswith("```"):
        json_text = json_text.strip("`").split('\n', 1)[-1].rsplit('\n', 1)[0]
    
    # Fix internal quotes (escape unescaped quotes inside strings)
    # This regex ensures any double quotes inside strings are escaped
    json_text = re.sub(r'\"([^\"]+)\"', r'\"\\\"\1\\\"\"', json_text)

    # Ensure the JSON text has a valid ending
    last_valid_index = max(json_text.rfind("}"), json_text.rfind("]"))
    json_fixed = json_text[:last_valid_index + 1]

    # Strip any unnecessary whitespace at the beginning or end
    json_fixed = json_fixed.strip()
    
    return json_fixed


def load_json(json_text):
    try:
        # Try to directly load the JSON first
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        # If there's a JSONDecodeError, attempt to fix the JSON string
        _logger.warning(f"JSONDecodeError: {e}. Attempting to fix JSON.")
        fixed_json_text = fix_json(json_text)
        try:
            return json.loads(fixed_json_text)
        except json.JSONDecodeError as e:
            _logger.error(f"Failed to parse fixed JSON: {e}")
            return None  # Returning None if still unable to parse
    except Exception as e:
        # Handle unexpected errors
        _logger.exception(f"Unexpected error: {e}")
        return None
        
    
def get_log_level(level):
    levels = {
        'VERBOSE': LOGGING_LEVEL_VERBOSE,
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
    }
    
    level = levels.get(level, logging.DEBUG)
    return level


def get_config_path():
    # Get path from environment variable or default to current directory
    return os.getenv('WASTEPRO_CONFIG_PATH', os.path.join(os.getcwd(), 'wastepro.toml'))


def get_agent_config():
    global config
    
    broker_name = config['broker']['broker_name']

    agent_config = {
        'version': config['system']['version'],
        'broker': {
            **config['broker'].get(broker_name, {})
        }
    }

    return agent_config


def wait_agent(agent):
    def signal_handler(signal, frame):
        agent.terminate()
    signal.signal(signal.SIGINT, signal_handler)

    time.sleep(1)
    dot_counter = 0
    minute_tracker = datetime.now().minute

    while agent.is_active():
        time.sleep(1)

        dot_counter += 1
        if dot_counter % 6 == 0:
            print('.', end='', flush=True)

        current_minute = datetime.now().minute
        if current_minute != minute_tracker:
            print(f"{datetime.now().strftime('%H:%M')}", end='', flush=True)
            minute_tracker = current_minute
    print()



from colorama import init, Fore, Style

init(autoreset=True)    # Initialize colorama for Windows

class ColorFormatter(logging.Formatter):
    LEVEL_COLORS = {
        'E': Fore.RED,
        'W': Fore.YELLOW,
        'I': Fore.CYAN,
        'D': Fore.WHITE,
        'V': Fore.LIGHTBLACK_EX
    }

    def format(self, record):
        level_char = record.levelname[0]  # Get first letter of log level
        color = self.LEVEL_COLORS.get(level_char, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"


def check_directory_accessible(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path '{path}' does not exist.")
    if not os.path.isdir(path):
        raise NotADirectoryError(f"Path '{path}' is not a directory.")
    if not os.access(path, os.R_OK):
        raise PermissionError(f"Path '{path}' is not readable.")