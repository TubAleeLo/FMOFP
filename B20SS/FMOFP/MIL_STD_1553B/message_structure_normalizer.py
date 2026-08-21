"""
Message Structure Normalizer

Ensures message structures conform to expected schema requirements for routing.
Bridges the gap between aggregated raw data and properly formatted messages.
"""

import traceback
import time
from typing import Dict, List, Any, Optional, Union, Tuple

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.message_schemas import get_schema_for_message_type
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import PrecipitationData

logger = get_logger()

class MessageStructureNormalizer:
    """
    Normalizes message structures to ensure compatibility with routing requirements.
    
    This class ensures that messages have all required fields for:
    1. Routing (rt_address, sub_address)
    2. Schema compliance based on message_type
    3. Proper data structure based on message contents
    """
    
    def __init__(self):
        """Initialize the message structure normalizer."""
        self.logger = get_logger()
        
    def normalize_message_structure(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a message structure to ensure routing compatibility.
        
        Args:
            message: The message to normalize
            
        Returns:
            Dict[str, Any]: A normalized message with all required fields
        """
        try:
            if not isinstance(message, dict):
                self.logger.error(f"[MSG_NORMALIZER] Cannot normalize non-dictionary message: {type(message)}")
                return message
                
            # Create a copy to avoid modifying the original
            normalized = message.copy()
            
            # First, extract message type for schema-specific normalization
            message_type = self._extract_message_type(normalized)
            self.logger.info(f"[MSG_NORMALIZER] Normalizing message of type: {message_type}")
            
            # Add basic logging for request_id tracking
            request_id = normalized.get('request_id')
            if request_id:
                self.logger.info(f"[MSG_NORMALIZER] Processing message with request_id: {request_id}")
            
            # Phase 1: Ensure critical routing fields (rt_address, sub_address)
            self._ensure_routing_fields(normalized)
            
            # Phase 2: Apply schema-specific normalization
            self._apply_schema_normalization(normalized, message_type)
            
            # Phase 3: Ensure proper data structure
            self._ensure_data_structure(normalized, message_type)
            
            # Final check for critical fields
            self._verify_critical_fields(normalized)
            
            return normalized
        except Exception as e:
            self.logger.error(f"[MSG_NORMALIZER] Error normalizing message: {e}")
            self.logger.error(traceback.format_exc())
            return message  # Return original on error
    
    def _extract_message_type(self, message: Dict[str, Any]) -> str:
        """Extract the message type from a message."""
        # Check direct field first
        if 'message_type' in message:
            return message['message_type']
            
        # Check metadata next
        if 'metadata' in message and isinstance(message['metadata'], dict):
            if 'message_type' in message['metadata']:
                return message['metadata']['message_type']
                
        # Detect from message characteristics
        if self._is_precipitation_message(message):
            return 'weather_radarPrecipitationResponse'
            
        if self._is_vil_message(message):
            return 'weather_radarVILResponse'
            
        return 'unknown'
        
    def _is_precipitation_message(self, message: Dict[str, Any]) -> bool:
        """Determine if this is a precipitation data message."""
        # Check direct message type 
        if 'message_type' in message and 'precipitation' in message['message_type'].lower():
            return True
            
        # Check command type
        if 'command_type' in message and 'precipitation' in message['command_type'].lower():
            return True
            
        # Check metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            if 'precipitation_message' in metadata and metadata['precipitation_message']:
                return True
            if 'message_type' in metadata and 'precipitation' in metadata['message_type'].lower():
                return True
            if 'command_type' in metadata and 'precipitation' in metadata['command_type'].lower():
                return True
            if 'data_type' in metadata and metadata['data_type'] == 'precipitation':
                return True
                
        # Check data structure - precipitation data array
        if 'data' in message and isinstance(message['data'], list) and len(message['data']) > 0:
            # Check for position, type, rate, intensity structure which is unique to precipitation
            if all(isinstance(item, dict) for item in message['data'][:5]):
                sample = message['data'][0]
                if 'position' in sample and 'type' in sample and 'rate' in sample:
                    return True
        
        # Check precipitation_data field
        if 'precipitation_data' in message and isinstance(message['precipitation_data'], list):
            return True
            
        return False
        
    def _is_vil_message(self, message: Dict[str, Any]) -> bool:
        """Determine if this is a VIL data message."""
        # First, explicitly exclude mode_change messages
        if 'command_type' in message and message['command_type'] == 'mode_change':
            return False
            
        if 'metadata' in message and isinstance(message['metadata'], dict):
            if 'command_type' in message['metadata'] and message['metadata']['command_type'] == 'mode_change':
                return False
                
        # Check direct message type 
        if 'message_type' in message and 'vil' in message['message_type'].lower():
            return True
            
        # Check command type
        if 'command_type' in message and 'vil' in message['command_type'].lower():
            return True
            
        # Check metadata
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            if 'vil_message' in metadata and metadata['vil_message']:
                return True
            if 'message_type' in metadata and 'vil' in metadata['message_type'].lower():
                return True
            if 'command_type' in metadata and 'vil' in metadata['command_type'].lower():
                return True
            if 'data_type' in metadata and metadata['data_type'] == 'vil':
                return True
                
        # Check data structure - VIL data array
        if 'data' in message and isinstance(message['data'], list) and len(message['data']) > 0:
            # Check for position, value, layer_count structure unique to VIL
            if all(isinstance(item, dict) for item in message['data'][:5]):
                sample = message['data'][0]
                if 'position' in sample and 'value' in sample and 'layer_count' in sample:
                    return True
        
        # Check vil_data field
        if 'vil_data' in message and isinstance(message['vil_data'], list):
            return True
            
        return False
    
    def _ensure_routing_fields(self, message: Dict[str, Any]) -> None:
        """Ensure critical routing fields are present in the message."""
        # Check for rt_address
        if 'rt_address' not in message:
            # Extract from frames if available 
            rt_address = self._extract_rt_address_from_frames(message)
            if rt_address is not None:
                message['rt_address'] = rt_address
                self.logger.info(f"[MSG_NORMALIZER] Extracted rt_address from frames: {rt_address}")
            else:
                # Try to extract from metadata
                rt_address = self._extract_rt_address_from_metadata(message)
                if rt_address is not None:
                    message['rt_address'] = rt_address
                    self.logger.info(f"[MSG_NORMALIZER] Extracted rt_address from metadata: {rt_address}")
                
        # Check for sub_address
        if 'sub_address' not in message:
            sub_address = self._extract_sub_address(message)
            if sub_address is not None:
                message['sub_address'] = sub_address
                self.logger.info(f"[MSG_NORMALIZER] Extracted sub_address: {sub_address}")
                
    def _extract_rt_address_from_frames(self, message: Dict[str, Any]) -> Optional[int]:
        """Extract RT address from frames if available."""
        # Check for frames list
        if 'frames' in message and isinstance(message['frames'], list) and len(message['frames']) > 0:
            # Status word is first frame and starts with '100'
            first_frame = message['frames'][0]
            if isinstance(first_frame, str) and len(first_frame) >= 8 and first_frame.startswith('100'):
                # Extract RT address from bits 3-7 (5 bits for RT address)
                try:
                    rt_address = int(first_frame[3:8], 2)
                    self.logger.info(f"[MSG_NORMALIZER] Extracted RT address {rt_address} from first frame")
                    return rt_address
                except ValueError:
                    self.logger.warning(f"[MSG_NORMALIZER] Failed to parse RT address from first frame: {first_frame}")
        
        # Check status_word if available
        if 'status_word' in message and isinstance(message['status_word'], str) and len(message['status_word']) >= 8:
            status_word = message['status_word']
            if status_word.startswith('100'):
                try:
                    rt_address = int(status_word[3:8], 2)
                    self.logger.info(f"[MSG_NORMALIZER] Extracted RT address {rt_address} from status_word")
                    return rt_address
                except ValueError:
                    self.logger.warning(f"[MSG_NORMALIZER] Failed to parse RT address from status_word: {status_word}")
                    
        # Check status_word dict if available
        if 'status_word' in message and isinstance(message['status_word'], dict) and 'rt_address' in message['status_word']:
            rt_address = message['status_word']['rt_address']
            self.logger.info(f"[MSG_NORMALIZER] Extracted RT address {rt_address} from status_word dictionary")
            return rt_address
            
        return None
    
    def _extract_rt_address_from_metadata(self, message: Dict[str, Any]) -> Optional[int]:
        """Extract RT address from metadata if available."""
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            
            # Direct rt_address field
            if 'rt_address' in metadata:
                return metadata['rt_address']
                
            # Source system field for radar messages
            if self._is_precipitation_message(message) or self._is_vil_message(message):
                # Check source_system or source_rt_address
                if 'source_rt_address' in metadata:
                    return metadata['source_rt_address']
                    
                # Check radar specific fields
                if 'radar_type' in metadata:
                    radar_type = metadata['radar_type']
                    if radar_type == 'weather_radar':
                        return 9  # Weather radar RT address
                
            # Check for embedded status word
            if 'status_word' in metadata and isinstance(metadata['status_word'], dict):
                status_word = metadata['status_word']
                if 'rt_address' in status_word:
                    return status_word['rt_address']
                    
        return None
        
    def _extract_sub_address(self, message: Dict[str, Any]) -> Optional[int]:
        """Extract sub_address from message if available."""
        # Check metadata first
        if 'metadata' in message and isinstance(message['metadata'], dict):
            metadata = message['metadata']
            
            # Check both naming conventions
            if 'sub_address' in metadata:
                return metadata['sub_address']
            elif 'subaddress' in metadata:
                return metadata['subaddress']
            
            # For precipitation data specifically
            if self._is_precipitation_message(message):
                return 1  # Precipitation data uses subaddress 1
                
            # For VIL data specifically  
            if self._is_vil_message(message):
                return 1  # VIL data also uses subaddress 1
                
        return None
        
    def _apply_schema_normalization(self, message: Dict[str, Any], message_type: str) -> None:
        """Apply schema-specific normalization based on message type."""
        # Get schema if available
        schema = get_schema_for_message_type(message_type)
        if not schema:
            self.logger.warning(f"[MSG_NORMALIZER] No schema found for message type: {message_type}")
            return
            
        # Ensure metadata exists
        if 'metadata' not in message:
            message['metadata'] = {}
        elif not isinstance(message['metadata'], dict):
            message['metadata'] = {}
            
        # Ensure all schema metadata fields are present
        for field in schema.get('metadata_fields', []):
            # Check if field exists at top level or in metadata
            if field in message:
                # Mirror to metadata if not there already
                if field not in message['metadata']:
                    message['metadata'][field] = message[field]
            elif field in message['metadata']:
                # Mirror to top level if not there already
                message[field] = message['metadata'][field]
                
        # For precipitation data messages
        if message_type == 'weather_radarPrecipitationResponse':
            # Set default command type if missing
            if 'command_type' not in message:
                message['command_type'] = 'precipitation_data'
                message['metadata']['command_type'] = 'precipitation_data'
                
            # Set default command name if missing
            if 'command_name' not in message:
                message['command_name'] = 'DISPLAY_PRECIPITATION_DATA'
                message['metadata']['command_name'] = 'DISPLAY_PRECIPITATION_DATA'
                
            # Set data_count field if data is available
            if 'data' in message and isinstance(message['data'], list):
                message['data_count'] = len(message['data'])
                message['metadata']['data_count'] = len(message['data'])
                
            # Precipitation-specific flags
            message['metadata']['precipitation_message'] = True
            message['metadata']['precipitation_data'] = True
                
        # For VIL data messages
        elif message_type == 'weather_radarVILResponse':
            # Set default command type if missing
            if 'command_type' not in message:
                message['command_type'] = 'vil_data'
                message['metadata']['command_type'] = 'vil_data'
                
            # Set default command name if missing
            if 'command_name' not in message:
                message['command_name'] = 'DISPLAY_VIL_DATA'
                message['metadata']['command_name'] = 'DISPLAY_VIL_DATA'
                
            # Set data_count field if data is available
            if 'data' in message and isinstance(message['data'], list):
                message['data_count'] = len(message['data'])
                message['metadata']['data_count'] = len(message['data'])
                
            # VIL-specific flags
            message['metadata']['vil_message'] = True
            message['metadata']['vil_data_available'] = True
    
    def _ensure_data_structure(self, message: Dict[str, Any], message_type: str) -> None:
        """Ensure proper data structure based on message type."""
        if message_type == 'weather_radarPrecipitationResponse':
            self._normalize_precipitation_data(message)
        elif message_type == 'weather_radarVILResponse':
            self._normalize_vil_data(message)
            
    def _normalize_precipitation_data(self, message: Dict[str, Any]) -> None:
        """Normalize precipitation data structure."""
        # Handle case where data is absent
        if 'data' not in message or not message['data']:
            message['data'] = []
            return
            
        original_data = message['data']
        normalized_data = []
        
        # Check if we need to normalize the data structure
        if all(isinstance(item, PrecipitationData) for item in original_data):
            # Already properly formatted
            return
            
        # Convert dict objects to proper structure
        for item in original_data:
            if isinstance(item, dict):
                if 'position' in item and 'type' in item:
                    # Extract required fields
                    position = item.get('position', (0.0, 0.0))
                    if not isinstance(position, tuple) and isinstance(position, list):
                        position = tuple(position)  # Convert list to tuple if needed
                        
                    precip_type = item.get('type', 'rain')
                    rate = float(item.get('rate', 0.0))
                    intensity = float(item.get('intensity', 0.0))
                    show_values = bool(item.get('show_values', False))
                    
                    # Create standardized data object
                    normalized_data.append({
                        'position': position,
                        'type': precip_type,
                        'rate': rate,
                        'intensity': intensity,
                        'show_values': show_values
                    })
            
        # Update the message with normalized data if we have any
        if normalized_data:
            message['data'] = normalized_data
            message['data_count'] = len(normalized_data)
            message['metadata']['data_count'] = len(normalized_data)
            message['metadata']['precipitation_data_normalized'] = True
    
    def _normalize_vil_data(self, message: Dict[str, Any]) -> None:
        """Normalize VIL data structure."""
        # Similar to precipitation but for VIL data - less critical for our current issue
        pass
        
    def _verify_critical_fields(self, message: Dict[str, Any]) -> None:
        """Verify that critical fields are present in the normalized message."""
        # Check for rt_address
        if 'rt_address' not in message:
            self.logger.warning("[MSG_NORMALIZER] Critical routing field rt_address still missing after normalization")
            
        # Check for sub_address
        if 'sub_address' not in message:
            self.logger.warning("[MSG_NORMALIZER] Critical routing field sub_address still missing after normalization")
            
        # Check if this is a precipitation data message that might be incorrectly marked as transfer_complete
        is_precipitation_message = self._is_precipitation_message(message)
        
        # Special handling for transfers that should NOT be marked as transfer_complete
        if message.get('is_transfer_complete') and is_precipitation_message:
            # Ensure precipitation data command_type is preserved (don't set to 'transfer_complete')
            if message.get('command_type') == 'transfer_complete':
                # Restore to precipitation_data
                message['command_type'] = 'precipitation_data'
                if 'metadata' in message and isinstance(message['metadata'], dict):
                    message['metadata']['command_type'] = 'precipitation_data'
                self.logger.info(f"[MSG_NORMALIZER] Preserved precipitation data command_type (not using transfer_complete)")
        
        # Log successful normalization
        self.logger.info("[MSG_NORMALIZER] Message normalization complete")
        if 'rt_address' in message:
            self.logger.info(f"[MSG_NORMALIZER] rt_address: {message['rt_address']}")
        if 'sub_address' in message:
            self.logger.info(f"[MSG_NORMALIZER] sub_address: {message['sub_address']}")
        if 'message_type' in message:
            self.logger.info(f"[MSG_NORMALIZER] message_type: {message['message_type']}")
        if 'command_type' in message:
            self.logger.info(f"[MSG_NORMALIZER] command_type: {message['command_type']}")
        if 'command_name' in message:
            self.logger.info(f"[MSG_NORMALIZER] command_name: {message['command_name']}")
        if 'data' in message and isinstance(message['data'], list):
            self.logger.info(f"[MSG_NORMALIZER] data_count: {len(message['data'])}")

# Singleton instance
_message_structure_normalizer = None

def get_message_structure_normalizer():
    """Get the singleton instance of MessageStructureNormalizer."""
    global _message_structure_normalizer
    if _message_structure_normalizer is None:
        _message_structure_normalizer = MessageStructureNormalizer()
    return _message_structure_normalizer
