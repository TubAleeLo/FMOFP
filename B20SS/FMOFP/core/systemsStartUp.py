import traceback
import asyncio
import FMOFP.Utils.common.fetching as fetching
from FMOFP.Utils.common.thread_manager import ThreadManager, registered_threads
from Systems.radarManagement.radarControl import get_radar_management_system
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Interfaces.userInterface.managers.display_manager import get_display_manager
from FMOFP.Interfaces.userInterface.displays.display_nodes.display_tree_manager import get_display_tree_manager
from FMOFP.local_messaging.routing.response_services.system_response_services.DisplayResponseService import get_display_response_service
from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
logger = get_logger()

class systemsStartup:
    # Class-level locks for thread safety
    _radar_lock = asyncio.Lock()
    _displays_lock = asyncio.Lock()
    
    def __init__(self):
        logger.info("Initializing systems startup")
        self.thread_manager = ThreadManager()
        logger.info("Thread Manager initialized")
        registered_threads.register_known_threads(self)
        logger.info("Known threads registered")
        
        ##  RADAR SECTION
        logger.info("Initializing Radar Management System")
        self.radar_started = False
        self.radar_management = None
        
        # Add display system initialization
        self.displays_started = False
        self.display_management = None
        
        # Track initialization status
        self._radar_initialized = False
        self._displays_initialized = False
        
        logger.info("Systems startup initialization completed")

    async def start(self):
        logger.info("Starting systems startup process")
        
        try:
            # Start radar system
            logger.info("Starting radar system")
            try:
                await self._start_radar_system()
                
                # ADDITIONAL SYSTEMS STARTUP CALLS HERE
                
                # Displays - Note: Qt initialization is now handled by system_manager
                await self._start_displays()
                
            except Exception as e:
                logger.exception(f"Error starting radar system: {str(e)}")
                raise
            
        except Exception as e:
            logger.error(f"Error in startup process: {str(e)}")
            self._handle_startup_error(e)
    
    async def _start_displays(self):
        """Initialize and start the Display management system"""
        # Use async lock to prevent concurrent initialization
        async with self._displays_lock:
            # Check if already initialized or started
            if self.displays_started or self._displays_initialized:
                
                return
                
            try:
                logger.info("Creating Display management system")
                self.display_management = get_display_manager()
                
                # Initialize display tree manager first using singleton
                logger.info("Creating display tree manager")
                display_tree = get_display_tree_manager()
                
                # Check if already initialized
                if not hasattr(display_tree, '_initialized') or not display_tree._initialized:
                    await display_tree.initialize()  # Initialize the tree
                
                # Initialize display message handler using singleton
                logger.info("Creating display message handler")
                display_handler = get_display_message_handler()
                
                # Initialize display response service using singleton
                logger.info("Creating display response service")
                display_response = get_display_response_service()
                
                # Check if already started
                if not hasattr(display_response, '_started') or not display_response._started:
                    await display_response.start()  # Start the response service
                
                # Register components with system manager
                from FMOFP.core.system_manager import get_system_manager
                system_manager = get_system_manager()
                system_manager.register_component('display_tree_manager', display_tree)
                system_manager.register_component('display_message_handler', display_handler)
                system_manager.register_component('display_response_service', display_response)
                
                # Initialize display management system
                logger.info("Initializing Display management system")
                await self.display_management.initialize()
                
                # Verify all components are registered and initialized
                required_components = [
                    'display_tree_manager',
                    'display_message_handler', 
                    'display_response_service'
                ]
                for component in required_components:
                    if not system_manager.get_component(component):
                        raise RuntimeError(f"Required display component {component} not registered")
                    logger.info(f"Verified {component} is registered")
                
                # Start display management. DisplayManager.start() is a
                # coroutine and this method is async, so await it directly —
                # the previous bare call created the coroutine and dropped
                # it ("RuntimeWarning: coroutine 'DisplayManager.start' was
                # never awaited"), so the display manager never actually
                # started here. (Latent until August 2026: the enclosing
                # systemsStartup.start() itself was never awaited either —
                # see system_manager.start_FM_system() — so this line had
                # never previously executed at all.)
                await self.display_management.start()
                self.displays_started = True
                self._displays_initialized = True
                logger.info("Display management system and all components started successfully")
                
            except Exception as e:
                logger.exception("Failed to start Display management system")
                raise
    
    async def _start_radar_system(self):
        """Initialize and start the radar system"""
        # Use async lock to prevent concurrent initialization
        async with self._radar_lock:
            # Check if already initialized or started
            if self.radar_started or self._radar_initialized:
                logger.info("Radar system already initialized or started, skipping")
                return
                
            try:
                logger.info("Creating radar management system")
                self.radar_management = get_radar_management_system()
                
                logger.info("Initializing radar system")
                self.radar_management.initialize()
                
                # Start the radar system (threads handled by system_manager)
                self.radar_management.start()
                
                self.radar_started = True
                self._radar_initialized = True
                logger.info("Radar system started successfully")
                
            except Exception as e:
                logger.exception("Failed to start radar system")
                raise
    
    def _handle_startup_error(self, error):
        """Handle errors during system startup"""
        logger.error(f"Startup error: {str(error)}")
        try:
            # Attempt shutdown
            self.stop()
        except Exception as e:
            logger.exception("Error during error handling shutdown")
            
    def stop(self):
        logger.info("Stopping systems startup process")
        try:
            logger.info("Stopping thread manager")
            self.thread_manager.stop_all_threads()
            
            if self.radar_management:
                self.radar_management.stop()
                
            if self.display_management:
                self.display_management.stop()
                
            logger.info("Systems startup process stopped")
        except Exception as e:
            logger.exception(f"Error during system shutdown: {str(e)}")
