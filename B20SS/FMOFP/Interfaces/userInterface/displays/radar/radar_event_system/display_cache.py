"""
Display Cache

Provides local caching for radar display data.
Maintains system separation by storing data only in local memory.
"""

import time
from typing import Dict, Any, Optional
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class DisplayCache:
    """Local cache for radar display data."""
    
    def __init__(self):
        """Initialize display cache."""
        # Local memory only
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._displays: Dict[str, str] = {}  # display_id -> display_type
        self._last_update: Dict[str, float] = {}  # display_id -> timestamp
        
        logger.info("Initialized DisplayCache")
        
    def register_display(self, display_id: str, display_type: str):
        """Register display for caching.
        
        Args:
            display_id: Display identifier
            display_type: Type of display
        """
        try:
            self._displays[display_id] = display_type
            self._cache[display_id] = {}
            self._last_update[display_id] = time.time()
            
            logger.info(f"Registered display {display_id} ({display_type})")
            
        except Exception as e:
            logger.error(f"Error registering display: {e}")
            
    def unregister_display(self, display_id: str):
        """Unregister display and clear its cache.
        
        Args:
            display_id: Display identifier
        """
        try:
            self._displays.pop(display_id, None)
            self._cache.pop(display_id, None)
            self._last_update.pop(display_id, None)
            
            logger.info(f"Unregistered display {display_id}")
            
        except Exception as e:
            logger.error(f"Error unregistering display: {e}")
            
    def update_display_data(self, display_id: str, data: Dict[str, Any]):
        """Update cached data for display.
        
        Args:
            display_id: Display identifier
            data: Data to cache
        """
        try:
            if display_id not in self._displays:
                logger.warning(f"Display {display_id} not registered")
                return
                
            # Update cache with timestamp
            self._cache[display_id] = {
                'data': data,
                'timestamp': time.time()
            }
            self._last_update[display_id] = time.time()
            
            logger.debug(f"Updated cache for display {display_id}")
            
        except Exception as e:
            logger.error(f"Error updating display data: {e}")
            
    def get_display_data(self, display_id: str) -> Optional[Dict[str, Any]]:
        """Get cached data for display.
        
        Args:
            display_id: Display identifier
            
        Returns:
            Cached data or None if not found
        """
        try:
            if display_id not in self._displays:
                logger.warning(f"Display {display_id} not registered")
                return None
                
            cached = self._cache.get(display_id, {})
            return cached.get('data')
            
        except Exception as e:
            logger.error(f"Error getting display data: {e}")
            return None
            
    def get_last_update(self, display_id: str) -> Optional[float]:
        """Get timestamp of last update for display.
        
        Args:
            display_id: Display identifier
            
        Returns:
            Timestamp or None if not found
        """
        return self._last_update.get(display_id)
        
    def clear_cache(self, display_id: Optional[str] = None):
        """Clear cache for display or all displays.
        
        Args:
            display_id: Optional display identifier. If None, clears all.
        """
        try:
            if display_id:
                if display_id in self._cache:
                    self._cache[display_id] = {}
                    logger.info(f"Cleared cache for display {display_id}")
            else:
                self._cache.clear()
                logger.info("Cleared all display caches")
                
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            
    def is_registered(self, display_id: str) -> bool:
        """Check if display is registered.
        
        Args:
            display_id: Display identifier
            
        Returns:
            bool: True if registered
        """
        return display_id in self._displays
        
    def get_display_type(self, display_id: str) -> Optional[str]:
        """Get type of registered display.
        
        Args:
            display_id: Display identifier
            
        Returns:
            Display type or None if not registered
        """
        return self._displays.get(display_id)
