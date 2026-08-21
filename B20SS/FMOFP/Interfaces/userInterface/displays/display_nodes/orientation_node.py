"""
Orientation Node

Specialized display node for managing flight orientation data.
Provides structured storage and behavior for attitude, position, and velocity.
"""

from typing import Any, Dict, Optional, Union, List
import threading
import time
from .display_node_base import DisplayNode
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class OrientationNode(DisplayNode):
    """Node for managing flight orientation data"""
    
    def __init__(self, name: str, parent: Optional[DisplayNode] = None):
        """Initialize orientation node.
        
        Args:
            name: Node identifier
            parent: Optional parent node
        """
        super().__init__(name, parent)
        
        # Set default values corresponding to FMS structure
        if name == "attitude":
            self.value = {
                'roll': 0,       # Roll angle in degrees
                'pitch': 0,      # Pitch angle in degrees
                'yaw': 0,        # Yaw angle in degrees
                'roll_rate': 0,  # Roll rate in degrees/second
                'pitch_rate': 0, # Pitch rate in degrees/second
                'yaw_rate': 0,   # Yaw rate in degrees/second
            }
        elif name == "position":
            self.value = {
                'latitude': 0,        # Current latitude
                'longitude': 0,       # Current longitude
                'altitude': 0,        # Current altitude in feet
                'heading': 0,         # Current heading in degrees
                'track': 0,           # Ground track in degrees
            }
        elif name == "velocity":
            self.value = {
                'airspeed': 0,        # Aircraft airspeed in knots
                'ground_speed': 0,    # Ground speed in knots
                'vertical_speed': 0,  # Vertical speed in feet/minute
                'mach': 0,            # Mach number
            }
        elif name == "tactical":
            self.value = {
                'g_force': 0,         # Current G-force
                'aoa': 0,             # Angle of attack in degrees
                'sideslip': 0,        # Sideslip angle in degrees
                'energy_state': 0,    # Aircraft energy state
                'mode': 'NORMAL',     # Flight mode: NORMAL, COMBAT, STEALTH, etc.
            }
        
        logger.info(f"[ORIENTATION_NODE] Created node: {name} with default values")
    
    async def set_parameter(self, param_name: str, value: Any) -> None:
        """Set a specific orientation parameter.
        
        Args:
            param_name: Parameter name
            value: Parameter value
        """
        if isinstance(self.value, dict) and param_name in self.value:
            # Create a copy of the current value
            updated_value = self.value.copy()
            # Update the specific parameter
            updated_value[param_name] = value
            # Update the node with the new value
            await self.update(updated_value)
            logger.info(f"[ORIENTATION_NODE] Updated {self.name}.{param_name} to {value}")
        else:
            logger.warning(f"[ORIENTATION_NODE] Invalid parameter: {param_name} for node {self.name}")
    
    async def set_parameters(self, params: Dict[str, Any]) -> None:
        """Set multiple orientation parameters at once.
        
        Args:
            params: Dictionary of parameter name/value pairs
        """
        if isinstance(self.value, dict):
            # Create a copy of the current value
            updated_value = self.value.copy()
            # Update all specified parameters
            valid_updates = 0
            for param_name, value in params.items():
                if param_name in updated_value:
                    updated_value[param_name] = value
                    valid_updates += 1
                else:
                    logger.warning(f"[ORIENTATION_NODE] Ignoring invalid parameter: {param_name}")
            
            # Only update the node if we had valid parameters
            if valid_updates > 0:
                await self.update(updated_value)
                logger.info(f"[ORIENTATION_NODE] Updated {valid_updates} parameters in {self.name}")
        else:
            logger.warning(f"[ORIENTATION_NODE] Node {self.name} value is not a dictionary")
    
    def get_parameter(self, param_name: str) -> Any:
        """Get a specific orientation parameter.
        
        Args:
            param_name: Parameter name
            
        Returns:
            Parameter value or None if not found
        """
        if isinstance(self.value, dict) and param_name in self.value:
            return self.value[param_name]
        return None
