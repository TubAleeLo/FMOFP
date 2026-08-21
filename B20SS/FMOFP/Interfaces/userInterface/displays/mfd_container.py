"""
MFD Container

Container widget that manages MFD display instances and handles
switching between different display types.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
from .mfd_display_factory import MFDDisplayFactory
from .visual.theme_manager import get_theme_manager
from .display_nodes.display_tree_manager import get_display_tree_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class MFDContainer(QWidget):
    """Container for MFD that can swap implementations"""
    
    # Signal emitted when display type changes
    display_type_changed = pyqtSignal(str)
    
    def __init__(self, parent=None):
        """Initialize the MFD container"""
        super().__init__(parent)
        
        # Set up layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Initialize MFD
        self.mfd = None
        self._theme_manager = get_theme_manager()
        self._current_display_type = None
        self._running = False  # Start as not running until explicitly started
        self._initialized = False
        
        # Connect to display signal service
        from .display_signal_service import DisplaySignalService
        self._signal_service = DisplaySignalService.get_instance()
        self._signal_service.display_type_changed.connect(self._handle_display_type_changed)
        
        logger.info("MFD Container created with layout and connected to signal service")
    
    async def initialize(self):
        """Initialize the MFD display - must be called after display tree is initialized"""
        try:
            if self._initialized:
                logger.info("MFD Container already initialized")
                return
                
            logger.info("Initializing MFD Container")
            
            # Ensure display tree is initialized
            display_tree = get_display_tree_manager()
            if not display_tree._initialized:
                logger.info("Initializing display tree from MFD Container")
                await display_tree.initialize()
                
            # Now create the initial display
            await self.replace_mfd_display()
            
            self._initialized = True
            logger.info("MFD Container initialization complete")
            
        except Exception as e:
            logger.error(f"Error initializing MFD Container: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def replace_mfd_display(self):
        """Replace the current MFD with a new one based on display type"""
        try:
            # Get current display type
            display_type = MFDDisplayFactory.get_current_display_type()
            logger.info(f"Current MFD display type from factory: {display_type}")
            
            # If display type hasn't changed, do nothing
            if display_type == self._current_display_type and self.mfd is not None:
                logger.info(f"MFD display type unchanged: {display_type}")
                return
            
            logger.info(f"Replacing MFD display with type: {display_type}")
            
            # Remove current MFD if it exists
            if self.mfd:
                # Stop the current MFD if it's running
                if hasattr(self.mfd, 'stop') and self._running:
                    try:
                        self.mfd.stop()
                        logger.info("Stopped existing MFD display")
                    except Exception as stop_error:
                        logger.error(f"Error stopping existing MFD display: {str(stop_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                # Call cleanup method if it exists to ensure proper resource cleanup
                if hasattr(self.mfd, 'cleanup'):
                    try:
                        self.mfd.cleanup()
                        logger.info("Cleaned up resources for existing MFD display")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up existing MFD display: {str(cleanup_error)}")
                        import traceback
                        logger.error(traceback.format_exc())
                
                # Ensure the old display is completely removed
                self.layout.removeWidget(self.mfd)
                self.mfd.setParent(None)
                self.mfd.deleteLater()
                
                # Force an update to ensure the old display is gone
                self.update()
                
                logger.info("Removed existing MFD display")
            
            # Create new MFD using factory with self as parent
            logger.info("Creating new MFD display using factory")
            self.mfd = MFDDisplayFactory.create_display(parent=self)
            
            if not self.mfd:
                logger.error("Factory returned None for MFD display")
                raise RuntimeError("Failed to create MFD display")
            
            # Add to layout
            self.layout.addWidget(self.mfd)
            logger.info("Added new MFD display to layout")
            
            # Update current display type
            self._current_display_type = display_type
            
            # Emit signal
            self.display_type_changed.emit(display_type)
            
            logger.info(f"Successfully replaced MFD with {display_type} display")
            
            # Start the display if container is running
            if self._running and hasattr(self.mfd, 'start'):
                try:
                    self.mfd.start()
                    logger.info(f"Started new {display_type} MFD display")
                except Exception as start_error:
                    logger.error(f"Error starting new MFD display: {str(start_error)}")
                    import traceback
                    logger.error(traceback.format_exc())
            
        except Exception as e:
            logger.error(f"Error replacing MFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    async def check_display_type(self):
        """Check if display type has changed and update if needed"""
        display_type = MFDDisplayFactory.get_current_display_type()
        if display_type != self._current_display_type:
            logger.info(f"Display type changed from {self._current_display_type} to {display_type}")
            await self.replace_mfd_display()
    
    async def start(self):
        """Start the MFD display"""
        try:
            # Ensure initialized
            if not self._initialized:
                logger.info("Initializing MFD Container during start")
                await self.initialize()
            
            # Verify MFD exists
            if not self.mfd:
                logger.error("Cannot start MFD container: No MFD display instance")
                raise RuntimeError("No MFD display instance")
                
            # Start the display first
            if hasattr(self.mfd, 'start'):
                self.mfd.start()
                logger.info("MFD display started")
                
                # Verify display is actually running
                if hasattr(self.mfd, 'is_running') and not self.mfd.is_running():
                    logger.error("MFD display failed to start properly")
                    raise RuntimeError("MFD display failed to start properly")
                
                # Only set running flag after successful start
                self._running = True
                logger.info("MFD container running state set to True")
            else:
                logger.error("MFD display does not have start method")
                raise RuntimeError("MFD display does not have start method")
        except Exception as e:
            # Ensure running flag is False on error
            self._running = False
            logger.error(f"Error starting MFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def stop(self):
        """Stop the MFD display"""
        try:
            self._running = False
            if self.mfd:
                # Stop the display
                if hasattr(self.mfd, 'stop'):
                    self.mfd.stop()
                    logger.info("MFD display stopped")
                
                # Clean up resources
                if hasattr(self.mfd, 'cleanup'):
                    self.mfd.cleanup()
                    logger.info("MFD display resources cleaned up")
        except Exception as e:
            logger.error(f"Error stopping MFD display: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
    
    def is_running(self):
        """Check if the MFD display is running"""
        # Check both container running state and actual display running state
        if not self._running:
            return False
        # Verify the actual display is running if it exists
        if self.mfd and hasattr(self.mfd, 'is_running'):
            return self.mfd.is_running()
        return self._running
    
    def set_mode(self, mode):
        """Set the display mode"""
        if self.mfd and hasattr(self.mfd, 'set_mode'):
            self.mfd.set_mode(mode)
            logger.info(f"MFD display mode set to {mode}")
    
    def _handle_display_type_changed(self, category: str, display_type: str):
        """Handle display type change signal from signal service"""
        try:
            # Only process signals for MFD
            if category != "mfd":
                return
                
            logger.info(f"Received display type change signal: {category}={display_type}")
            
            # Schedule the async replace operation
            import asyncio
            
            # Create a task to replace the display
            asyncio.create_task(self.replace_mfd_display())
            logger.info(f"Scheduled MFD display replacement for type: {display_type}")
            
        except Exception as e:
            logger.error(f"Error handling display type change signal: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
