"""
Factory for creating appropriate radar display instances
"""
from typing import Optional, Dict, Type, List
import traceback
from Systems.radarManagement.radar_enums import (
    RadarMode, weather_radarMode, targeting_radarMode,
    tfr_radarMode, sar_radarMode, aewc_radarMode
)
from .base_radar_display import BaseRadarDisplay
from .weather_radar_display import WeatherRadarDisplay
from .targeting_radar_display import TargetingRadarDisplay
from .tfr_radar_display import TFRRadarDisplay
from .sar_radar_display import SARRadarDisplay
from .aewc_radar_display import AEWCRadarDisplay
from .holographic_radar_display import HolographicRadarDisplay
from ..visual.theme_manager import get_theme_manager
from Utils.logger.sys_logger import get_logger
import time

logger = get_logger()

# Log throttling variables
_last_log_times = {}
_log_throttle_interval = 5.0  # Seconds between similar log messages

def throttled_log(level, message, key=None):
    """
    Log a message with throttling to prevent excessive similar log messages.
    
    Args:
        level: The logging level (e.g., logger.debug, logger.info, logger.warning)
        message: The message to log
        key: Optional key to identify this type of message (defaults to message itself)
    
    Returns:
        True if the message was logged, False if it was throttled
    """
    global _last_log_times
    
    # Use message as key if none provided
    if key is None:
        key = message
        
    current_time = time.time()
    last_time = _last_log_times.get(key, 0)
    
    # Check if enough time has passed since the last similar message
    if current_time - last_time >= _log_throttle_interval:
        # Update the last log time for this message
        _last_log_times[key] = current_time
        
        # Log the message
        level(message)
        return True
    
    return False

