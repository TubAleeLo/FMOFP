"""
HUD Container

Container widget that manages HUD display instances and handles
switching between different display types.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from .hud_display_factory import HUDDisplayFactory
from .visual.theme_manager import get_theme_manager
from .display_nodes.display_tree_manager import get_display_tree_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class HUDContainer(QWidget):
    """Container for HUD that can swap implementations"""
    
    # Signal emitted when display type changes
    display_type_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the HUD container"""
        super().__init__(parent)
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Initialize HUD
        self.hud = None
        self._theme_manager = get_theme_manager()
        self._current_display_type = None
        self._running = False  # Start as not running until explicitly started
        self._initialized = False
        
        # Connect to display signal service
        from .display_signal_service import DisplaySignalService
        self._signal_service = DisplaySignalService.get_instance()
        self._signal_service.display_type_changed.connect(self._handle_display_type_changed)
        
        logger.info("HUD Container created with layout and connected to signal service")
    
    async def initialize(self):
        """Initialize the HUD display - must be called after display tree is initialized"""
        try:
            if self._initialized:
                logger.info("HUD Container already initialized")
                return
                
            logger.info("Initializing HUD Container")
            
            # Ensure display tree is initialized
            display_tree = get_display_tree_manager()
            if not display_tree._initialized:
                logger.info("Initializing display tree from HUD Container")
                await display_tree.initialize()
                
            # Now create the initial display
            await self.replace_hud_display()
            
            self._initialized = True
            logger.info("HUD Container initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing HUD Container: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def replace_hud_display(self):
        """Replace the current HUD with a new one based on display type"""
        try:
            # Get current display type
            display_type = HUDDisplayFactory.get_current_display_type()
            logger.info(f"Current HUD display type from factory: {display_type}")
            
            # If display type hasn't changed, do nothing
            if display_type == self._current_display_type and self.hud is not None:
                logger.info(f"HUD display type unchanged: {display_type}")
                return
            
            logger.info(f"Replacing HUD display with type: {display_type}")
            
            # Remove current HUD if it exists
            if self.hud:
                # Stop the current HUD if it's running
                if hasattr(self.hud, 'stop') and self._running:
                    try:
                        self.hud.stop()
                        logger.info("Stopped existing HUD display")
                    except Exception as stop_error:
                        logger.error(f"Error stopping existing HUD display: {str(stop_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                # Call cleanup method if it exists to ensure proper resource cleanup
                if hasattr(self.hud, 'cleanup'):
                    try:
                        self.hud.cleanup()
                        logger.info("Cleaned up resources for existing HUD display")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up existing HUD display: {str(cleanup_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                # Ensure the old display is completely removed
                self.layout.removeWidget(self.hud)
                self.hud.setParent(None)
                self.hud.deleteLater()
                
                # Force an update to ensure the old display is gone
                self.update()
                
                logger.info("Removed existing HUD display")
            
            # Create new HUD using factory with self as parent
            logger.info("Creating new HUD display using factory")
            self.hud = HUDDisplayFactory.create_display(parent=self)
            
            if not self.hud:
                logger.error("Factory returned None for HUD display")
                raise RuntimeError("Failed to create HUD display")
            
            # Add to layout
            self.layout.addWidget(self.hud)
            logger.info("Added new HUD display to layout")
            
            # Update current display type
            self._current_display_type = display_type
            logger.info(f"HUD container updated display type to: {display_type}")
            
            # Emit signal
            self.display_type_changed.emit(display_type)
            logger.info(f"HUD container emitted display_type_changed signal: {display_type}")
            
            logger.info(f"Successfully replaced HUD with {display_type} display")
            
            # Log container state before starting display
            logger.info(f"HUD container state before start: running={self._running}, display_type={self._current_display_type}")
            
            # Start the display if container is running
            if self._running and hasattr(self.hud, 'start'):
                try:
                    self.hud.start()
                    # Verify display is running
                    is_running = self.hud.is_running() if hasattr(self.hud, 'is_running') else "unknown"
                    logger.info(f"Started new {display_type} HUD display, is_running={is_running}")
                except Exception as start_error:
                    logger.error(f"Error starting new HUD display: {str(start_error)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Log container state after starting display
            logger.info(f"HUD container state after start: running={self._running}, display_type={self._current_display_type}")
            
        except Exception as e:
            logger.error(f"Error replacing HUD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    async def check_display_type(self):
        """Check if display type has changed and update if needed"""
        display_type = HUDDisplayFactory.get_current_display_type()
        if display_type != self._current_display_type:
            logger.info(f"Display type changed from {self._current_display_type} to {display_type}")
            await self.replace_hud_display()
    
    async def start(self):
        """Start the HUD display"""
        try:
            # Ensure initialized
            if not self._initialized:
                logger.info("Initializing HUD Container during start")
                await self.initialize()
            
            # Verify HUD exists
            if not self.hud:
                logger.error("Cannot start HUD container: No HUD display instance")
                raise RuntimeError("No HUD display instance")
            
            # Start the display
            if hasattr(self.hud, 'start'):
                self.hud.start()
                logger.info("HUD display started")
                
                # Verify display is actually running with enhanced logging
                if hasattr(self.hud, 'is_running'):
                    running_state = self.hud.is_running()
                    logger.info(f"HUD display running state: {running_state}")
                    if not running_state:
                        logger.error("HUD display failed to start properly")
                        raise RuntimeError("HUD display failed to start properly")
                else:
                    logger.warning("HUD display does not have is_running method, cannot verify running state")
                
                # Only set running flag after successful start
                self._running = True
                logger.info("HUD container running state set to True")
            else:
                logger.error("HUD display does not have start method")
                raise RuntimeError("HUD display does not have start method")
        except Exception as e:
            # Ensure running flag is False on error
            self._running = False
            logger.error(f"Error starting HUD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def stop(self):
        """Stop the HUD display"""
        try:
            self._running = False
            if self.hud:
                # Stop the display
                if hasattr(self.hud, 'stop'):
                    self.hud.stop()
                    logger.info("HUD display stopped")
                
                # Clean up resources
                if hasattr(self.hud, 'cleanup'):
                    self.hud.cleanup()
                    logger.info("HUD display resources cleaned up")
        except Exception as e:
            logger.error(f"Error stopping HUD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def is_running(self):
        """Check if the HUD display is running"""
        # Check both container running state and actual display running state
        if not self._running:
            return False
        # Verify the actual display is running if it exists
        if self.hud and hasattr(self.hud, 'is_running'):
            return self.hud.is_running()
        return self._running
    
    def set_mode(self, mode):
        """Set the display mode"""
        if self.hud and hasattr(self.hud, 'set_mode'):
            self.hud.set_mode(mode)
            logger.info(f"HUD display mode set to {mode}")
    
    def _handle_display_type_changed(self, category: str, display_type: str):
        """Handle display type change signal from signal service"""
        try:
            # Only process signals for HUD
            if category != "hud":
                return
                
            logger.info(f"Received display type change signal: {category}={display_type}")
            
            # Schedule the async replace operation
            import asyncio
            
            # Create a task to replace the display
            asyncio.create_task(self.replace_hud_display())
            logger.info(f"Scheduled HUD display replacement for type: {display_type}")
            
        except Exception as e:
            logger.error(f"Error handling display type change signal: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
