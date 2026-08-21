"""
Centralized legend generator for radar displays.

This module provides a centralized approach to generating legends for different
radar display types, ensuring only one appropriate legend is generated at a time
while pulling data from the same source of truth.
"""
import time
from typing import Dict, Optional, Any, Set, Counter
from enum import Enum
from PyQt6.QtCore import QRectF, QPointF
from PyQt6.QtGui import QPainter
from ..utils.visual_settings_manager import get_visual_settings_manager
from Utils.logger.sys_logger import get_logger
from .legend_manager import LegendConfig, get_legend_manager

logger = get_logger()

class LegendType(Enum):
    """Types of legends that can be generated"""
    VIL = "vil"
    PRECIPITATION = "precipitation"
    INTENSITY = "intensity"
    TURBULENCE = "turbulence"
    WINDSHEAR = "windshear"
    TERRAIN = "terrain"

class LegendGenerator:
    """Centralized generator for radar display legends"""
    
    def __init__(self, radar_type: str = 'weather_radar'):
        """Initialize the legend generator.
        
        Args:
            radar_type: Type of radar (e.g. 'weather_radar')
        """
        self.radar_type = radar_type
        self._current_mode = None
        self._settings_manager = get_visual_settings_manager(radar_type)
        self._legend_manager = get_legend_manager(radar_type)
        
        # Track which legend types are currently active
        self._active_legend_types = set()
        
        # Cache for generated legends
        self._legend_cache = {}
        
        # Data tracking for contextual legend display
        self._data_display_status = {
            'vil': {'visible': False, 'last_seen': 0},
            'precipitation': {'visible': False, 'last_seen': 0},
            'cells': {'visible': False, 'last_seen': 0}
        }
        self._data_retention_time = 10.0  # Keep showing legend for 10 seconds after data disappears
        
        # Message counters for throttling log messages
        self._message_counters = {
            'data_status': Counter(),
            'active_data_types': 0,
            'mode_update': Counter(),
            'active_legend_types': 0,
            'settings_update': 0
        }
        # Thresholds for when to log with counters
        self._log_threshold = 10  # Log after this many occurrences
        
        logger.info(f"[LEGEND_GENERATOR] Initialized for {radar_type}")
        
    def update_mode(self, mode: str) -> None:
        """Update the current mode and refresh legend states.
        
        Args:
            mode: Current radar mode
        """
        if self._current_mode == mode:
            # Increment the counter for same mode updates, which might be throttled
            key = f"same_mode_{mode}"
            self._message_counters['mode_update'][key] = self._message_counters['mode_update'].get(key, 0) + 1
            count_value = self._message_counters['mode_update'][key]
            
            # Only log if threshold reached
            if count_value >= self._log_threshold:
                logger.info(f"[LEGEND_GENERATOR] Mode already set to {mode} ({count_value} occurrences since last log)")
                self._message_counters['mode_update'][key] = 0
            return
            
        # Different mode - update everything and log immediately
        old_mode = self._current_mode
        self._current_mode = mode
        self._legend_manager.update_legend_state(mode)
        self._update_active_legend_types()
        
        # Clear cache when mode changes
        self._legend_cache.clear()
        
        # Always log mode changes (not throttled)
        logger.info(f"[LEGEND_GENERATOR] Updated mode from {old_mode} to {mode}")
        
    def _update_active_legend_types(self) -> None:
        """Update the set of active legend types based on current mode, settings, and visibility."""
        previous_active_types = self._active_legend_types.copy()
        self._active_legend_types.clear()
        
        # Get settings
        settings = self._settings_manager.get_settings()
        current_time = time.time()
        
        # Check each legend type
        for legend_type in LegendType:
            config = self._legend_manager.get_legend_config(legend_type.value)
            if config and config.is_allowed_in_mode(self._current_mode):
                # Check if legend is enabled in settings
                setting_key = f"show_{legend_type.value}_legend"
                if settings.get(setting_key, False):
                    # Check if this data type is actually visible or recently visible
                    data_type = legend_type.value
                    is_active = False
                    
                    # If data exists in data_display_status, check visibility with lag allowance
                    if data_type in self._data_display_status:
                        status = self._data_display_status[data_type]
                        is_active = status['visible'] or (current_time - status['last_seen'] < self._data_retention_time)
                    
                    # Add to active types if visible or if we don't have visibility info for this type
                    if is_active or data_type not in self._data_display_status:
                        self._active_legend_types.add(legend_type)
        
        # Increment counter for active_legend_types logs
        self._message_counters['active_legend_types'] += 1
        count_value = self._message_counters['active_legend_types']
        
        # Only log if threshold reached or active types changed
        if previous_active_types != self._active_legend_types or count_value >= self._log_threshold:
            logger.info(f"[LEGEND_GENERATOR] Active legend types: {self._active_legend_types} ({count_value} occurrences since last log)")
            self._message_counters['active_legend_types'] = 0
        
    def reset_message_counters(self, counter_type: Optional[str] = None, 
                             exclude_types: Optional[Set[str]] = None) -> None:
        """Reset message counters for logging throttling.
        
        Args:
            counter_type: Specific counter type to reset, or None to reset all
            exclude_types: Set of counter types to exclude from reset
        """
        if exclude_types is None:
            exclude_types = set()
            
        if counter_type:
            # Reset specific counter type
            if counter_type == 'data_status':
                # For data_status, we keep a separate counter per data type
                # We can selectively clear specific data types
                data_types_to_clear = set(self._message_counters['data_status'].keys())
                data_types_to_clear -= exclude_types
                
                for data_type in data_types_to_clear:
                    self._message_counters['data_status'][data_type] = 0
            elif counter_type not in exclude_types:
                # Reset other counter types if not excluded
                self._message_counters[counter_type] = 0 if isinstance(self._message_counters[counter_type], int) else Counter()
        else:
            # Reset all counters except excluded types
            for c_type in self._message_counters:
                if c_type not in exclude_types:
                    if c_type == 'data_status':
                        # Handle data_status specially - keep excluded data types
                        data_types_to_keep = set(self._message_counters['data_status'].keys()) & exclude_types
                        self._message_counters['data_status'] = Counter()
                        for data_type in data_types_to_keep:
                            self._message_counters['data_status'][data_type] = self._message_counters['data_status'][data_type]
                    else:
                        # Reset other counter types
                        self._message_counters[c_type] = 0 if isinstance(self._message_counters[c_type], int) else Counter()
                        
    def update_data_status(self, data_type: str, count: int) -> None:
        """Update the display status for a data type based on its count.
        
        Args:
            data_type: Type of data (e.g., 'vil', 'precipitation')
            count: Number of data points currently displayed
        """
        current_time = time.time()
        
        if data_type in self._data_display_status:
            # Update visibility status
            was_visible = self._data_display_status[data_type]['visible']
            is_visible = count > 0
            
            # Store current count and status
            if not hasattr(self, '_last_data_status'):
                self._last_data_status = {}
            
            # Check if we need to store this data type's last status
            if data_type not in self._last_data_status:
                self._last_data_status[data_type] = {
                    'visible': is_visible,
                    'count': count
                }
                
            # Only update and log if something actually changed OR at throttled intervals
            status_changed = (was_visible != is_visible or 
                             self._last_data_status[data_type]['count'] != count)
            
            if status_changed:
                # Update the stored state due to a change
                self._data_display_status[data_type]['visible'] = is_visible
                self._last_data_status[data_type]['visible'] = is_visible
                self._last_data_status[data_type]['count'] = count
                
                # Update last_seen timestamp if data is visible or just disappeared
                if is_visible:
                    self._data_display_status[data_type]['last_seen'] = current_time
                elif was_visible and not is_visible:
                    # Only update when transitioning from visible to not visible
                    self._data_display_status[data_type]['last_seen'] = current_time
                
                # Always log actual changes immediately
                logger.info(f"[LEGEND_GENERATOR] State change: {data_type} status: visible={is_visible}, points={count}")
                # Reset counter when we log a change
                self._message_counters['data_status'][data_type] = 0
            else:
                # No change, just update the state without logging
                self._data_display_status[data_type]['visible'] = is_visible
                
                # Increment counter for unchanged updates
                self._message_counters['data_status'][data_type] += 1
                count_value = self._message_counters['data_status'][data_type]
                
                # We use an extra check to completely avoid calling the logger if not needed
                if count_value >= 1000:
                    logger.debug(f"[LEGEND_GENERATOR] No change in {data_type} status after {count_value} checks: visible={is_visible}, points={count}")
                    # Reset counter after logging
                    self._message_counters['data_status'][data_type] = 0
            
    def get_primary_legend_type(self) -> Optional[LegendType]:
        """Get the primary legend type for the current mode based on what data is actually visible.
        
        Returns:
            Primary legend type or None if no legends are active
        """
        if not self._active_legend_types:
            return None
            
        # First, calculate which data types should have their legends shown
        # based on current visibility and retention time
        current_time = time.time()
        active_data_types = set()
        
        for data_type, status in self._data_display_status.items():
            if status['visible'] or (current_time - status['last_seen'] < self._data_retention_time):
                # Convert data_type to LegendType
                try:
                    legend_type = LegendType(data_type)
                    if legend_type in self._active_legend_types:
                        active_data_types.add(legend_type)
                except ValueError:
                    # Handle case where data_type doesn't match a LegendType
                    pass
        
        # Increment counter for active_data_types log
        self._message_counters['active_data_types'] += 1
        count_value = self._message_counters['active_data_types']
        
        # Only log if we've reached the threshold or if active types changed
        if not hasattr(self, '_last_active_data_types') or self._last_active_data_types != active_data_types or count_value >= self._log_threshold:
            logger.info(f"[LEGEND_GENERATOR] Active data types for legend: {active_data_types} ({count_value} occurrences since last log)")
            self._message_counters['active_data_types'] = 0
            self._last_active_data_types = active_data_types.copy()
        
        # If we have active data types, prioritize them
        if active_data_types:
            # Priority order based on mode, but only considering active data types
            if self._current_mode == "SURVEILLANCE":
                priorities = [
                    LegendType.VIL,
                    LegendType.PRECIPITATION,
                    LegendType.INTENSITY
                ]
            elif self._current_mode == "MAPPING":
                priorities = [
                    LegendType.TERRAIN,
                    LegendType.VIL
                ]
            elif self._current_mode == "TURBULENCE":
                priorities = [
                    LegendType.TURBULENCE,
                    LegendType.INTENSITY
                ]
            elif self._current_mode == "WINDSHEAR":
                priorities = [
                    LegendType.WINDSHEAR,
                    LegendType.INTENSITY
                ]
            else:
                # Default priority
                priorities = list(LegendType)
                
            # Return first active data type in priority order
            for legend_type in priorities:
                if legend_type in active_data_types:
                    return legend_type
                    
            # Fallback to first active data type
            return next(iter(active_data_types))
        
        # If no active data types, fall back to regular priority logic
        if self._current_mode == "SURVEILLANCE":
            priorities = [
                LegendType.VIL,
                LegendType.PRECIPITATION,
                LegendType.INTENSITY
            ]
        elif self._current_mode == "MAPPING":
            priorities = [
                LegendType.TERRAIN,
                LegendType.VIL
            ]
        elif self._current_mode == "TURBULENCE":
            priorities = [
                LegendType.TURBULENCE,
                LegendType.INTENSITY
            ]
        elif self._current_mode == "WINDSHEAR":
            priorities = [
                LegendType.WINDSHEAR,
                LegendType.INTENSITY
            ]
        else:
            # Default priority
            priorities = list(LegendType)
            
        # Return first active legend type in priority order
        for legend_type in priorities:
            if legend_type in self._active_legend_types:
                return legend_type
                
        # Fallback to first active legend type
        return next(iter(self._active_legend_types)) if self._active_legend_types else None
        
    def draw_legend(self, painter: QPainter, rect: QRectF, legend_type: Optional[LegendType] = None) -> None:
        """Draw a specific legend type or the primary legend if none specified.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
            legend_type: Type of legend to draw, or None to draw primary legend
        """
        # If no specific legend requested, use primary legend
        if legend_type is None:
            legend_type = self.get_primary_legend_type()
            if not legend_type:
                return
                
        # Use the legend manager to draw the legend
        self._legend_manager.draw_legend(painter, rect, legend_type.value)
        
    def draw_all_legends(self, painter: QPainter, rect: QRectF) -> None:
        """Draw all active legends using the collapsible panel.
        
        Args:
            painter: QPainter instance
            rect: Drawing rectangle
        """
        # Use the legend manager to draw all legends
        self._legend_manager.draw_all_legends(painter, rect)
        
    def handle_click(self, pos: QPointF) -> bool:
        """Handle mouse click at the specified position.
        
        Args:
            pos: Click position
            
        Returns:
            True if click was handled, False otherwise
        """
        # Use the legend manager to handle the click
        return self._legend_manager.handle_click(pos)
        
    def get_legend_config(self, legend_type: LegendType) -> Optional[LegendConfig]:
        """Get the configuration for a specific legend type.
        
        Args:
            legend_type: Type of legend
            
        Returns:
            Legend configuration or None if not found
        """
        return self._legend_manager.get_legend_config(legend_type.value)
        
    def is_legend_active(self, legend_type: LegendType) -> bool:
        """Check if a legend type is currently active.
        
        Args:
            legend_type: Type of legend
            
        Returns:
            True if the legend is active, False otherwise
        """
        return legend_type in self._active_legend_types
        
    def get_active_legend_types(self) -> Set[LegendType]:
        """Get the set of currently active legend types.
        
        Returns:
            Set of active legend types
        """
        return self._active_legend_types.copy()
        
    def update_settings(self, settings: Dict[str, Any]) -> None:
        """Update settings and refresh legend states.
        
        Args:
            settings: New settings
        """
        # Update settings manager
        self._settings_manager.update_settings(settings)
        
        # Update legend states
        if self._current_mode:
            self._legend_manager.update_legend_state(self._current_mode)
            self._update_active_legend_types()
            
        # Clear cache when settings change
        self._legend_cache.clear()
        
        # Increment counter for settings update logs
        self._message_counters['settings_update'] += 1
        count_value = self._message_counters['settings_update']
        
        # Log with counter if threshold is reached
        logger.info(f"[LEGEND_GENERATOR] Updated settings: {settings} ({count_value} occurrences since last log)")
        
        # Reset counter if threshold exceeded
        if count_value >= self._log_threshold:
            self._message_counters['settings_update'] = 0
        
    @property
    def legend_manager(self):
        """Get the underlying legend manager.
        
        Returns:
            The legend manager instance
        """
        return self._legend_manager

# Global instance
_legend_generator = None

def get_legend_generator(radar_type: str = 'weather_radar'):
    """Get global LegendGenerator instance."""
    global _legend_generator
    if _legend_generator is None:
        _legend_generator = LegendGenerator(radar_type)
    return _legend_generator
