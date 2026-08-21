"""
Base Radar Display

Implements base radar display functionality using DisplayMessenger for 1553B communication.
Maintains system separation through proper RT implementation.
"""

import time
from typing import Dict, Any, Optional
from FMOFP.Interfaces.userInterface.messaging.displayMessenger import get_display_messenger
from FMOFP.Interfaces.userInterface.messaging.display_mil_std_1553b import DisplayMIL_STD_1553B_Message
from FMOFP.Interfaces.userInterface.messaging.display_command_map import DISPLAY_SUBADDRESSES
from FMOFP.Interfaces.userInterface.messaging.display_address_utils import get_display_rt_address
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class BaseRadarDisplay:
    """Base class for radar displays using DisplayMessenger."""
    
    def __init__(self, display_type: str):
        """Initialize radar display.
        
        Args:
            display_type: Type of display (e.g., 'radar')
        """
        self.display_type = display_type
        self.display_messenger = get_display_messenger()
        
        # Local state only
        self._local_cache: Dict[str, Any] = {}
        self._mode: Optional[int] = None
        self._error_state = False
        self._error_message = ""
        
        logger.info(f"Initialized {display_type} display")
        
    async def handle_mode_change(self, mode: int):
        """Handle mode change through DisplayMessenger.
        
        Args:
            mode: Mode value to set
        """
        try:
            # Construct message using display-local message class
            message = DisplayMIL_STD_1553B_Message(
                rt_address=self.display_messenger.get_display_address(),
                sub_address=DISPLAY_SUBADDRESSES['radar'],
                data=format(mode, '016b')
            )
            
            # Route through DisplayMessenger
            self.display_messenger.route_message(message)
            
            # Update local state
            self._mode = mode
            self.update_local_cache({'mode': mode})
            
            logger.info(f"{self.display_type} mode changed to {mode}")
            
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")
            self._error_state = True
            self._error_message = f"Mode change error: {str(e)}"
            
    def update_local_cache(self, data: Dict[str, Any]):
        """Update local cache only, no system access.
        
        Args:
            data: Data to cache locally
        """
        try:
            self._local_cache.update({
                **data,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.error(f"Error updating local cache: {e}")
            
    def get_cached_data(self, key: str) -> Any:
        """Get data from local cache only.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached value or None if not found
        """
        return self._local_cache.get(key)
        
    def handle_data_update(self, data: Dict[str, Any]):
        """Handle data update locally.
        
        Args:
            data: Updated display data
        """
        try:
            # Update local cache
            self.update_local_cache(data)
            
            # Trigger display refresh
            self.update()
            
        except Exception as e:
            logger.error(f"Error handling data update: {e}")
            self._error_state = True
            self._error_message = f"Data update error: {str(e)}"
            
    def update(self):
        """Update display from local cache."""
        try:
            if self._error_state:
                self._draw_error_message()
                return
                
            if not self._mode:
                return
                
            # Get cached data
            cached_data = self._local_cache.get('radar_data')
            if cached_data:
                self.render(cached_data)
                
        except Exception as e:
            logger.error(f"Error updating display: {e}")
            self._error_state = True
            self._error_message = f"Display update error: {str(e)}"
            
    def render(self, data: Dict[str, Any]):
        """Render display with data.
        
        Args:
            data: Display data to render
        """
        raise NotImplementedError("Subclasses must implement render()")
        
    def _draw_error_message(self):
        """Draw error message on display."""
        if self._error_message:
            # Implementation specific to display framework
            pass
            
    def is_healthy(self) -> bool:
        """Check if display is healthy.
        
        Returns:
            bool: True if display is healthy
        """
        return (
            not self._error_state and
            self.display_messenger and
            self.display_messenger.is_healthy()
        )
