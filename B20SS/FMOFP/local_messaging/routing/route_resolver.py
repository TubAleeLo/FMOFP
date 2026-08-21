"""
Route Resolver

Determines message destinations based on routing rules.
Handles special cases like VIL data, precipitation data, and mode changes.
"""

import traceback
from typing import Dict, Any, Optional, List, Tuple, Union

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.local_messaging.routing.routing_registry import get_routing_registry

logger = get_logger()

class RouteResolver:
    def __init__(self, routing_registry=None):
        self.routing_registry = routing_registry or get_routing_registry()
        self.logger = get_logger()
        logger.info("RouteResolver initialized")
        
    def resolve_routes(self, message: Union[Dict[str, Any], Any]) -> List[str]:
        """
        Resolve routes for a message.
        
        Args:
            message: The message to resolve routes for
            
        Returns:
            List[str]: List of destination system IDs
        """
        try:
            destinations = []
            
            # Check for special cases first
            special_case_destinations = self._resolve_special_cases(message)
            if special_case_destinations:
                return special_case_destinations
                
            # Check RT address-based routing
            rt_destinations = self._resolve_by_rt_address(message)
            destinations.extend(rt_destinations)
            
            # Check content-based routing
            content_destinations = self._resolve_by_content(message)
            for dest in content_destinations:
                if dest not in destinations:
                    destinations.append(dest)
                    
            return destinations
        except Exception as e:
            self.logger.error(f"Error resolving routes: {e}")
            self.logger.error(traceback.format_exc())
            return []
        
    def _resolve_special_cases(self, message: Union[Dict[str, Any], Any]) -> Optional[List[str]]:
        """
        Resolve routes for special cases.
        
        Args:
            message: The message to resolve routes for
            
        Returns:
            Optional[List[str]]: List of destination system IDs, or None if not a special case
        """
        # Get message type and command name
        message_type = None
        command_name = None
        
        if isinstance(message, dict):
            message_type = message.get('message_type')
            command_name = message.get('command_name')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            if hasattr(message, 'command_name'):
                command_name = message.command_name
        
        # Check if message type is in special cases
        if message_type:
            for case_id, case in self.routing_registry.special_cases.items():
                if message_type in case['message_types']:
                    self.logger.info(f"Special case found for message type: {message_type}")
                    return case['destinations']
        
        # Check if command name is in special cases
        if command_name:
            for case_id, case in self.routing_registry.special_cases.items():
                if 'command_names' in case and command_name in case['command_names']:
                    self.logger.info(f"Special case found for command name: {command_name}")
                    return case['destinations']

                    
        return None
        
    def _resolve_by_rt_address(self, message: Union[Dict[str, Any], Any]) -> List[str]:
        """
        Resolve routes based on RT address.
        
        Args:
            message: The message to resolve routes for
            
        Returns:
            List[str]: List of destination system IDs
        """
        destinations = []
        
        # Get RT address
        rt_address = None
        if isinstance(message, dict):
            rt_address = message.get('rt_address')
        elif hasattr(message, 'rt_address'):
            rt_address = message.rt_address
            
        if rt_address is None:
            self.logger.error(f"Message has no RT address")
            return destinations
            
        # Get system ID
        system_id = self.routing_registry.get_system_by_rt_address(rt_address)
        if not system_id:
            self.logger.error(f"Invalid RT address: {rt_address}")
            return destinations
        
        # Log routing details for debugging    
        self.logger.info(f"Resolving route for RT address {rt_address}, system ID: {system_id}")
            
        # Map system ID to destination
        if system_id == 'radar':
            destinations.append('radar')
        elif system_id == 'displays':
            destinations.append('display')
        elif system_id == 'flightmanagementsystem' or system_id == 'flightManagementSystem':
            # Send to the flightmanagementsystem queue for consistency
            destinations.append('flightmanagementsystem')
            self.logger.info(f"FMS message detected with RT address {rt_address}, routing to 'flightmanagementsystem'")
        else:
            destinations.append(system_id)
            
        return destinations
        
    def _resolve_by_content(self, message: Union[Dict[str, Any], Any]) -> List[str]:
        """
        Resolve routes based on message content.
        
        Args:
            message: The message to resolve routes for
            
        Returns:
            List[str]: List of destination system IDs
        """
        destinations = []
        
        # Check message type
        message_type = None
        if isinstance(message, dict):
            message_type = message.get('message_type')
        elif hasattr(message, 'message_type'):
            message_type = message.message_type
            
        if message_type:
            # Check for exact system prefixes in message type
            system_prefixes = {
                'radar': ['radar_', 'weather_radar_', 'tfr_radar_', 'sar_radar_', 'targeting_radar_', 'aewc_radar_'],
                'display': ['display_', 'displays_'],
                'flightmanagementsystem': ['fms_', 'flightManagementSystem', 'flightmanagementsystem']
            }
            
            for system, prefixes in system_prefixes.items():
                for prefix in prefixes:
                    if isinstance(message_type, str) and (message_type.startswith(prefix) or prefix in message_type.lower()):
                        if system not in destinations:
                            destinations.append(system)
                            self.logger.info(f"Routing to {system} based on message type prefix/match: {prefix}")
                            break
                    
        # Check command name
        command_name = None
        if isinstance(message, dict):
            command_name = message.get('command_name')
        elif hasattr(message, 'command_name'):
            command_name = message.command_name
            
        if command_name:
            # Check for exact system prefixes in command name
            system_prefixes = {
                'radar': ['RADAR_', 'WEATHER_RADAR_', 'TFR_RADAR_', 'SAR_RADAR_', 'TARGETING_RADAR_', 'AEWC_RADAR_'],
                'display': ['DISPLAY_', 'DISPLAYS_'],
                'flightmanagementsystem': ['FMS_', 'FLIGHT_MANAGEMENT_']
            }
            
            for system, prefixes in system_prefixes.items():
                for prefix in prefixes:
                    if command_name.startswith(prefix):
                        if system not in destinations:
                            destinations.append(system)
                            self.logger.info(f"Routing to {system} based on command name prefix: {prefix}")
                            break
                    
        # Check metadata for additional routing information
        metadata = None
        if isinstance(message, dict) and 'metadata' in message:
            metadata = message['metadata']
        elif hasattr(message, 'metadata'):
            metadata = message.metadata
            
        if metadata and isinstance(metadata, dict):
            # Check for explicit destination
            if 'destination' in metadata:
                dest = metadata['destination']
                if dest == 'radar_handler' or dest == 'radar_system' or dest == 'weather_radar':
                    if 'radar' not in destinations:
                        destinations.append('radar')
                        self.logger.info(f"Routing to radar based on metadata destination: {dest}")
                elif dest == 'display_handler' or dest == 'display_system':
                    if 'display' not in destinations:
                        destinations.append('display')
                        self.logger.info(f"Routing to display based on metadata destination: {dest}")
                elif dest == 'flightmanagementsystem' or dest == 'flightManagementSystem' or dest == 'fms_handler' or dest == 'fms_system':
                    if 'flightmanagementsystem' not in destinations:
                        destinations.append('flightmanagementsystem')
                        self.logger.info(f"Routing to flightmanagementsystem based on metadata destination: {dest}")
                        
            # Check for source system
            if 'source_system' in metadata:
                source = metadata['source_system']
                if source == 'weather_radar':
                    if 'radar' not in destinations:
                        destinations.append('radar')
                elif source == 'display_system':
                    if 'display' not in destinations:
                        destinations.append('display')
                elif source == 'flightmanagementsystem' or source == 'flightManagementSystem' or source == 'fms':
                    if 'flightmanagementsystem' not in destinations:
                        destinations.append('flightmanagementsystem')
                        self.logger.info(f"Routing to flightmanagementsystem based on metadata source: {source}")
                        
        return destinations

def get_route_resolver():
    """Get a new instance of RouteResolver."""
    return RouteResolver()
