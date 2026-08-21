"""
Radar Message Format Adapter

Provides utilities for adapting various message formats specifically for radar systems.
Maintains physical separation between Bus Controller and Remote Terminal systems.
"""

import time
import logging
from typing import Any, Dict, Optional, Union, List

from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.radar_command_map import (
    is_weather_data_command,
    get_data_type_from_command,
    WEATHER_DATA_TYPES
)

logger = get_logger()

class RadarMessageAdapter:
    """
    Adapts various message formats for radar systems.
    
    This adapter is specifically designed for radar systems to handle
    message format normalization while maintaining physical separation
    between Bus Controller and Remote Terminal systems.
    """
    
    @staticmethod
    def normalize_message(message: Any) -> Dict[str, Any]:
        """
        Convert any message format to a standard radar message dictionary.
        
        Args:
            message: The message to normalize, can be any type
            
        Returns:
            Dict[str, Any]: A normalized radar message dictionary with standard fields
        """
        try:
            # Initialize standard radar message structure
            normalized = {
                'request_id': None,
                'data': None,
                'message_type': None,
                'command_type': None,
                'timestamp': time.time(),
                'rt_address': None,
                'subaddress': None,
                'metadata': {}
            }
            
            is_precipitation_message = False
            
            # Handle dictionary messages
            if isinstance(message, dict):
                # Copy standard fields directly
                for key in normalized.keys():
                    if key in message:
                        normalized[key] = message[key]
                
                # Extract metadata from various fields
                for meta_field in ['additional_info', 'metadata', 'info']:
                    if meta_field in message and isinstance(message[meta_field], dict):
                        normalized['metadata'].update(message[meta_field])
                        # Check for precipitation_message flag
                        if 'precipitation_message' in message[meta_field]:
                            is_precipitation_message = True
                            logger.info("[RADAR_ADAPTER] Found precipitation_message flag in metadata")
                        # Check for request_id in metadata
                        if 'request_id' in message[meta_field] and (normalized['request_id'] is None):
                            normalized['request_id'] = message[meta_field]['request_id']
                            logger.info(f"[RADAR_ADAPTER] Found request_id in {meta_field}: {normalized['request_id']}")
                        # Check for request_uuid in metadata (used in BaseMessage)
                        if 'request_uuid' in message[meta_field] and (normalized['request_id'] is None):
                            normalized['request_id'] = message[meta_field]['request_uuid']
                            logger.info(f"[RADAR_ADAPTER] Found request_uuid in {meta_field}: {normalized['request_id']}")
                
                # Check for command_name containing PRECIP
                if 'command_name' in message and 'PRECIP' in str(message['command_name']):
                    is_precipitation_message = True
                    logger.info(f"[RADAR_ADAPTER] Found PRECIP in command_name: {message['command_name']}")
                
                # Handle special case for data field
                if 'data' not in message and 'payload' in message:
                    normalized['data'] = message['payload']
                
                # Handle special case for request_id field
                if normalized['request_id'] is None:
                    # Try direct access first (most common case)
                    if 'request_id' in message:
                        normalized['request_id'] = message['request_id']
                        logger.info(f"[RADAR_ADAPTER] Found direct request_id: {normalized['request_id']}")
                    # Check for BaseMessage request_uuid field
                    elif 'request_uuid' in message:
                        normalized['request_id'] = message['request_uuid']
                        logger.info(f"[RADAR_ADAPTER] Found request_uuid: {normalized['request_id']}")
                    # Try alternative field names
                    else:
                        for id_field in ['requestId', 'id', 'uuid', 'message_uuid']:
                            if id_field in message:
                                normalized['request_id'] = message[id_field]
                                logger.info(f"[RADAR_ADAPTER] Found request_id in alternate field '{id_field}': {normalized['request_id']}")
                                break
                
                # Handle special case for message_type field
                if 'message_type' not in message:
                    for type_field in ['messageType', 'type', 'msg_type']:
                        if type_field in message:
                            normalized['message_type'] = message[type_field]
                            break
                    
                    # Try to infer message type from other fields
                    if not normalized['message_type'] and 'message_header' in message:
                        normalized['message_type'] = message['message_header']
                
            # Handle object messages with attributes
            else:
                # Extract standard fields from attributes
                for field in normalized.keys():
                    if hasattr(message, field):
                        normalized[field] = getattr(message, field)
                
                # Extract metadata from various attribute patterns
                for meta_field in ['additional_info', 'metadata', 'info']:
                    if hasattr(message, meta_field):
                        meta_value = getattr(message, meta_field)
                        if isinstance(meta_value, dict):
                            normalized['metadata'].update(meta_value)
                            # Check for precipitation_message flag
                            if 'precipitation_message' in meta_value:
                                is_precipitation_message = True
                                logger.info("[RADAR_ADAPTER] Found precipitation_message flag in metadata attribute")
                            # Check for request_id in metadata
                            if 'request_id' in meta_value and (normalized['request_id'] is None):
                                normalized['request_id'] = meta_value['request_id']
                                logger.info(f"[RADAR_ADAPTER] Found request_id in {meta_field} attribute: {normalized['request_id']}")
                            # Check for request_uuid in metadata (used in BaseMessage)
                            if 'request_uuid' in meta_value and (normalized['request_id'] is None):
                                normalized['request_id'] = meta_value['request_uuid']
                                logger.info(f"[RADAR_ADAPTER] Found request_uuid in {meta_field} attribute: {normalized['request_id']}")
                
                # Check for command_name containing PRECIP
                if hasattr(message, 'command_name') and 'PRECIP' in str(getattr(message, 'command_name', '')):
                    is_precipitation_message = True
                    logger.info(f"[RADAR_ADAPTER] Found PRECIP in command_name attribute: {getattr(message, 'command_name')}")
                
                # Handle special case for data field
                if normalized['data'] is None and hasattr(message, 'payload'):
                    normalized['data'] = getattr(message, 'payload')
                
                # Direct check for request_id attribute first (most common case)
                if normalized['request_id'] is None and hasattr(message, 'request_id'):
                    normalized['request_id'] = getattr(message, 'request_id')
                    logger.info(f"[RADAR_ADAPTER] Found direct request_id attribute: {normalized['request_id']}")
                
                # Check for BaseMessage request_uuid attribute 
                if normalized['request_id'] is None and hasattr(message, 'request_uuid'):
                    normalized['request_id'] = getattr(message, 'request_uuid')
                    logger.info(f"[RADAR_ADAPTER] Found request_uuid attribute: {normalized['request_id']}")
                
                # Try alternative attribute names
                if normalized['request_id'] is None:
                    for id_field in ['requestId', 'id', 'uuid', 'message_uuid']:
                        if hasattr(message, id_field):
                            normalized['request_id'] = getattr(message, id_field)
                            logger.info(f"[RADAR_ADAPTER] Found request_id in alternate attribute '{id_field}': {normalized['request_id']}")
                            break
                
                # Deep search for request_id in object attributes if still not found
                if normalized['request_id'] is None:
                    for attr_name in dir(message):
                        if attr_name.startswith('_') or callable(getattr(message, attr_name)):
                            continue
                        attr_value = getattr(message, attr_name)
                        if isinstance(attr_value, dict) and 'request_id' in attr_value:
                            normalized['request_id'] = attr_value['request_id']
                            logger.info(f"[RADAR_ADAPTER] Found request_id in nested attribute '{attr_name}': {normalized['request_id']}")
                            break
                        elif isinstance(attr_value, dict) and 'request_uuid' in attr_value:
                            normalized['request_id'] = attr_value['request_uuid']
                            logger.info(f"[RADAR_ADAPTER] Found request_uuid in nested attribute '{attr_name}': {normalized['request_id']}")
                            break
                
                # Handle special case for message_type field
                if normalized['message_type'] is None:
                    for type_field in ['messageType', 'type', 'msg_type']:
                        if hasattr(message, type_field):
                            normalized['message_type'] = getattr(message, type_field)
                            break
                    
                    # Try to infer message type from other fields
                    if not normalized['message_type'] and hasattr(message, 'message_header'):
                        normalized['message_type'] = getattr(message, 'message_header')
                
                # Try to infer message type from class name
                if not normalized['message_type'] and hasattr(message, '__class__'):
                    class_name = message.__class__.__name__
                    normalized['message_type'] = class_name
            
            # Set RT address for radar systems if not already set
            if not normalized['rt_address']:
                normalized['rt_address'] = 9  # Default RT address for weather radar
            
            # Set subaddress based on message type if not already set
            if not normalized['subaddress']:
                normalized['subaddress'] = RadarMessageAdapter._infer_subaddress(normalized['message_type'])
            
            # Perform message type inference if still not determined
            if not normalized['message_type']:
                normalized['message_type'] = RadarMessageAdapter._infer_message_type(message)
            
            # Log the normalized message structure
            logger.debug(f"Normalized radar message: {normalized}")
            
            return normalized
            
        except Exception as e:
            raise ValueError(f"Error normalizing radar message: {str(e)}") from e

    
    @staticmethod
    def _infer_message_type(message: Any) -> str:
        """
        Infer message type from message content for radar systems.
        
        Args:
            message: The message to analyze
            
        Returns:
            str: Inferred message type
        """
        # Check if it's a dictionary with specific keys
        if isinstance(message, dict):
            # Check for VIL data indicators
            if any(key.lower() in ['vil', 'vertically', 'liquid'] for key in message.keys()):
                return 'vil_data'
            
            # Check for precipitation data indicators
            if any(key.lower() in ['precip', 'precipitation', 'rain'] for key in message.keys()):
                return 'precipitation_data'
            
            # Check for mode change indicators
            if any(key.lower() in ['mode', 'surveillance', 'mapping', 'standby'] for key in message.keys()):
                return 'mode_change'
            
            # Check for scan parameters
            if 'scan_parameters' in message:
                scan_params = message['scan_parameters']
                if isinstance(scan_params, dict):
                    if 'data_type' in scan_params:
                        data_type = scan_params['data_type'].lower()
                        if 'vil' in data_type:
                            return 'vil_data'
                        elif 'precip' in data_type:
                            return 'precipitation_data'
        
        # Check if it's an object with specific attributes
        else:
            # Get all attributes
            attrs = dir(message)
            
            # Check for VIL data indicators
            if any(attr.lower() in ['vil', 'vertically', 'liquid'] for attr in attrs):
                return 'vil_data'
            
            # Check for precipitation data indicators
            if any(attr.lower() in ['precip', 'precipitation', 'rain'] for attr in attrs):
                return 'precipitation_data'
            
            # Check for mode change indicators
            if any(attr.lower() in ['mode', 'surveillance', 'mapping', 'standby'] for attr in attrs):
                return 'mode_change'
            
            # Check class name
            if hasattr(message, '__class__'):
                class_name = message.__class__.__name__.lower()
                if 'vil' in class_name:
                    return 'vil_data'
                elif 'precip' in class_name:
                    return 'precipitation_data'
                elif 'mode' in class_name:
                    return 'mode_change'
                
            # Check for scan parameters
            if hasattr(message, 'scan_parameters'):
                scan_params = getattr(message, 'scan_parameters')
                if isinstance(scan_params, dict):
                    if 'data_type' in scan_params:
                        data_type = scan_params['data_type'].lower()
                        if 'vil' in data_type:
                            return 'vil_data'
                        elif 'precip' in data_type:
                            return 'precipitation_data'
        
        # Default to unknown if no pattern matched
        return None
    
    @staticmethod
    def _infer_subaddress(message_type: str) -> int:
        """
        Infer subaddress from message type for radar systems.
        
        Args:
            message_type: The message type to analyze
            
        Returns:
            int: Inferred subaddress
        """
        if not message_type:
            return 0
            
        message_type_lower = str(message_type).lower()
        
        # Mode change messages use subaddress 2
        if any(term in message_type_lower for term in ['mode', 'surveillance', 'mapping', 'standby']):
            return 2
            
        # Data messages use subaddress 1
        if any(term in message_type_lower for term in ['data', 'vil', 'precip', 'echo', 'shear', 'turbulence']):
            return 1
            
        # Status messages use subaddress 0
        if any(term in message_type_lower for term in ['status', 'health', 'diagnostic']):
            return 0
            
        # Default to data subaddress
        return 1
    
    @staticmethod
    def is_precipitation_request(message: Any) -> bool:
        """
        Determine if a message is a precipitation data request for radar systems.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a precipitation data request, False otherwise
        """
        # Normalize the message
        normalized = RadarMessageAdapter.normalize_message(message)
        
        # Log the check for debugging
        logger.info(f"[PRECIP_CHECK] Checking if message is precipitation request: {normalized['message_type']}")
        
        # Check command word using radar_command_map
        command_word = normalized.get('command_word')
        if command_word and is_weather_data_command(command_word, 'precipitation'):
            logger.info("[PRECIP_CHECK] Identified as precipitation request by command word pattern")
            return True
            
        # Check if data type from command word is 'precipitation'
        if command_word and get_data_type_from_command(command_word) == 'precipitation':
            logger.info("[PRECIP_CHECK] Identified as precipitation request by data type from command")
            return True
        
        # Check message type - IMPORTANT: Exclude responses to prevent loops
        message_type = normalized['message_type']
        if message_type:
            message_type_str = str(message_type).lower()
            # Check if it contains precipitation terms but is NOT a response
            if (any(term in message_type_str for term in ['precip', 'precipitation', 'rain']) and 
                'response' not in message_type_str):
                logger.info("[PRECIP_CHECK] Identified as precipitation request by message type")
                return True
            # Explicitly reject precipitation responses
            elif 'precip' in message_type_str and 'response' in message_type_str:
                logger.info("[PRECIP_CHECK] Identified as precipitation response, not a request")
                return False
        
        # Check for weather_radarData with RT=9, SA=1, but ensure it's not a response
        if (message_type == 'weather_radarData' and 
            normalized['rt_address'] == 9 and 
            normalized['subaddress'] == 1 and
            normalized['command_type'] == 'data'):
            
            # Check if this is a response by looking for response indicators
            is_response = False
            
            # Check metadata for response indicators
            if normalized['metadata']:
                if 'response' in str(normalized['metadata']).lower():
                    is_response = True
                if 'original_request_id' in normalized['metadata']:
                    is_response = True
            
            # Check additional_info for response indicators
            if isinstance(message, dict) and 'additional_info' in message:
                additional_info = message['additional_info']
                if isinstance(additional_info, dict):
                    if 'response' in str(additional_info).lower():
                        is_response = True
                    if 'original_request_id' in additional_info:
                        is_response = True
            
            # Check for precipitation data in the message
            if hasattr(message, 'precipitation_data') or (isinstance(message, dict) and 'precipitation_data' in message):
                is_response = True
            
            if not is_response:
                logger.info("[PRECIP_CHECK] Identified as potential precipitation request by generic weather radar data pattern")
                return True
            else:
                logger.info("[PRECIP_CHECK] Identified as precipitation response, not a request")
                return False
        
        # Check command type and data type
        if normalized['command_type'] == 'data':
            # Check if data field contains precipitation indicators
            data = normalized['data']
            if isinstance(data, dict) and any(key.lower() in ['precip', 'precipitation', 'rain'] for key in data.keys()):
                logger.info("[PRECIP_CHECK] Identified as precipitation request by data field keys")
                return True
            
            # Check if data has precipitation-related attributes
            if hasattr(data, 'scan_parameters'):
                scan_params = getattr(data, 'scan_parameters')
                if isinstance(scan_params, dict) and 'data_type' in scan_params:
                    is_precip = scan_params['data_type'].lower() in ['precip', 'precipitation', 'rain']
                    if is_precip:
                        logger.info("[PRECIP_CHECK] Identified as precipitation request by scan parameters")
                        return True
        
        # Check metadata
        metadata = normalized['metadata']
        if metadata and any(key.lower() in ['precip', 'precipitation', 'rain'] for key in metadata.keys()):
            logger.info("[PRECIP_CHECK] Identified as precipitation request by metadata keys")
            return True
        
        # Check class name if available
        if hasattr(message, '__class__'):
            class_name = message.__class__.__name__.lower()
            if 'precip' in class_name:
                logger.info(f"[PRECIP_CHECK] Identified as precipitation request by class name: {class_name}")
                return True
        
        # Check the raw message string for precipitation indicators as a last resort
        message_str = str(message).lower()
        if 'precip' in message_str or 'precipitation' in message_str or 'rain' in message_str:
            logger.info("[PRECIP_CHECK] Identified as precipitation request by string content")
            return True
        
        logger.info("[PRECIP_CHECK] Not identified as a precipitation request")
        return False
        
    @staticmethod
    def is_vil_request(message: Any) -> bool:
        """
        Determine if a message is a VIL data request for radar systems.
        
        Args:
            message: The message to check
            
        Returns:
            bool: True if the message is a VIL data request, False otherwise
        """
        # Normalize the message
        normalized = RadarMessageAdapter.normalize_message(message)
        
        # Log the check for debugging
        logger.info(f"[VIL_CHECK] Checking if message is VIL request: {normalized['message_type']}")
        
        # First check if this is a precipitation request - if so, it's not a VIL request
        if RadarMessageAdapter.is_precipitation_request(message):
            logger.info("[VIL_CHECK] Message identified as precipitation request, not VIL")
            return False
        
        # Check command word using radar_command_map
        command_word = normalized.get('command_word')
        if command_word and is_weather_data_command(command_word, 'vil'):
            logger.info("[VIL_CHECK] Identified as VIL request by command word pattern")
            return True
            
        # Check if data type from command word is 'vil'
        if command_word and get_data_type_from_command(command_word) == 'vil':
            logger.info("[VIL_CHECK] Identified as VIL request by data type from command")
            return True
        
        # Check message type - IMPORTANT: Exclude responses to prevent loops
        message_type = normalized['message_type']
        if message_type:
            message_type_str = str(message_type).lower()
            # Check if it contains VIL terms but is NOT a response
            if (any(term in message_type_str for term in ['vil', 'vertically', 'liquid']) and 
                'response' not in message_type_str):
                logger.info("[VIL_CHECK] Identified as VIL request by message type")
                return True
            # Explicitly reject VIL responses
            elif 'vil' in message_type_str and 'response' in message_type_str:
                logger.info("[VIL_CHECK] Identified as VIL response, not a request")
                return False
        
        # Check for weather_radarData with RT=9, SA=1, but ensure it's not a response
        if (message_type == 'weather_radarData' and 
            normalized['rt_address'] == 9 and 
            normalized['subaddress'] == 1 and
            normalized['command_type'] == 'data'):
            
            # Check if this is a response by looking for response indicators
            is_response = False
            
            # Check metadata for response indicators
            if normalized['metadata']:
                if 'response' in str(normalized['metadata']).lower():
                    is_response = True
                if 'original_request_id' in normalized['metadata']:
                    is_response = True
            
            # Check additional_info for response indicators
            if isinstance(message, dict) and 'additional_info' in message:
                additional_info = message['additional_info']
                if isinstance(additional_info, dict):
                    if 'response' in str(additional_info).lower():
                        is_response = True
                    if 'original_request_id' in additional_info:
                        is_response = True
            
            # Check for VIL data in the message
            if hasattr(message, 'vil_data') or (isinstance(message, dict) and 'vil_data' in message):
                is_response = True
            
            if not is_response:
                logger.info("[VIL_CHECK] Identified as potential VIL request by generic weather radar data pattern")
                return True
            else:
                logger.info("[VIL_CHECK] Identified as VIL response, not a request")
                return False
        
        # Check command type and data type
        if normalized['command_type'] == 'data':
            # Check if data field contains VIL indicators
            data = normalized['data']
            if isinstance(data, dict) and any(key.lower() in ['vil', 'vertically', 'liquid'] for key in data.keys()):
                logger.info("[VIL_CHECK] Identified as VIL request by data field keys")
                return True
            
            # Check if data has VIL-related attributes
            if hasattr(data, 'scan_parameters'):
                scan_params = getattr(data, 'scan_parameters')
                if isinstance(scan_params, dict) and 'data_type' in scan_params:
                    is_vil = scan_params['data_type'].lower() in ['vil', 'vertically', 'liquid']
                    if is_vil:
                        logger.info("[VIL_CHECK] Identified as VIL request by scan parameters")
                        return True
        
        # Check metadata
        metadata = normalized['metadata']
        if metadata and any(key.lower() in ['vil', 'vertically', 'liquid'] for key in metadata.keys()):
            logger.info("[VIL_CHECK] Identified as VIL request by metadata keys")
            return True
        
        # Check class name if available
        if hasattr(message, '__class__'):
            class_name = message.__class__.__name__.lower()
            if 'vil' in class_name:
                logger.info(f"[VIL_CHECK] Identified as VIL request by class name: {class_name}")
                return True
        
        # Check for scan parameters
        if hasattr(message, 'scan_parameters'):
            scan_params = getattr(message, 'scan_parameters')
            if isinstance(scan_params, dict):
                # Check for mode parameter indicating surveillance mode (which supports VIL)
                if 'mode' in scan_params and scan_params['mode'].upper() == 'SURVEILLANCE':
                    logger.info("[VIL_CHECK] Identified as VIL request by SURVEILLANCE mode in scan parameters")
                    return True
        
        # Check the raw message string for VIL indicators as a last resort
        message_str = str(message).lower()
        if 'vil' in message_str or 'vertically' in message_str or 'liquid' in message_str:
            logger.info("[VIL_CHECK] Identified as VIL request by string content")
            return True
        
        logger.info("[VIL_CHECK] Not identified as a VIL request")
        return False
    
def get_radar_message_adapter():
    """Get the RadarMessageAdapter singleton instance."""
    return RadarMessageAdapter()
