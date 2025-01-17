from pathlib import Path
import os

# Logging setting
import logging 
from logging import Logger
from logging.handlers import TimedRotatingFileHandler

LOGGING_LEVEL_VERBOSE = int(logging.DEBUG / 2)
logging.addLevelName(LOGGING_LEVEL_VERBOSE, "VERBOSE")

def verbose(self, message, *args, **kwargs):
    if self.isEnabledFor(LOGGING_LEVEL_VERBOSE):
        self._log(LOGGING_LEVEL_VERBOSE, message, args, **kwargs, stacklevel=2)
logging.Logger.verbose = verbose


config = {}


def initialize():
    config_path = get_config_path()
    print(f'Config path: {config_path}')
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    
    global config
    config = __import__('toml').load(config_path)
    logger:Logger = _init_logging(config)    
    logger.debug(f'Config: {config}')


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
    file_handler = TimedRotatingFileHandler(log_path, when="d")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # 避免重複添加 handler
    logger = logging.getLogger(log_name)
    logger.handlers.clear()
    logger.propagate = False    # 避免被加入 default handler
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.setLevel(log_level)

    logger.info(f"Log name: {logger.name}, level: {logger.level}, path: {log_path}")

    return logger
    
    
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
