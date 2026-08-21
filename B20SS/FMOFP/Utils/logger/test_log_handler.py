import os
import re
import logging
from datetime import datetime

class TestLogHandler(logging.Handler):
    """
    A logging handler that detects test execution and redirects logs to a separate file.
    This handler watches for specific test start patterns and creates a new log file
    when a test begins running.
    """
    def __init__(self, base_path, level=logging.DEBUG):
        super().__init__(level)
        self.base_path = base_path
        self.logs_dir = os.path.join(base_path, 'logs')
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.test_file_handler = None
        self.startup_file_handler = None
        self.in_test_mode = False
        self.current_test_name = None
        
    def detect_test_start(self, record):
        """Detects if a log message indicates a test is starting"""
        msg = record.getMessage()
        # Pattern to match test start messages
        test_start_patterns = [
            r"==== TEST START: (.*?) ====",
            r"Starting (.*?) test\.\.\.",
            r"=== Step 1: .*? ===",
            r"\[TEST POINT\]",
            r"Running (.*?) test\.\.\."
        ]
        
        for pattern in test_start_patterns:
            match = re.search(pattern, msg)
            if match:
                # Extract test name if available
                test_name = match.group(1) if len(match.groups()) > 0 else "unknown"
                return True, test_name
        return False, None
        
    def setup_test_file(self, test_name):
        """Creates a new test log file when a test starts"""
        if self.test_file_handler:
            self.test_file_handler.close()
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_test_name = re.sub(r'[^\w]', '_', test_name).lower()
        test_log_file = os.path.join(self.logs_dir, f'TEST_{safe_test_name}_{timestamp}.log')
        
        # encoding='utf-8' added (Round 17, encoding/non-ASCII sweep) --
        # see sys_logger.py's RotatingFileHandler fix for the full
        # writeup; same gap, same fix, for consistency across every
        # log file this app writes.
        self.test_file_handler = logging.FileHandler(test_log_file, encoding='utf-8')
        self.test_file_handler.setLevel(logging.DEBUG)
        self.test_file_handler.setFormatter(self.formatter)
        self.current_test_name = test_name
        
        # Log the test start marker to the test log
        startup_msg = f"==== TEST STARTED: {test_name} at {timestamp} ====\n"
        self.test_file_handler.stream.write(startup_msg)
        self.test_file_handler.flush()
        
        return test_log_file
        
    def setup_startup_file(self):
        """Creates a startup log file if not already created"""
        if not self.startup_file_handler:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            startup_log_file = os.path.join(self.logs_dir, f'STARTUP_{timestamp}.log')
            
            self.startup_file_handler = logging.FileHandler(startup_log_file, encoding='utf-8')
            self.startup_file_handler.setLevel(logging.DEBUG)
            self.startup_file_handler.setFormatter(self.formatter)
            
            # Copy any existing log content to the startup file
            try:
                # Find most recent DEBUG log
                debug_logs = [f for f in os.listdir(self.logs_dir) if f.startswith('DEBUG_')]
                if debug_logs:
                    latest_log = max(debug_logs)
                    with open(os.path.join(self.logs_dir, latest_log), 'r', encoding='utf-8') as src:
                        startup_content = src.read()
                        self.startup_file_handler.stream.write(startup_content)
                        self.startup_file_handler.flush()
            except Exception as e:
                print(f"Error copying existing logs: {e}")
                
            return startup_log_file
        return None
        
    def emit(self, record):
        """Process and route log records to the appropriate file"""
        # Check if this record indicates the start of a test
        is_test_start, test_name = self.detect_test_start(record)
        
        if is_test_start and not self.in_test_mode:
            # First test is starting - set up startup file with existing logs
            startup_file = self.setup_startup_file()
            if startup_file:
                print(f"Created startup log file: {startup_file}")
                
            # Set up test file
            test_file = self.setup_test_file(test_name)
            print(f"Created test log file: {test_file}")
            self.in_test_mode = True
        elif is_test_start and self.in_test_mode and test_name != self.current_test_name:
            # New test starting while another test is running
            test_file = self.setup_test_file(test_name)
            print(f"Created new test log file: {test_file}")
        
        # Route the record to the appropriate handler
        if self.in_test_mode and self.test_file_handler:
            self.test_file_handler.emit(record)
        elif self.startup_file_handler:
            self.startup_file_handler.emit(record)