class RadarDisplayFactory:
    """Factory for creating and managing radar display instances"""
    
    # Display class mapping
    _display_classes: Dict[Type[RadarMode], Type[BaseRadarDisplay]] = {
        weather_radarMode: WeatherRadarDisplay,
        targeting_radarMode: TargetingRadarDisplay,
        tfr_radarMode: TFRRadarDisplay,
        sar_radarMode: SARRadarDisplay,
        aewc_radarMode: AEWCRadarDisplay
    }
    
    # Cache for display instances
    _display_cache: Dict[Type[RadarMode], BaseRadarDisplay] = {}
    
    @classmethod
    def create_display(cls, mode: RadarMode) -> Optional[BaseRadarDisplay]:
        """Create or retrieve appropriate radar display for the given mode"""
        try:
            # Determine the mode type
            mode_type = type(mode)
            
            # Log the request for debugging (throttled)
            throttled_log(logger.debug, f"Creating radar display for mode: {mode}, type: {mode_type}", 
                         key=f"create_display_{mode_type.__name__}")
            
            # Check theme settings for display type
            theme_manager = get_theme_manager()
            display_type = theme_manager.get_display_type("radar", "standard")
            throttled_log(logger.debug, f"Current radar display type from theme: {display_type}",
                         key="display_type_check")
            
            # Check if we need to clear the cache when switching display types
            if mode_type in cls._display_cache:
                cached_display = cls._display_cache[mode_type]
                
                # If we have a holographic display in cache but theme says standard, clear it
                if isinstance(cached_display, HolographicRadarDisplay) and display_type == "standard":
                    logger.warning(f"Switching to standard display for radar, clearing holographic cache for {mode_type}")
                    cls._display_cache.pop(mode_type, None)
                # If we have a standard display in cache but theme says holographic, clear it
                elif not isinstance(cached_display, HolographicRadarDisplay) and display_type == "holographic":
                    logger.warning(f"Switching to holographic display for radar, clearing standard cache for {mode_type}")
                    cls._display_cache.pop(mode_type, None)
            
            # Check if we're switching between display types
            # If we have a cached display of a different type, clear the cache first
            if mode_type in cls._display_cache:
                cached_display = cls._display_cache[mode_type]
                
                # Check if the cached display matches the current display type
                if ((display_type == "holographic" and not isinstance(cached_display, HolographicRadarDisplay)) or
                    (display_type == "standard" and isinstance(cached_display, HolographicRadarDisplay))):
                    # Display type has changed, clear the cache
                    logger.info(f"Display type changed to {display_type}, clearing cache for {mode_type}")
                    
                    # Properly clean up the cached display before removing it
                    if hasattr(cached_display, 'cleanup'):
                        try:
                            cached_display.cleanup()
                            logger.info(f"Cleaned up cached display for {mode_type}")
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning up cached display: {str(cleanup_error)}")
                    
                    # Remove from cache
                    cls._display_cache.pop(mode_type, None)
                    
                    # Force garbage collection to clean up references
                    import gc
                    gc.collect()
                    logger.info("Forced garbage collection after clearing display cache")
            
            # Check if we need to create a special display based on display type
            if display_type == "holographic":
                # Check if we already have a holographic display in cache
                if mode_type in cls._display_cache:
                    display = cls._display_cache[mode_type]
                    # Check if it's the right type
                    if isinstance(display, HolographicRadarDisplay):
                        throttled_log(logger.debug, f"Retrieved cached holographic display for mode type: {mode_type}",
                                    key=f"retrieved_cached_holo_{mode_type.__name__}")
                        return display
                
                # Create new holographic display
                display = HolographicRadarDisplay()
                cls._display_cache[mode_type] = display
                logger.info(f"Created holographic display for mode type: {mode_type}")
                
                # Ensure the display is properly initialized
                if hasattr(display, 'initialize_display'):
                    try:
                        # Initialize asynchronously if possible
                        import asyncio
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Create a task if loop is running
                            asyncio.create_task(display.initialize_display())
                        else:
                            # Run directly if no loop is running
                            loop.run_until_complete(display.initialize_display())
                        logger.info(f"Initialized holographic display for {mode_type}")
                    except Exception as init_error:
                        logger.error(f"Error initializing holographic display: {str(init_error)}")
                
                return display
            
            # For standard display type, check cache first
            elif mode_type in cls._display_cache:
                display = cls._display_cache[mode_type]
                # Make sure it's not a holographic display
                if not isinstance(display, HolographicRadarDisplay):
                    throttled_log(logger.debug, f"Retrieved cached standard display for mode type: {mode_type}",
                                key=f"retrieved_cached_std_{mode_type.__name__}")
                    return display
                else:
                    # We have a holographic display but need a standard one
                    # Clean up and remove from cache
                    if hasattr(display, 'cleanup'):
                        try:
                            display.cleanup()
                            logger.info(f"Cleaned up holographic display for {mode_type}")
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning up holographic display: {str(cleanup_error)}")
                    
                    # Remove from cache
                    cls._display_cache.pop(mode_type, None)
                    
                    # Force garbage collection
                    import gc
                    gc.collect()
                    logger.info("Forced garbage collection after clearing holographic display")
            
            # Special case for weather radar - use widget directly
            if mode_type == weather_radarMode:
                # Import the widget
                from .weather_radar_widget import get_weather_radar_widget
                
                # Check if we already have a weather radar display in cache
                # If so, we need to ensure it's properly cleaned up before creating a new one
                if mode_type in cls._display_cache:
                    old_display = cls._display_cache[mode_type]
                    throttled_log(logger.debug, f"Found existing weather radar display in cache: {old_display}",
                                key="found_existing_weather_radar")
                    
                    # Check if the display type matches what we need
                    display_type_matches = (
                        (display_type == "holographic" and isinstance(old_display, HolographicRadarDisplay)) or
                        (display_type == "standard" and not isinstance(old_display, HolographicRadarDisplay))
                    )
                    
                    if display_type_matches:
                        # We can reuse the existing display
                        throttled_log(logger.debug, f"Reusing existing {display_type} display for weather radar",
                                    key=f"reusing_{display_type}_weather_radar")
                        return old_display
                    
                    # Remove from cache to ensure we create a fresh instance
                    cls._display_cache.pop(mode_type, None)
                
                # Use the reset functionality to ensure a clean instance
                from .weather_radar_widget import reset_weather_radar_widget, get_weather_radar_widget
                
                # First request a reset
                reset_weather_radar_widget()
                
                # Then get a fresh instance with force_reset=True to ensure it's applied immediately
                widget = get_weather_radar_widget(force_reset=True)
                
                throttled_log(logger.debug, "Created fresh weather radar widget instance",
                            key="created_fresh_weather_radar_widget")
                
                # Initialize if needed
                if not widget.is_running():
                    # Initialize asynchronously
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Create a task if loop is running
                        asyncio.create_task(widget.initialize_display(show_window=False))
                    else:
                        # Run directly if no loop is running
                        loop.run_until_complete(widget.initialize_display(show_window=False))
                
                # Return the widget's display directly
                display = widget.display
                
                # Verify the display type matches what we need
                if display_type == "holographic" and not isinstance(display, HolographicRadarDisplay):
                    # We need a holographic display but got a standard one
                    logger.warning(f"Expected holographic display but got {type(display).__name__}, creating new holographic display")
                    
                    # Create a holographic display
                    from .weather_radar_holographic_display import WeatherRadarHolographicDisplay
                    display = WeatherRadarHolographicDisplay()
                    
                    # Initialize if needed
                    if hasattr(display, 'initialize_display'):
                        try:
                            # Initialize asynchronously
                            import asyncio
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                # Create a task if loop is running
                                asyncio.create_task(display.initialize_display())
                            else:
                                # Run directly if no loop is running
                                loop.run_until_complete(display.initialize_display())
                        except Exception as init_error:
                            logger.error(f"Error initializing holographic display: {str(init_error)}")
                
                elif display_type == "standard" and isinstance(display, HolographicRadarDisplay):
                    # We need a standard display but got a holographic one
                    logger.warning(f"Expected standard display but got {type(display).__name__}, creating new standard display")
                    
                    # Create a standard display
                    from .weather_radar_display import WeatherRadarDisplay
                    display = WeatherRadarDisplay()
                
                # Cache the display
                cls._display_cache[mode_type] = display
                logger.info(f"Created {display_type} display for weather radar mode")
                
                return display
            
            # Create new display instance based on mode type for other radar types
            if mode_type in cls._display_classes:
                display_class = cls._display_classes[mode_type]
                display = display_class()
                
                # Cache the new instance
                cls._display_cache[mode_type] = display
                logger.debug(f"Created new display for mode type: {mode_type}")
                
                return display
            else:
                logger.warning(f"Unknown radar mode type: {mode_type}")
                return None
            
        except Exception as e:
            logger.error(f"Error creating radar display: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    @classmethod
    def clear_cache(cls, mode_type: Optional[Type[RadarMode]] = None):
        """
        Clear the display cache, optionally for a specific mode type.
        
        Args:
            mode_type: Optional specific mode type to clear, or None for all
        """
        try:
            if mode_type is None:
                # Clear entire cache with proper cleanup
                for cached_mode_type, display in list(cls._display_cache.items()):
                    # Call cleanup method if it exists
                    if hasattr(display, 'cleanup'):
                        try:
                            display.cleanup()
                            logger.info(f"Cleaned up display for {cached_mode_type.__name__}")
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning up display: {str(cleanup_error)}")
                            logger.error(traceback.format_exc())
                    
                    # Remove from cache
                    del cls._display_cache[cached_mode_type]
                
                logger.info("Cleared entire radar display cache")
                
                # Reset the weather radar widget
                from .weather_radar_widget import reset_weather_radar_widget
                reset_weather_radar_widget(force_immediate=True)
                logger.info("Forced reset of weather radar widget during cache clear")
                
                # Reset the radar display data coordinator
                from .radar_display_data_coordinator import get_radar_display_data_coordinator
                coordinator = get_radar_display_data_coordinator()
                coordinator.reset_data()
                logger.info("Reset all data in radar display data coordinator during cache clear")
                
                # Force garbage collection
                import gc
                gc.collect()
                logger.info("Forced garbage collection during cache clear")
            else:
                # Clear specific mode type with proper cleanup
                if mode_type in cls._display_cache:
                    display = cls._display_cache[mode_type]
                    
                    # Call cleanup method if it exists
                    if hasattr(display, 'cleanup'):
                        try:
                            display.cleanup()
                            logger.info(f"Cleaned up display for {mode_type.__name__}")
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning up display: {str(cleanup_error)}")
                            logger.error(traceback.format_exc())
                    
                    # Special handling for weather radar
                    if mode_type == weather_radarMode:
                        # Reset the weather radar widget
                        from .weather_radar_widget import reset_weather_radar_widget
                        reset_weather_radar_widget(force_immediate=True)
                        logger.warning("Forced reset of weather radar widget during cache clear")
                        
                        # Reset the radar display data coordinator for weather data
                        from .radar_display_data_coordinator import get_radar_display_data_coordinator
                        coordinator = get_radar_display_data_coordinator()
                        coordinator.reset_data('precipitation')
                        coordinator.reset_data('vil')
                        coordinator.reset_data('cells')
                        logger.warning("Reset weather data in radar display data coordinator during cache clear")
                    
                    # Remove from cache
                    del cls._display_cache[mode_type]
                    logger.warning(f"Cleared radar display cache for {mode_type.__name__}")
                    
                    # Force garbage collection
                    import gc
                    gc.collect()
                    logger.warning(f"Forced garbage collection after clearing cache for {mode_type.__name__}")
        except Exception as e:
            logger.error(f"Error clearing radar display cache: {str(e)}")
            logger.error(traceback.format_exc())

    @classmethod
    def get_supported_modes(cls) -> List[Type[RadarMode]]:
        """Get list of supported radar mode types"""
        try:
            return list(cls._display_classes.keys())
        except Exception as e:
            logger.error(f"Error getting supported modes: {str(e)}")
            return []

    @classmethod
    def is_mode_supported(cls, mode: RadarMode) -> bool:
        """Check if a radar mode type is supported"""
        try:
            return type(mode) in cls._display_classes
        except Exception as e:
            logger.error(f"Error checking mode support: {str(e)}")
            return False

    @classmethod
    def register_display_class(cls, mode_type: Type[RadarMode], 
                             display_class: Type[BaseRadarDisplay]) -> bool:
        """Register a new radar display class for a mode type"""
        try:
            if not issubclass(display_class, BaseRadarDisplay):
                logger.error(f"Display class must inherit from BaseRadarDisplay")
                return False
                
            cls._display_classes[mode_type] = display_class
            logger.debug(f"Registered display class for mode type: {mode_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error registering display class: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    @classmethod
    def unregister_display_class(cls, mode_type: Type[RadarMode]) -> bool:
        """Unregister a radar display class"""
        try:
            if mode_type in cls._display_classes:
                del cls._display_classes[mode_type]
                # Also remove from cache if present
                if mode_type in cls._display_cache:
                    del cls._display_cache[mode_type]
                logger.debug(f"Unregistered display class for mode type: {mode_type}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error unregistering display class: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    @classmethod
    def get_display_class(cls, mode_type: Type[RadarMode]) -> Optional[Type[BaseRadarDisplay]]:
        """Get the display class registered for a mode type"""
        try:
            return cls._display_classes.get(mode_type)
        except Exception as e:
            logger.error(f"Error getting display class: {str(e)}")
            return None

    @classmethod
    def invalidate_cache(cls, mode_type: Optional[Type[RadarMode]] = None):
        """Invalidate cache entries"""
        try:
            if mode_type is None:
                # Invalidate entire cache
                cls.clear_cache()
            elif mode_type in cls._display_cache:
                # Invalidate specific mode type
                del cls._display_cache[mode_type]
                logger.debug(f"Invalidated cache for mode type: {mode_type}")
                
        except Exception as e:
            logger.error(f"Error invalidating cache: {str(e)}")
            logger.error(traceback.format_exc())
