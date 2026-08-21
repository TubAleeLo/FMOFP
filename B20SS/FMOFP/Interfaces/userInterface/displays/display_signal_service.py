"""
Display Signal Service

A lightweight signaling service that allows (ONLY) display components to communicate
without direct dependencies or async/sync boundary issues.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplaySignalService(QObject):
    """
    Signal service for display-related events.
    
    This service provides a way for display components to communicate
    without direct dependencies. It uses PyQt's signal/slot mechanism
    to handle cross-component communication.
    """
    
    # Signals
    display_type_changed = pyqtSignal(str, str)  # (category, display_type)
    
    # Singleton instance
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of the signal service"""
        if cls._instance is None:
            cls._instance = DisplaySignalService()
            logger.info("Created DisplaySignalService instance")
        return cls._instance
    
    def __init__(self):
        """Initialize the signal service"""
        super().__init__()
        logger.debug("DisplaySignalService initialized")
    
    def emit_display_type_changed(self, category: str, display_type: str):
        """Emit a signal when a display type changes"""
        logger.info(f"Emitting display_type_changed signal: {category}={display_type}")
        self.display_type_changed.emit(category, display_type)
