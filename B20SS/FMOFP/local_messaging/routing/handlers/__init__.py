"""
Special Case Handlers for the Unified Router

These handlers manage special case message types that require custom routing logic.
"""

from FMOFP.local_messaging.routing.handlers.vil_handler import get_vil_handler
from FMOFP.local_messaging.routing.handlers.precipitation_handler import get_precipitation_handler
from FMOFP.local_messaging.routing.handlers.mode_change_handler import get_mode_change_handler
