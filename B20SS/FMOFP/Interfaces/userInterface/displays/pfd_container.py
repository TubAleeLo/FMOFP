"""
PFD Container

Container widget that manages PFD display instances and handles
switching between different display types.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from .pfd_display_factory import PFDDisplayFactory
from .visual.theme_manager import get_theme_manager
from .display_nodes.display_tree_manager import get_display_tree_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class PFDContainer(QWidget):
    """Container for PFD that can swap implementations"""
    
    # Signal emitted when display type changes
    display_type_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the PFD container"""
        super().__init__(parent)
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Initialize PFD
        self.pfd = None
        self._theme_manager = get_theme_manager()
        self._current_display_type = None
        self._running = False  # Start as not running until explicitly started
        self._initialized = False
        
        # Connect to display signal service
        from .display_signal_service import DisplaySignalService
        self._signal_service = DisplaySignalService.get_instance()
        self._signal_service.display_type_changed.connect(self._handle_display_type_changed)
        
        logger.info("PFD Container created with layout and connected to signal service")
    
    async def initialize(self):
        """Initialize the PFD display - must be called after display tree is initialized"""
        try:
            if self._initialized:
                logger.info("PFD Container already initialized")
                return
                
            logger.info("Initializing PFD Container")
            
            # Ensure display tree is initialized
            display_tree = get_display_tree_manager()
            if not display_tree._initialized:
                logger.info("Initializing display tree from PFD Container")
                await display_tree.initialize()
                
            # Now create the initial display
            await self.replace_pfd_display()
            
            self._initialized = True
            logger.info("PFD Container initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing PFD Container: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def replace_pfd_display(self):
        """Replace the current PFD with a new one based on display type"""
        try:
            # Get current display type
            display_type = PFDDisplayFactory.get_current_display_type()
            logger.info(f"Current PFD display type from factory: {display_type}")
            
            # If display type hasn't changed, do nothing
            if display_type == self._current_display_type and self.pfd is not None:
                logger.info(f"PFD display type unchanged: {display_type}")
                return
            
            logger.info(f"Replacing PFD display with type: {display_type}")
            
            # Remove current PFD if it exists
            if self.pfd:
                # Stop the current PFD if it's running
                if hasattr(self.pfd, 'stop') and self._running:
                    try:
                        self.pfd.stop()
                        logger.info("Stopped existing PFD display")
                    except Exception as stop_error:
                        logger.error(f"Error stopping existing PFD display: {str(stop_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                # Call cleanup method if it exists to ensure proper resource cleanup
                if hasattr(self.pfd, 'cleanup'):
                    try:
                        self.pfd.cleanup()
                        logger.info("Cleaned up resources for existing PFD display")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up existing PFD display: {str(cleanup_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                self.layout.removeWidget(self.pfd)
                self.pfd.setParent(None)
                self.pfd.deleteLater()
                
                # Force an update to ensure the old display is gone
                self.update()
                
                logger.info("Removed existing PFD display")
            
            # Create new PFD using factory with self as parent
            logger.info("Creating new PFD display using factory")
            self.pfd = PFDDisplayFactory.create_display(parent=self)     # Oh Brother Where Art Thou - Dueling Banjos
            
            if not self.pfd:
                logger.error("Factory returned None for PFD display")
                raise RuntimeError("Failed to create PFD display")
            
            # Add to layout
            self.layout.addWidget(self.pfd)
            logger.info("Added new PFD display to layout")
            
            # Update current display type
            self._current_display_type = display_type
            
            # Emit signal
            self.display_type_changed.emit(display_type)
            
            logger.info(f"Successfully replaced PFD with {display_type} display")
            
            # Start the display if container is running
            if self._running and hasattr(self.pfd, 'start'):
                try:
                    self.pfd.start()
                    logger.info(f"Started new {display_type} PFD display")
                except Exception as start_error:
                    logger.error(f"Error starting new PFD display: {str(start_error)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
        except Exception as e:
            logger.error(f"Error replacing PFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def check_display_type(self):
        """Check if display type has changed and update if needed"""
        display_type = PFDDisplayFactory.get_current_display_type()
        if display_type != self._current_display_type:
            logger.info(f"Display type changed from {self._current_display_type} to {display_type}")
            await self.replace_pfd_display()
    
    async def start(self):
        """Start the PFD display"""
        try:
            # Ensure initialized
            if not self._initialized:
                logger.info("Initializing PFD Container during start")
                await self.initialize()
            
            # Verify PFD exists
            if not self.pfd:
                logger.error("Cannot start PFD container: No PFD display instance")
                raise RuntimeError("No PFD display instance")
                
            # Start the display first
            if hasattr(self.pfd, 'start'):
                self.pfd.start()
                logger.info("PFD display started")
                
                # Verify display is actually running
                if hasattr(self.pfd, 'is_running') and not self.pfd.is_running():
                    logger.error("PFD display failed to start properly")
                    raise RuntimeError("PFD display failed to start properly")
                
                # Only set running flag after successful start
                self._running = True
                logger.info("PFD container running state set to True")
            else:
                logger.error("PFD display does not have start method")
                raise RuntimeError("PFD display does not have start method")
        except Exception as e:
            # Ensure running flag is False on error
            self._running = False
            logger.error(f"Error starting PFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def stop(self):
        """Stop the PFD display"""
        try:
            self._running = False
            if self.pfd:
                # Stop the display
                if hasattr(self.pfd, 'stop'):
                    self.pfd.stop()
                    logger.info("PFD display stopped")
                
                # Clean up resources
                if hasattr(self.pfd, 'cleanup'):
                    self.pfd.cleanup()
                    logger.info("PFD display resources cleaned up")
        except Exception as e:
            logger.error(f"Error stopping PFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def is_running(self):
        """Check if the PFD display is running"""
        # Check both container running state and actual display running state
        if not self._running:
            return False
        # Verify the actual display is running if it exists
        if self.pfd and hasattr(self.pfd, 'is_running'):
            return self.pfd.is_running()
        return self._running
    
    def set_mode(self, mode):
        """Set the display mode"""
        if self.pfd and hasattr(self.pfd, 'set_mode'):
            self.pfd.set_mode(mode)
            logger.info(f"PFD display mode set to {mode}")
    
    def _handle_display_type_changed(self, category: str, display_type: str):
        """Handle display type change signal from signal service"""
        try:
            # Only process signals for PFD
            if category != "pfd":
                return
                
            logger.info(f"Received display type change signal: {category}={display_type}")
            
            # Schedule the async replace operation
            import asyncio
            
            # Create a task to replace the display
            asyncio.create_task(self.replace_pfd_display())
            logger.info(f"Scheduled PFD display replacement for type: {display_type}")
            
        except Exception as e:
            logger.error(f"Error handling display type change signal: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
