import os
import sys
import time
import threading
from queue import Queue
import concurrent.futures
import xml.etree.ElementTree as ET
import Utils.common.fetching as fetching
from core.system_manager import get_system_manager
from Utils.common.thread_manager import ThreadManager
from Utils.logger.sys_logger import SysLogger
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()
sys_logger = logger

class ApplicationController:
    def __init__(self):
        self.system_manager = get_system_manager()
        self.thread_manager = self.system_manager.thread_manager
        self.node = self.system_manager.node
        self.db = self.system_manager.db
        self.db_lock = threading.Lock()
        self.command_processed = threading.Event()
        self.debugging = self.load_debugging_config()
        self.commandInterface = self.load_command_interface()
        self.stop_threads = False
        self.init_threads()

    def load_logging_level_config(self):
        try:
            tree = ET.parse('startupConfigurations.xml')
            root = tree.getroot()
            command_interface_element = root.find('./logging/level')
            if command_interface_element is not None:
                return command_interface_element.text.lower() == 'true'
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
        except FileNotFoundError:
            logger.error("startupConfigurations.xml file not found")
        return False

    def load_logging_config(self):
        try:
            tree = ET.parse('FMOFP/startupConfiguration.xml')
            root = tree.getroot()
            command_interface_element = root.find('./logging/logging_enabled')
            if command_interface_element is not None:
                return command_interface_element.text.lower() == 'true'
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
        except FileNotFoundError:
            logger.error("startupConfigurations.xml file not found")
        return False

    def load_debugging_config(self):
        try:
            tree = ET.parse('FMOFP/startupConfiguration.xml')
            root = tree.getroot()
            command_interface_element = root.find('./logging/debugging')
            if command_interface_element is not None:
                return command_interface_element.text.lower() == 'true'
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
        except FileNotFoundError:
            logger.error("startupConfigurations.xml file not found")
        return False

    def load_command_interface(self):
        try:
            tree = ET.parse('FMOFP/startupConfiguration.xml')
            root = tree.getroot()
            command_interface_element = root.find('./logging/commandInterface')
            if command_interface_element is not None:
                return command_interface_element.text.lower() == 'true'
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
        except FileNotFoundError:
            logger.error("FMOFP/startupConfiguration.xml file not found")
        return False

    def init_threads(self):
        self.system_manager.initialize_threads()
        self.thread_manager.add_thread("Queue Processor", self.process_queue)
        self.thread_manager.add_thread("Thread Status Checker", self._check_thread_status)

    def start(self):
        try:
            self.system_manager.start()
            sys_logger.setup_logger()
        except Exception as e:
            logger.error(f"Error starting threads: {e}")

    def process_queue(self):
        last_processed = {
            'status_msg': 0,
            'alert_msg': 0,
            'data_msg': 0,
            'command_msg': 0,
            'log_msg': 0
        }

        rate_config = {
            'status_msg': 1,
            'alert_msg': 5,
            'data_msg': 10,
            'command_msg': 2,
            'log_msg': 0.5
        }

        while not self.node.get_flag('stop_threads'):
            current_time = time.time()
            for msg_type, rate in rate_config.items():
                if current_time - last_processed[msg_type] >= 1 / rate:
                    self.process_message(msg_type)
                    last_processed[msg_type] = current_time
            time.sleep(0.01)

    def process_message(self, msg_type):
        logger.debug(f"Processing message of type: {msg_type}")
        # Add your message processing logic here

    def _check_thread_status(self):
        self.thread_status = {name: "Running" for name in self.thread_manager.threads.keys()}
        self._initialize_thread_status_table()

        while not self.stop_threads:
            for thread_name, status in self.thread_status.items():
                existing_thread = self.db.read_table('thread_status', fields=['thread_name'], condition={'thread_name': thread_name})

                if existing_thread:
                    with self.db_lock:
                        self.db.update_table('thread_status', {'status': status}, {'thread_name': thread_name})
                else:
                    with self.db_lock:
                        self.db.insert_into_table('thread_status', {'thread_name': thread_name, 'status': status})

            self.check_stop_flag()

    def check_stop_flag(self):
        stop_threads = self.node.get_flag('stop_threads')
        if stop_threads:
            logger.info("Stop flag set, stopping threads...")
            self.stop()

    def _initialize_thread_status_table(self):
        table_name = 'thread_status'
        field_data_dict = {'thread_name': 'TEXT', 'status': 'TEXT'}

        try:
            table_exists = self.db.table_exists(table_name)
            if not table_exists:
                self.db.create_table(table_name, field_data_dict)
                logger.info(f"Created {table_name} table")
            else:
                columns = self.db.execute_query(f"PRAGMA table_info('{table_name}');")
                column_names = {col[1]: col[5] for col in columns}

                if 'thread_name' not in column_names or not column_names['thread_name']:
                    logger.debug(f"Adding PRIMARY KEY constraint to 'thread_name' column in {table_name} table")
                    old_table_name = f"{table_name}_old"

                    old_table_exists = self.db.table_exists(old_table_name)
                    if old_table_exists:
                        logger.debug(f"Dropping old table: {old_table_name}")
                        self.db.execute_query(f"DROP TABLE {old_table_name}")

                        old_table_exists = self.db.table_exists(old_table_name)
                        if old_table_exists:
                            logger.error(f"Error dropping old table: {old_table_name}")
                        else:
                            logger.debug(f"Old table dropped: {old_table_name}")

                    self.db.execute_query(f"ALTER TABLE {table_name} RENAME TO {old_table_name}")
                    self.db.create_table(table_name, field_data_dict)

                    new_table_columns = self.db.execute_query(f"PRAGMA table_info('{table_name}');")
                    new_column_names = {col[1]: col[5] for col in new_table_columns}

                    if 'thread_name' in new_column_names and new_column_names['thread_name']:
                        self.db.execute_query(f"INSERT INTO {table_name} (thread_name, status) SELECT thread_name, status FROM {old_table_name}")
                        self.db.execute_query(f"DROP TABLE {old_table_name}")
                        logger.info(f"Added PRIMARY KEY constraint to 'thread_name' column in {table_name} table")
                    else:
                        logger.error(f"Error adding PRIMARY KEY constraint to 'thread_name' column in {table_name} table")
                else:
                    logger.debug(f"'thread_name' column already has the PRIMARY KEY constraint in {table_name} table")
                    
                self.stop_threads = False
                
        except Exception as e:
            logger.error(f"Error initializing {table_name} table: {e}", exc_info=True)

    def load_config(self):
        if self.db:
            self.db.close_connection()

class Threads(ApplicationController):
    def __init__(self):
        super().__init__()

    def start(self):
        super().start()

if __name__ == "__main__":
    threads = Threads()
    threads.start()