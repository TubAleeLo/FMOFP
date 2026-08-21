import os
import sys
import xml.etree.ElementTree as ET
from typing import Dict
import Utils.common.fetching as fetching
from Utils.common.thread_manager import thread_manager
from FMOFP.MIL_STD_1553B.Bus_Controller.BC import Bus_Controller
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import Remote_Terminal
from storage.DBM import DatabaseManager
from Utils.logger.sys_logger import get_logger
from Utils.common.system_state_manager import SystemStateManager
from Utils.common.system_states import SystemState
from Utils.debug.userCLI import get_user_cli

class startup:
    def __init__(self):
        self.logger = get_logger().logger
        self.logger.info("Initializing base startup")
        self.bc = Bus_Controller()
        self.logger.info("Bus Controller initialized")
        self.rt = Remote_Terminal()
        self.logger.info("Remote Terminal initialized")
        self.state_manager = SystemStateManager()
        self.monitoring = None
        self.initialize_database_components()

    def initialize_database_components(self):
        try:
            if self.state_manager.system_state_node:
                state = self.state_manager.get_state()
                self.intitialized = True

                return
            else:
                self.state_manager.set_state(SystemState.INITIALIZING)
                self.logger.info("Database components already initialized with INITIALIZING state")

            self.logger.info("Starting database components initialization")
            schema_path = os.path.join(fetching.fetch_fmofp_path(), 'storage', 'databases', 'schema.xml')
            db_config_path = os.path.join(fetching.fetch_fmofp_path(), 'dbConfig.xml')
            
            self.logger.info(f"Initializing DatabaseManager with config path: {db_config_path}")
            db_manager = DatabaseManager(db_config_path)
            self.logger.info("DatabaseManager initialized successfully")
            
            self.logger.info(f"Initializing SchemaManager with schema path: {schema_path}")
            # NOTE (production readiness re-analysis, August 2026): `SchemaManager`
            # is referenced here but does not exist anywhere in this codebase --
            # never implemented, never imported. Found via
            # `ruff check --select F821` (undefined-name). Confirmed via a
            # repo-wide search that this whole `startup` class (this file,
            # core/baseStartUp.py) is dead code: nothing anywhere imports
            # `core.baseStartUp` or calls `startup()` -- the live boot path is
            # SystemStart.py -> core/system_manager.py, which handles database
            # initialization itself via DatabaseManager directly, without a
            # separate schema-management step. Not fixed: fabricating a
            # SchemaManager implementation with no real specification (what
            # schema.xml format it should read, how it should reconcile with
            # DatabaseManager's own table-creation calls) would be a guess, not
            # a bug fix, and this code path is not reachable today regardless.
            # Documented rather than invented; see PLANNING.md.
            self.schema_manager = SchemaManager(db_manager, schema_path)  # noqa: F821 -- see NOTE above; dead code, deliberately left undefined
            self.logger.info(f"SchemaManager initialized: {self.schema_manager}")
            
            if not self.schema_manager.schema:
                self.logger.error("Failed to load database schema")
                raise ValueError("Failed to load database schema")
            
            self.logger.info("Starting to ensure database schema")
            self.schema_manager.ensure_schema()
            self.logger.info("Database schema ensured successfully")
            
            # Log information about all initialized systems
            for system_name in db_manager.systems.keys():
                self.logger.info(f"System '{system_name}' initialized with database")
                tables = db_manager.get_system_db(system_name).list_tables()
                self.logger.info(f"Tables in '{system_name}' database: {tables}")
                for table in tables:
                    columns = db_manager.get_system_db(system_name).execute_query(f"PRAGMA table_info({table})")
                    self.logger.info(f"Columns in '{system_name}.{table}': {[col[1] for col in columns]}")
            
            self.logger.info("Database components initialization completed successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database components: {e}", exc_info=True)
            raise

    def commandInterface_config(self, config_path: str) -> Dict[str, Dict[str, int]]:
        """
        Load command interface configuration from an XML file.
        """
        self.logger.info(f"Loading command interface configuration from {config_path}")
        commandInterface = ""
        try:
            root = ET.parse(config_path).getroot()
            for rate_config in root.findall('logging'):
                commandInterface = rate_config.find('commandInterface').text
            self.logger.info(f"Command interface configuration loaded: {commandInterface}")
        except Exception as e:
            self.logger.error(f"Error loading command interface configuration from '{config_path}': {e}", exc_info=True)
        return commandInterface

    def initialize_user_cli_threads(self):
        self.state_manager = SystemStateManager()
        state = self.state_manager.get_state()
        if state in [SystemState.INITIALIZED, SystemState.RUNNING, SystemState.NORMAL]:
            self.logger.info("User CLI threads already initialized. Skipping initialization")
            return
        self.logger.info("Initializing user CLI threads")
        startup_config_path = os.path.join(fetching.fetch_fmofp_path(), 'startupConfiguration.xml')
        commandInterface = self.commandInterface_config(startup_config_path)
        if commandInterface:
            self.logger.info("Getting UserCLI instance")
            try:
                ucli = get_user_cli()
                self.logger.info("UserCLI instance retrieved successfully")
            except Exception as e:
                self.logger.error(f"Error getting UserCLI instance: {e}", exc_info=True)
                return

            self.logger.info("Adding UserCLI threads to thread manager")
            try:
                thread_manager.add_thread("UserCLI Control", target=ucli.commandLineThreadControl)
                thread_manager.add_thread("UserCLI Input", target=ucli.get_commands)
                thread_manager.add_thread("UserCLI Processing", target=ucli.process_commands)
                thread_manager.add_thread("UserCLI Output", target=ucli.output_commands)
                self.logger.info("UserCLI threads added to thread manager")
            except Exception as e:
                self.logger.error(f"Error adding UserCLI threads to thread manager: {e}", exc_info=True)
                return

            self.logger.info("Starting UserCLI threads")
            try:
                for thread_name in ["UserCLI Control", "UserCLI Input", "UserCLI Processing", "UserCLI Output"]:
                    status = thread_manager.get_thread_status(thread_name)
                    self.logger.info(f"Status before starting: {status}")
                    if "not running" in status:
                        success = thread_manager.start_thread(thread_name)
                        if success:
                            self.logger.info(f"Thread '{thread_name}' started successfully")
                        else:
                            self.logger.warning(f"Failed to start thread '{thread_name}'")
                    else:
                        
                        pass
                self.logger.info("UserCLI threads started successfully")
            except Exception as e:
                self.logger.error(f"Error starting UserCLI threads: {e}", exc_info=True)
        else:
            self.logger.info("Command interface not configured, skipping user CLI thread initialization")


    def start_thread_if_not_running(self, thread_name):
        status = thread_manager.get_thread_status(thread_name)
        self.logger.info(f"Status before starting: {status}")
        if "not running" in status:
            success = thread_manager.start_thread(thread_name)
            if success:
                self.logger.info(f"Thread '{thread_name}' started successfully")
            else:
                self.logger.warning(f"Failed to start thread '{thread_name}'")
        else:
           
            pass
