"""
MFD Display Factory

Factory for creating appropriate Multi-Function Display instances
based on the selected display type.
"""

from typing import Optional
import traceback
from .mfd import MultiFunctionDisplay
from .holographic_mfd import HolographicMFD
from .visual.theme_manager import get_theme_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class MFDDisplayFactory:
    """Factory for creating and managing Multi-Function Display instances"""
    
    # Cache for display instance
    _display_instance = None
    _current_display_type = None
    
    @classmethod
    def create_display(cls, parent=None) -> Optional[MultiFunctionDisplay]:
        """Create or retrieve appropriate MFD based on theme settings
        
        Args:
            parent: Optional parent widget for the display
        """
        try:
            # Check theme settings for display type with detailed logging
            theme_manager = get_theme_manager()
            display_type = theme_manager.get_display_type("mfd", "standard")
            logger.info(f"Theme manager returned display type: {display_type} for MFD")
            
            # When a parent is provided, we should always create a new instance
            # since it will be used in a container
            if parent is not None:
                logger.info(f"Creating new MFD display with parent: {parent}")
                cls._display_instance = None
            # Otherwise check if we already have a cached instance of the correct type
            elif cls._display_instance and cls._current_display_type == display_type:
                logger.info(f"Using cached MFD display of type: {display_type}")
                return cls._display_instance
            
            # Create appropriate display based on type
            logger.info(f"Creating new MFD display of type: {display_type}")
            if display_type == "holographic":
                try:
                    display = HolographicMFD(parent=parent)
                    cls._display_instance = display if parent is None else None
                    logger.info("Successfully created HolographicMFD instance")
                except Exception as holographic_error:
                    logger.error(f"Error creating HolographicMFD: {str(holographic_error)}")
                    logger.error(traceback.format_exc())
                    # Fallback to standard MFD
                    display = MultiFunctionDisplay(parent=parent)
                    cls._display_instance = display if parent is None else None
                    logger.info("Falling back to standard MultiFunctionDisplay")
            else:  # Default to standard
                display = MultiFunctionDisplay(parent=parent)
                cls._display_instance = display if parent is None else None
                logger.info("Created standard MultiFunctionDisplay")
                
            # Store the current display type
            cls._current_display_type = display_type
            
            # Initialize the display if it has an initialize method
            if hasattr(display, 'initialize'):
                try:
                    display.initialize()
                    logger.info(f"Initialized {display_type} MFD display")
                except Exception as init_error:
                    logger.error(f"Error initializing {display_type} MFD display: {str(init_error)}")
                    logger.error(traceback.format_exc())
            
            return display
        except Exception as e:
            logger.error(f"Error creating MFD display: {str(e)}")
            logger.error(traceback.format_exc())
            # Fallback to standard MFD
            try:
                fallback_display = MultiFunctionDisplay(parent=parent)
                logger.info("Created fallback MultiFunctionDisplay after error")
                return fallback_display
            except Exception as fallback_error:
                logger.error(f"Error creating fallback display: {str(fallback_error)}")
                logger.error(traceback.format_exc())
                return None
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the display cache"""
        try:
            if cls._display_instance:
                # Call cleanup method if it exists
                if hasattr(cls._display_instance, 'cleanup'):
                    try:
                        cls._display_instance.cleanup()
                        logger.info("Cleaned up MFD display resources")
                    except Exception as cleanup_error:
                        logger.error(f"Error cleaning up MFD display: {str(cleanup_error)}")
                        logger.error(traceback.format_exc())
                
                cls._display_instance = None
                cls._current_display_type = None
                logger.info("MFD display cache cleared")
                
                # Force garbage collection
                import gc
                gc.collect()
                logger.debug("Forced garbage collection after clearing MFD cache")
        except Exception as e:
            logger.error(f"Error clearing MFD display cache: {str(e)}")
            logger.error(traceback.format_exc())
    
    @classmethod
    def invalidate_cache(cls) -> None:
        """Invalidate the display cache"""
        cls.clear_cache()
    
    @classmethod
    def get_current_display_type(cls) -> str:
        """Get the current display type"""
        theme_manager = get_theme_manager()
        return theme_manager.get_display_type("mfd", "standard")
