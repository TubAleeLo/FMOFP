import logging
import logging.handlers
import sys
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from FMOFP.Utils.common.fetching import fetch_fmofp_path
from FMOFP.Utils.logger.test_log_handler import TestLogHandler

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class BaseLogFilter(logging.Filter):
    def filter(self, record):
        raise NotImplementedError("Subclasses should implement this method")

class KeywordFilter(BaseLogFilter):
    def __init__(self, keyword):
        self.keyword = keyword

    def filter(self, record):
        # Changed to return True for all messages since we want to allow everything
        # and only use keywords for additional tracking
        return True

class LevelFilter(BaseLogFilter):
    def __init__(self, level):
        self.level = level

    def filter(self, record):
        # Changed to return True for all messages since we handle levels through handler levels
        return True

class SysLogger(metaclass=Singleton):
    _initialized = False
    
    def __init__(self):
        if SysLogger._initialized:
            return
            
        # Configure root logger first
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(logging.DEBUG)  # Always set to lowest level
        
        # Create system and command loggers
        self.logger = logging.getLogger('system')
        self.command_logger = logging.getLogger('command')
        
        # Ensure loggers propagate to root
        self.logger.propagate = True
        self.command_logger.propagate = True
        
        # Load configuration
        self.filters = []
        self.load_config()
        self.load_filters()
        
        # Set up proper logging
        self.setup_logging()
        SysLogger._initialized = True
        
    def load_config(self):
        try:
            config_path = os.path.join(fetch_fmofp_path(), 'startupConfiguration.xml')
            tree = ET.parse(config_path)
            root = tree.getroot()
            logging_config = root.find('logging')
            if logging_config is not None:
                command_interface_elem = logging_config.find('commandInterface')
                logging_enabled_elem = logging_config.find('logging_enabled')
                debugging_elem = logging_config.find('debugging')
                level_elem = logging_config.find('level')
                console_output_elem = logging_config.find('console_output')

                self.commandInterface = command_interface_elem is not None and command_interface_elem.text.lower() == 'true'
                self.logging_enabled = logging_enabled_elem is not None and logging_enabled_elem.text.lower() == 'true'
                self.debugging = debugging_elem is not None and debugging_elem.text.lower() == 'true'
                self.level = level_elem.text.lower() if level_elem is not None and level_elem.text else 'info'
                self.console_output = console_output_elem is not None and console_output_elem.text.lower() == 'true'
                
                # Convert level string to logging level
                level_map = {
                    'debug': logging.DEBUG,
                    'info': logging.INFO,
                    'warning': logging.WARNING,
                    'error': logging.ERROR,
                    'critical': logging.CRITICAL
                }
                self.log_level = level_map.get(self.level, logging.DEBUG)
                
                # Log configuration using root logger directly
                self.root_logger.info("Logging configuration loaded:")
                self.root_logger.info(f"  commandInterface: {self.commandInterface}")
                self.root_logger.info(f"  logging_enabled: {self.logging_enabled}")
                self.root_logger.info(f"  debugging: {self.debugging}")
                self.root_logger.info(f"  level: {self.level}")
                self.root_logger.info(f"  console_output: {self.console_output}")
        except Exception as e:
            print(f"Error loading logging configuration: {e}")
            self.commandInterface = False
            self.logging_enabled = True  # Changed to True by default
            self.debugging = True  # Changed to True by default
            self.level = 'debug'  # Changed to debug by default
            self.console_output = True  # Changed to True by default
            self.log_level = logging.DEBUG

    def load_filters(self):
        try:
            filters_path = os.path.join(fetch_fmofp_path(), 'Utils', 'logger', 'filtersConfiguration.xml')
            tree = ET.parse(filters_path)
            root = tree.getroot()
            
            # Clear existing filters
            self.filters = []
            
            # We're not using filters anymore since we handle levels through handlers
            pass
            
        except Exception as e:
            self.root_logger.error(f"Error loading filters configuration: {e}")

    def ensure_logs_directory(self):
        """Create logs directory if it doesn't exist"""
        logs_dir = os.path.join(fetch_fmofp_path(), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        return logs_dir

    def cleanup_old_logs(self):
        """Remove all existing log files"""
        logs_dir = os.path.join(fetch_fmofp_path(), 'logs')
        if os.path.exists(logs_dir):
            for file in os.listdir(logs_dir):
                if file.endswith('.log'):
                    try:
                        os.remove(os.path.join(logs_dir, file))
                    except Exception as e:
                        print(f"Error removing old log file {file}: {e}")

    def setup_logging(self):
        if self.logging_enabled:
            # Remove all existing handlers
            self.root_logger.handlers.clear()
            self.logger.handlers.clear()
            self.command_logger.handlers.clear()

            # Clean up all old log files before creating new one
            self.cleanup_old_logs()

            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

            # Set up file logging
            logs_dir = self.ensure_logs_directory()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(logs_dir, f'{self.level.upper()}_{timestamp}.log')
            
            # Create file handler with DEBUG level to capture all messages
            # NOTE (production readiness re-analysis, August 2026): this was a
            # plain logging.FileHandler with no size cap or rotation -- at the
            # default DEBUG level (startupConfiguration.xml's <level>) this file
            # grows without bound for the entire lifetime of the process. Measured
            # live: a single ~25s boot+shutdown test produced a 508KB / 4767-line
            # log file, which extrapolates to hundreds of MB over a multi-hour
            # training session with no cap -- a real disk-filling risk for a
            # simulator meant to run for extended periods. Switched to
            # RotatingFileHandler (50MB per file, 5 backups = 250MB worst case per
            # session) -- identical behavior for short/typical runs (well under
            # 50MB), bounded worst case for long-running ones. Log content,
            # location, naming, and cleanup_old_logs() behavior are unchanged.
            # encoding='utf-8' added (August 2026 re-analysis round, Round
            # 17, encoding/non-ASCII sweep): without an explicit encoding,
            # FileHandler/RotatingFileHandler fall back to the platform's
            # locale-preferred encoding, which on Windows (a supported
            # deployment target -- see install.py's platform.system()
            # branch) is typically a restrictive single-byte codepage like
            # cp1252, not UTF-8. This codebase's own log messages already
            # contain non-ASCII characters in live, routinely-executed
            # lines (e.g. missionControl.py's `f"... {target_id} -> ..."`,
            # written with a literal U+2192 arrow, not "->"). Live-
            # reproduced: logging such a line through a cp1252-encoded
            # handler raises UnicodeEncodeError inside logging's own
            # emit() -- caught internally by logging's handleError(), so
            # it doesn't crash the caller, but the log line is silently
            # dropped entirely (0 bytes written) and a "--- Logging
            # error ---" traceback is printed to stderr every single time,
            # which would repeat continuously on Windows for any of the
            # ~20 files in this codebase using non-ASCII log characters --
            # a real loss of exactly the log data this session's entire
            # verification methodology depends on. UTF-8 can represent
            # every character these log messages use and is a no-op
            # behavior change on Linux/macOS (already the typical default
            # there).
            file_handler = logging.handlers.RotatingFileHandler(
                log_file, maxBytes=50 * 1024 * 1024, backupCount=5, encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # Capture all messages in file
            file_handler.setFormatter(formatter)
            
            # Add file handler to root logger
            self.root_logger.addHandler(file_handler)
            
            # Create and add TestLogHandler to root logger
            test_log_handler = TestLogHandler(fetch_fmofp_path())
            test_log_handler.setLevel(logging.DEBUG)
            self.root_logger.addHandler(test_log_handler)

            # Set up console logging if enabled
            if self.console_output:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(self.log_level)  # Use configured level for console
                console_handler.setFormatter(formatter)
                
                # Add console handler to root logger
                self.root_logger.addHandler(console_handler)

            # Set levels for all loggers
            self.root_logger.setLevel(logging.DEBUG)  # Root logger captures everything
            self.logger.setLevel(self.log_level)      # System logger uses configured level
            self.command_logger.setLevel(self.log_level)  # Command logger uses configured level

            # Log initialization using logger instead of print
            self.root_logger.info(f"Logging system initialized - Writing to {log_file}")
        else:
            self.root_logger.addHandler(logging.NullHandler())

    def add_filter(self, log_filter):
        if isinstance(log_filter, BaseLogFilter):
            self.filters.append(log_filter)
        else:
            raise TypeError("Filter must be an instance of BaseLogFilter")

    # Expose logging functionality through root logger
    def debug(self, msg, *args, **kwargs):
        self.root_logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):

        self.root_logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.root_logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.root_logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.root_logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        self.root_logger.exception(msg, *args, exc_info=exc_info, **kwargs)

# Singleton logger instance
_logger_instance = None

def get_logger():
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = SysLogger()
    return _logger_instance
