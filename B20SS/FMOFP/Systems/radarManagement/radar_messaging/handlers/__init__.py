"""
Package for standardized radar message handlers.
"""

# Import handlers for easy access
from FMOFP.Systems.radarManagement.radar_messaging.handlers.vil_data_handler import VILDataHandler
from FMOFP.Systems.radarManagement.radar_messaging.handlers.precipitation_data_handler import PrecipitationDataHandler
from FMOFP.Systems.radarManagement.radar_messaging.handlers.mode_change_handler import ModeChangeHandler

# Handler instances
_vil_data_handler = None
_precipitation_data_handler = None
_mode_change_handler = None

def get_vil_data_handler(radar_db=None):
    """
    Get or create the singleton VIL data handler.
    
    Args:
        radar_db: Optional radar database reference
        
    Returns:
        VILDataHandler: The singleton instance
    """
    global _vil_data_handler
    if _vil_data_handler is None:
        _vil_data_handler = VILDataHandler(radar_db)
    return _vil_data_handler

def get_precipitation_data_handler(radar_db=None):
    """
    Get or create the singleton precipitation data handler.
    
    Args:
        radar_db: Optional radar database reference
        
    Returns:
        PrecipitationDataHandler: The singleton instance
    """
    global _precipitation_data_handler
    if _precipitation_data_handler is None:
        _precipitation_data_handler = PrecipitationDataHandler(radar_db)
    return _precipitation_data_handler

def get_mode_change_handler():
    """
    Get or create the singleton mode change handler.
    
    Returns:
        ModeChangeHandler: The singleton instance
    """
    global _mode_change_handler
    if _mode_change_handler is None:
        _mode_change_handler = ModeChangeHandler()
    return _mode_change_handler

def register_handlers(router, radar_db=None):
    """
    Register all handlers with the unified router.
    
    Args:
        router: The router to register handlers with
        radar_db: Optional radar database reference
        
    Returns:
        list: The registered handlers
    """
    handlers = [
        get_vil_data_handler(radar_db),
        get_precipitation_data_handler(radar_db),
        get_mode_change_handler()
    ]
    
    # Register with router if provided
    if router:
        for handler in handlers:
            router.register_handler(handler)
            
    return handlers
