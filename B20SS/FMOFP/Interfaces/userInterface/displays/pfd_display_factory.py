"""
Factory for creating appropriate Primary Flight Display instances
"""
from typing import Optional
import traceback
from .pfd import PrimaryFlightDisplay
from .holographic_pfd import HolographicPFD
from .futuristic_pfd import FuturisticPFD
from .visual.theme_manager import get_theme_manager
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class PFDDisplayFactory:
    """Factory for creating and managing Primary Flight Display instances"""
    
    # Cache for display instance
    _display_instance = None
    
    # Track the current display type
    _current_display_type = None
    
    @classmethod
    def create_display(cls, parent=None) -> Optional[PrimaryFlightDisplay]:
        """Create or retrieve appropriate Primary Flight Display
        
        Args:
            parent: Optional parent widget for the display
        """
        try:
            # Check theme settings for display type with detailed logging
            theme_manager = get_theme_manager()
            display_type = theme_manager.get_display_type("pfd", "standard")
            logger.info(f"Theme manager returned display type: {display_type} for PFD")
            
            # When a parent is provided, we should always create a new instance
            # since it will be used in a container
            if parent is not None:
                logger.info(f"Creating new PFD display with parent: {parent}")
                cls._display_instance = None
            # Otherwise check if we already have a cached instance of the correct type
            elif cls._display_instance is not None and cls._current_display_type == display_type:
                logger.info(f"Retrieved cached PFD display of type: {display_type}")
                return cls._display_instance
            
            # Create appropriate display based on type
            logger.info(f"Creating new PFD display of type: {display_type}")
            if display_type == "holographic":
                try:
                    # Create holographic display with parent
                    display = HolographicPFD(parent=parent)
                    cls._display_instance = display if parent is None else None
                    cls._current_display_type = display_type
                    logger.info("Successfully created HolographicPFD instance")
                except Exception as holographic_error:
                    logger.error(f"Error creating HolographicPFD: {str(holographic_error)}")
                    logger.error(traceback.format_exc())
                    # Fallback to standard PFD
                    display = PrimaryFlightDisplay(parent=parent)
                    cls._display_instance = display if parent is None else None
                    cls._current_display_type = "standard"
                    logger.info("Falling back to standard PrimaryFlightDisplay")
            else:  # Default to standard
                # Create standard display with parent
                display = PrimaryFlightDisplay(parent=parent)
                cls._display_instance = display if parent is None else None
                cls._current_display_type = "standard"
                logger.info("Created standard PrimaryFlightDisplay")
            
            # Initialize the display if it has an initialize method
            if hasattr(display, 'initialize'):
                try:
                    display.initialize()
                    logger.info(f"Initialized {display_type} PFD display")
                except Exception as init_error:
                    logger.error(f"Error initializing {display_type} PFD display: {str(init_error)}")
                    logger.error(traceback.format_exc())
            
            return display
            
        except Exception as e:
            logger.error(f"Error creating PFD display: {str(e)}")
            logger.error(traceback.format_exc())
            
            # Fallback to standard display
            try:
                display = PrimaryFlightDisplay(parent=parent)
                cls._display_instance = display if parent is None else None
                cls._current_display_type = "standard"
                logger.info("Created fallback standard PFD display after error")
                return display
            except Exception as fallback_error:
                logger.error(f"Error creating fallback PFD display: {str(fallback_error)}")
                logger.error(traceback.format_exc())
                return None

    @classmethod
    def clear_cache(cls):
        """Clear the display cache"""
        try:
            if cls._display_instance is not None:
                # Clean up resources if needed
                if hasattr(cls._display_instance, 'cleanup'):
                    cls._display_instance.cleanup()
                
                cls._display_instance = None
                cls._current_display_type = None
                logger.debug("Cleared PFD display cache")
        except Exception as e:
            logger.error(f"Error clearing PFD display cache: {str(e)}")
            logger.error(traceback.format_exc())

    @classmethod
    def invalidate_cache(cls):
        """Invalidate cache and force recreation on next request"""
        cls.clear_cache()

    @classmethod
    def get_current_display_type(cls) -> str:
        """Get the current display type"""
        try:
            theme_manager = get_theme_manager()
            return theme_manager.get_display_type("pfd", "standard")
        except Exception as e:
            logger.error(f"Error getting current display type: {str(e)}")
            return "standard"
