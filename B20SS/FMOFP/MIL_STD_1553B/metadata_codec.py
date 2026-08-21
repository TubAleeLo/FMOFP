"""
MIL-STD-1553B Metadata Codec

Encodes and decodes metadata fields into MIL-STD-1553B data words.
This allows for preserving rich metadata across the BC-RT boundary
while adhering to the MIL-STD-1553B protocol.
"""

from typing import Dict, List, Any, Tuple
import xml.etree.ElementTree as ET
import os
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.message_schemas import (
    get_schema_for_message_type,
    get_field_position,
    extract_bit_range,
    extract_bits,
    set_bits,
    apply_schema_to_data_words,
    extract_fields_from_data_words,
    MODE_VALUE_MAP,
    MODE_NAME_MAP
)

logger = get_logger()

# Metadata field identifiers (bits 8-15 of first metadata word)
FIELD_MESSAGE_TYPE = 0x01
FIELD_COMMAND_TYPE = 0x02
FIELD_COMMAND_NAME = 0x04
FIELD_MESSAGE_HEADER = 0x08
FIELD_SENDING_SYSTEM = 0x10
FIELD_DESTINATION = 0x20
FIELD_ADDITIONAL_INFO = 0x40
FIELD_ORIGINAL_MESSAGE_TYPE = 0x80
FIELD_PRECIPITATION_DATA = 0x100  # Added for precipitation data payload
FIELD_VIL_DATA = 0x200  # Added for VIL data payload
# To add:
# FIELD_ECHO_TOP_DATA
# FIELD_STORM_CELL_DATA
# FIELD_WEATHER_DATA
# FIELD_TURBULENCE_DATA


# Extended metadata field identifiers (bits 0-7 of second metadata word)
FIELD_MODE = 0x01
FIELD_MODE_VALUE = 0x02  # Properly defined as a separate constant
FIELD_SOURCE_SYSTEM = 0x04
FIELD_REQUEST_ID = 0x08

# Additional extended field identifiers
FIELD_COMMAND_NAME_EXT = 0x10  # Extended command_name storage
FIELD_REQUEST_ID_EXT = 0x20    # Extended request_id storage
FIELD_UUID_STORAGE = 0x40      # Storage for UUIDs and other unique identifiers
FIELD_CRITICAL_STRING = 0x80   # Storage for other critical string values

# Current metadata format version
METADATA_VERSION = 0x01

class MetadataCodec:
    """Encodes and decodes metadata to/from MIL-STD-1553B data words"""

    @staticmethod
    def _load_message_types():
        """Load message types from command registry XML."""
        message_type_map = {}
        try:
            # Path to command registry XML
            current_dir = os.path.dirname(os.path.abspath(__file__))
            PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))
            command_registry_path = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'command_registry.xml')

            tree = ET.parse(command_registry_path)
            root = tree.getroot()

            # Extract message types and assign codes
            code = 1
            for cmd in root.findall('.//command'):
                msg_type = cmd.find('message_type').text
                if msg_type and msg_type not in message_type_map.values():
                    message_type_map[code] = msg_type
                    code += 1

            logger.info(f"Loaded {len(message_type_map)} message types from registry")
            return message_type_map
        except Exception as e:
            logger.error(f"Error loading message types: {e}")
            raise

    @staticmethod
    def _load_command_types():
        """Load command types from command registry XML."""
        command_type_map = {}
        try:
            # Path to command registry XML
            current_dir = os.path.dirname(os.path.abspath(__file__))
            PROJECT_ROOT = os.path.abspath(os.path.join(current_dir, '..', '..'))
            command_registry_path = os.path.join(PROJECT_ROOT, 'FMOFP', 'local_messaging', 'messageConfigurations', 'command_registry.xml')

            tree = ET.parse(command_registry_path)
            root = tree.getroot()

            # Extract unique command_types
            registered_command_types = set()
            for cmd in root.findall('.//command'):
                cmd_type = cmd.find('command_type').text
                if cmd_type:
                    registered_command_types.add(cmd_type)

            # Create indexed map for encoding/decoding
            for index, cmd_type in enumerate(sorted(registered_command_types), start=1):
                command_type_map[index] = cmd_type

            logger.info(f"Loaded {len(command_type_map)} command types from registry")
            return command_type_map
        except Exception as e:
            logger.error(f"Error loading command types: {e}")
            raise

    @staticmethod
    def _encode_position_word(point: Dict[str, Any]) -> Tuple[str, int, int]:
        """
        Encode a data point's (x, y) position into a single 16-bit word,
        scaled to one byte per axis: X in the high byte, Y in the low byte.

        This exact logic was previously duplicated verbatim in both the
        precipitation-data and VIL-data encoding blocks of encode_metadata()
        (the "should be moved into a shared helper" TODO on those blocks
        referred to this). It's extracted here because it's genuinely
        identical between the two - same scaling (x10, one byte per axis),
        same pack order. The rest of each block's value-word encoding
        (precipitation packs type/rate/intensity into 4+6+6 bits; VIL packs
        value/intensity into 10+6 bits) is intentionally NOT merged into a
        single generic helper: the bit layouts genuinely differ per data
        type, and both are decoded byte-for-byte elsewhere (see
        decode_metadata() below) - a generic merge would need to reproduce
        the wire format perfectly for both, and getting it subtly wrong
        would silently corrupt data on the wire rather than fail loudly.
        That risk isn't justified by a code-organization improvement alone.

        Args:
            point: A data point dict, optionally containing a 'position'
                key with a (x, y) tuple/list.

        Returns:
            Tuple of (pos_word_binary_string, x_scaled, y_scaled). x_scaled/
            y_scaled are returned (not just the packed word) because callers
            also use them in their own log messages.
        """
        pos_word = 0
        x_scaled = 0  # Default values in case position is missing
        y_scaled = 0
        if 'position' in point and isinstance(point['position'], (tuple, list)) and len(point['position']) >= 2:
            x, y = point['position']
            x_scaled = int(float(x) * 10) & 0xFF  # Scale and limit to one byte
            y_scaled = int(float(y) * 10) & 0xFF
            pos_word = (x_scaled << 8) | y_scaled
        return format(pos_word, '016b'), x_scaled, y_scaled

    @staticmethod
    def encode_metadata(metadata: Dict[str, Any]) -> List[str]:
        """
        Encode metadata dictionary into a list of 16-bit binary strings using schema.

        Args:
            metadata: Dictionary containing metadata fields

        Returns:
            List of 16-bit binary strings representing encoded metadata
        """
        try:
            # Start with empty list of data words
            data_words = []

            # Track which fields are included
            field_flags = 0
            extended_flags = 0

            # First metadata word: version and field flags (will be updated later)
            data_words.append('0000000000000000')  # Placeholder

            # Use our schema if message_type is provided
            message_type = metadata.get('message_type')
            schema = None

            if message_type:
                schema = get_schema_for_message_type(message_type)
                logger.info(f"Using schema for message type: {message_type}")

                # If we have a schema, encode according to it
                if schema:
                    # Get metadata fields from schema
                    metadata_fields = schema.get('metadata_fields', [])

                    # Mark fields that are included
                    if 'message_type' in metadata_fields:
                        field_flags |= FIELD_MESSAGE_TYPE
                    if 'command_type' in metadata_fields:
                        field_flags |= FIELD_COMMAND_TYPE
                    if 'command_name' in metadata_fields:
                        field_flags |= FIELD_COMMAND_NAME
                    if 'mode' in metadata_fields:
                        extended_flags |= FIELD_MODE
                    if 'request_id' in metadata_fields:
                        extended_flags |= FIELD_REQUEST_ID

            # Process critical fields first

            # Word 1: message_type (8 bits) + command_type (8 bits)
            message_type_code = 0
            command_type_code = 0

            # We'll use simple indexing for message types and command types
            # since we're using a schema-based approach now
            if 'message_type' in metadata and metadata['message_type']:
                field_flags |= FIELD_MESSAGE_TYPE
                msg_type = str(metadata['message_type'])

                # Assign a simple code based on message type
                # This will be 1-127 based on an alphabetical sorting of types
                # For consistency, we'll use well-known types where possible
                known_types = {
                    'weather_radarCommand': 1,
                    'weather_radarModeChangeRequest': 2,
                    'weather_radarModeChangeResponse': 3,
                    'weather_radarStatusRequest': 4,
                    'weather_radarStatusResponse': 5,
                    'weather_radarVILRequest': 6,
                    'weather_radarVILResponse': 7,
                    'weather_radarPrecipitationRequest': 8,
                    'weather_radarPrecipitationResponse': 9,
                    'weather_radarEchoTopRequest': 10,
                    'weather_radarEchoTopResponse': 11,
                    'weather_radarStormCellRequest': 12,
                    'weather_radarStormCellResponse': 13,
                    'tfr_radarModeChangeRequest': 14,
                    'tfr_radarModeChangeResponse': 15,
                    'sar_radarModeChangeRequest': 16,
                    'sar_radarModeChangeResponse': 17,
                    'targeting_radarModeChangeRequest': 18,
                    'targeting_radarModeChangeResponse': 19,
                    'aewc_radarModeChangeRequest': 20,
                    'aewc_radarModeChangeResponse': 21,
                    'display_show_request': 22,
                    'display_mode_request': 23,
                    'display_data_request': 24,
                    'display_mode_response': 25,
                    'displayCommand': 26,
                    'fmsCommand': 27,
                    'display_mode_change': 28,
                    'display_status_word': 29,
                    'flightManagementSystemCommand': 30,

                    # Flight Control System message types
                    'flight_control_systemCommand': 31,
                    'flight_control_systemStatusRequest': 32,
                    'flight_control_systemStatusResponse': 33,
                    'flight_control_systemModeChangeRequest': 34,
                    'flight_control_systemModeChangeResponse': 35,
                    'flight_control_systemControlInputRequest': 36,
                    'flight_control_systemControlInputResponse': 37,
                    'flight_control_systemOrientationDataRequest': 38,
                    'flight_control_systemOrientationDataResponse': 39,

                    # VIL data message handling
                    'display_data': 40,
                    'display_vil_data': 41,  # Add specific type for VIL display data

                    # Targeting Radar message types
                    'targeting_radarCommand': 42,
                    'targeting_radarStatusRequest': 43,
                    'targeting_radarStatusResponse': 44,
                    'targeting_radarTrackRequest': 45,
                    'targeting_radarTrackResponse': 46,

                    # AEWC Radar message types
                    'aewc_radarCommand': 47,
                    'aewc_radarStatusRequest': 48,
                    'aewc_radarStatusResponse': 49,
                    'aewc_radarSectorScanRequest': 50,
                    'aewc_radarSectorScanResponse': 51,

                    # SAR Radar message types
                    'sar_radarCommand': 52,
                    'sar_radarStatusRequest': 53,
                    'sar_radarStatusResponse': 54,
                    'sar_radarStripmapRequest': 55,
                    'sar_radarStripmapResponse': 56,

                    # TFR Radar message types
                    'tfr_radarCommand': 57,
                    'tfr_radarStatusRequest': 58,
                    'tfr_radarStatusResponse': 59,
                    'tfr_radarData': 60,  # Add support for TFR radar data messages
                    'tfr_radarElevationDataRequest': 61,  # Add support for TFR radar elevation data requests
                    'tfr_radarElevationDataResponse': 62,  # Add support for TFR radar elevation data responses

                    # Flight Management System message types
                    'flightManagementSystemStatus': 90,
                    'fms_attitudeUpdateRequest': 91,
                    'fms_attitudeUpdateResponse': 92,
                    'fms_navigationUpdateRequest': 93,
                    'fms_navigationUpdateResponse': 94,

                    # UNKNOWN -> Error
                    'raw_text': 127
                }

                message_type_code = known_types.get(msg_type, 127)  # Default to 127 if not known
                logger.info(f"Assigned message_type code {message_type_code} to '{msg_type}'")

            if 'command_type' in metadata and metadata['command_type']:
                field_flags |= FIELD_COMMAND_TYPE
                cmd_type = str(metadata['command_type'])

                # Assign a simple code based on command type
                known_command_types = {
                    'mode_change': 3,
                    'mode_change_complete': 4,
                    'data_request': 5,
                    'data_response': 6,
                    'status_request': 7,
                    'status_response': 8,
                    'vil_data': 9,
                    'precipitation_data': 10,
                    'system_command': 11,
                    'display_command': 12,
                    'mode_response': 13,
                    'data': 5,  # Map 'data' to same code as 'data_request' for backward compatibility
                    'precipitation': 10  # Map 'precipitation' to same code as 'precipitation_data'
                }

                command_type_code = known_command_types.get(cmd_type, 127)  # Default to 127 if not known
                logger.info(f"Encoded command_type '{cmd_type}' to code {command_type_code}")

            # Require schema-based encoding
            if not message_type:
                raise ValueError("Message type is required for encoding")

            if not schema:
                raise ValueError(f"No schema found for message type: {message_type}")

            # Start with base data words according to schema structure
            schema_data_words = []

            # Word 1: command_type code (high byte) and message_type code (low byte)
            # This ordering matches the expected format in the system
            type_word = (command_type_code << 8) | message_type_code
            schema_data_words.append(format(type_word, '016b'))

            # Create fields dictionary for schema application
            schema_fields = {}

            # Extract fields specified in the schema
            for field_name in schema.get('metadata_fields', []):
                if field_name in metadata:
                    # Special handling for mode - convert from string to numeric value
                    if field_name == 'mode' and isinstance(metadata[field_name], str):
                        mode_name = metadata[field_name].upper()
                        if mode_name in MODE_VALUE_MAP:
                            schema_fields['mode_value'] = MODE_VALUE_MAP[mode_name]
                            logger.info(f"Converted mode '{mode_name}' to value {schema_fields['mode_value']}")
                    else:
                        schema_fields[field_name] = metadata[field_name]

            # Apply schema to transform data words based on schema definition
            schema_data_words = apply_schema_to_data_words(message_type, schema_data_words, schema_fields)

            # Add all schema-based data words to our encoding
            data_words.extend(schema_data_words)
            logger.info(f"Encoded {len(schema_fields)} fields using schema for {message_type}")

            # Word 2: Block transfer info (if applicable)
            transfer_info_word = 0

            # Check if this is a block transfer message
            is_transfer = False
            if any(key in metadata for key in ['is_transfer_init', 'is_transfer_data', 'is_transfer_complete']):
                is_transfer = True

                # Encode transfer type in bits 0-1
                if metadata.get('is_transfer_init'):
                    transfer_info_word |= 1  # 01 = init
                elif metadata.get('is_transfer_data'):
                    transfer_info_word |= 2  # 10 = data
                elif metadata.get('is_transfer_complete'):
                    transfer_info_word |= 3  # 11 = complete

                # Encode total_messages in bits 2-7 (0-63)
                total_messages = min(metadata.get('total_messages', 0), 63)
                transfer_info_word |= (total_messages << 2)

                # Encode total_frames in bits 8-15 (0-255)
                total_frames = min(metadata.get('total_frames', 0), 255)
                transfer_info_word |= (total_frames << 8)

            # Add transfer info word if this is a transfer message
            if is_transfer:
                data_words.append(format(transfer_info_word, '016b'))

            # Word 3: Extended metadata flags and mode information
            mode_word = 0

            # Check for mode information - handle both string and numeric values
            if 'mode' in metadata and metadata['mode'] is not None:
                extended_flags |= FIELD_MODE
                mode_value = metadata['mode']
                mode_handled = False

                # First try mapping mode names to codes using comprehensive radar mode mapping
                if isinstance(mode_value, str):
                    # Comprehensive mode mapping based on RADAR_MODES.md standardization
                    mode_map = {
                        # Universal Base Modes (0-9)
                        'INITIALIZING': -1,
                        'STANDBY': 0,
                        'NORMAL': 1,
                        'DEGRADED': 2,
                        'TEST': 3,
                        'MAINTENANCE': 4,
                        'EMERGENCY': 5,
                        'FAILURE': 6,
                        'RECOVERY': 7,
                        'CALIBRATION': 8,

                        # Weather Radar Modes (10-19)
                        'SURVEILLANCE': 10,
                        'MAPPING': 11,
                        'TURBULENCE': 12,
                        'WINDSHEAR': 13,
                        'PRECIPITATION': 14,
                        'WEATHER': 6,  # Legacy mapping

                        # TFR Radar Modes (20-29)
                        'SEARCH': 20,
                        'TRACK': 21,
                        'ACTIVE': 22,
                        'TERRAIN_FOLLOWING': 23,
                        'OBSTACLE_AVOIDANCE': 24,
                        'GROUND_MAPPING': 25,

                        # SAR Radar Modes (30-39)
                        'STRIPMAP': 30,
                        'SPOTLIGHT': 31,
                        'SCANSAR': 32,
                        'INTERFEROMETRIC': 33,
                        'DOPPLER_BEAM': 34,

                        # Targeting Radar Modes (40-49)
                        'TARGET_SEARCH': 40,
                        'TARGET_TRACK': 41,
                        'LOCK': 42,
                        'TERRAIN_AVOIDANCE': 43,

                        # AEWC Radar Modes (50-59)
                        'AEWC_SEARCH': 50,
                        'AEWC_SURVEILLANCE': 51,
                        'SECTOR_SCAN': 52,
                        'STEALTH_DETECTION': 53,
                        'ELECTRONIC_PROTECTION': 54
                    }

                    # Try to use MODE_VALUE_MAP first for consistency with rest of system
                    if 'MODE_VALUE_MAP' in globals() and mode_value.upper() in MODE_VALUE_MAP:
                        mode_numeric = MODE_VALUE_MAP[mode_value.upper()]
                        mode_word |= mode_numeric
                        mode_handled = True
                        logger.info(f"Used MODE_VALUE_MAP to map mode '{mode_value}' to value {mode_numeric}")
                    else:
                        # Fall back to our comprehensive mode map
                        mode_name = mode_value.upper()
                        if mode_name in mode_map:
                            mode_code = mode_map[mode_name]
                            # For local mode codes, use the low byte
                            mode_word |= (mode_code & 0xFF)
                            mode_handled = True
                            logger.info(f"Mapped mode name '{mode_name}' to code {mode_code}")

                # If not already handled as a string, try as a numeric value
                if not mode_handled:
                    try:
                        # First check if this is a string that matches a named radar mode
                        if isinstance(mode_value, str):
                            # Comprehensive mode mapping based on RADAR_MODES.md standardization
                            mode_map = {
                                # Universal Base Modes (0-9)
                                'INITIALIZING': -1,
                                'STANDBY': 0,
                                'NORMAL': 1,
                                'DEGRADED': 2,
                                'TEST': 3,
                                'MAINTENANCE': 4,
                                'EMERGENCY': 5,
                                'FAILURE': 6,
                                'RECOVERY': 7,
                                'CALIBRATION': 8,

                                # Weather Radar Modes (10-19)
                                'SURVEILLANCE': 10,
                                'MAPPING': 11,
                                'TURBULENCE': 12,
                                'WINDSHEAR': 13,
                                'PRECIPITATION': 14,
                                'WEATHER': 6,  # Legacy mapping

                                # TFR Radar Modes (20-29)
                                'SEARCH': 20,
                                'TRACK': 21,
                                'ACTIVE': 22,
                                'TERRAIN_FOLLOWING': 23,
                                'OBSTACLE_AVOIDANCE': 24,
                                'GROUND_MAPPING': 25,

                                # SAR Radar Modes (30-39)
                                'STRIPMAP': 30,
                                'SPOTLIGHT': 31,
                                'SCANSAR': 32,
                                'INTERFEROMETRIC': 33,
                                'DOPPLER_BEAM': 34,

                                # Targeting Radar Modes (40-49)
                                'TARGET_SEARCH': 40,
                                'TARGET_TRACK': 41,
                                'LOCK': 42,
                                'TERRAIN_AVOIDANCE': 43,

                                # AEWC Radar Modes (50-59)
                                'AEWC_SEARCH': 50,
                                'AEWC_SURVEILLANCE': 51,
                                'SECTOR_SCAN': 52,
                                'STEALTH_DETECTION': 53,
                                'ELECTRONIC_PROTECTION': 54
                            }

                            # Try exact match first
                            if mode_value in mode_map:
                                mode_numeric = mode_map[mode_value] & 0xFF
                                mode_word |= mode_numeric
                                logger.info(f"Mapped mode name '{mode_value}' to numeric value: {mode_numeric}")
                                mode_handled = True
                            # Try uppercase version
                            elif mode_value.upper() in mode_map:
                                mode_numeric = mode_map[mode_value.upper()] & 0xFF
                                mode_word |= mode_numeric
                                logger.info(f"Mapped mode name '{mode_value.upper()}' to numeric value: {mode_numeric}")
                                mode_handled = True

                        # If not already handled as a string mode name, try direct numeric conversion
                        if not mode_handled:
                            # Try to convert to int and use bits 0-7
                            if isinstance(mode_value, (int, float)):
                                mode_numeric = int(mode_value) & 0xFF
                            elif isinstance(mode_value, str) and mode_value.isdigit():
                                # Only convert to int if the string is all digits
                                mode_numeric = int(mode_value) & 0xFF
                            else:
                                logger.error(f"Could not convert mode '{mode_value}' to integer - not a recognized mode name or numeric value")
                                raise ValueError(f"Could not convert mode '{mode_value}' to integer - not a recognized mode name or numeric value")
                            mode_word |= mode_numeric
                            logger.info(f"Used numeric mode value: {mode_numeric}")
                    except (ValueError, TypeError):
                        # If conversion fails, log error
                        logger.error(f"Could not convert mode '{mode_value}' to integer")
                        raise ValueError(f"Could not convert mode '{mode_value}' to integer")

            # ENHANCED: Special handling for command_name as a string
            command_name_encoded = False
            if 'command_name' in metadata and metadata['command_name']:
                # First set the flag indicating command_name is present
                field_flags |= FIELD_COMMAND_NAME

                # Get the command_name as a string
                cmd_name = str(metadata['command_name'])

                # Store the actual command_name string
                # instead of just a hash, to enable perfect reconstruction
                try:
                    # Set flag for extended command_name storage
                    extended_flags |= FIELD_COMMAND_NAME_EXT

                    # Encode the string as bytes, up to 12 chars max (fits in 2 words)
                    # This handles both common command names and longer unique ones
                    if len(cmd_name) > 12:
                        cmd_name = cmd_name[:12]  # Truncate to fit the 12-char
                        # command-name field in the 20-bit 1553B metadata word.
                        # This is a field-width constraint, not a payload limit;
                        # the block transfer path in FMSMessenger handles large
                        # data payloads independently of this encoding step.
                        # raise ValueError("[METADATA_ENCODER] Command name too long, truncated to 12 chars")   # Deal with later, currently have mechanisms to handle command name in flow.

                    # Pad to ensure even length for 16-bit words
                    padded_cmd = cmd_name.ljust(12, '\0')
                    cmd_bytes = padded_cmd.encode('utf-8', errors='ignore')

                    # Encode in two 16-bit words (6 chars each)
                    for i in range(0, 12, 6):
                        chunk = cmd_bytes[i:i+6]
                        if len(chunk) >= 2:  # Ensure at least 2 bytes for first word
                            word_val = (chunk[0] << 8) | chunk[1]
                            data_words.append(format(word_val, '016b'))

                            # If we have more bytes in this chunk, encode them too
                            if len(chunk) >= 4:
                                word_val = (chunk[2] << 8) | chunk[3]
                                data_words.append(format(word_val, '016b'))

                            if len(chunk) == 6:
                                word_val = (chunk[4] << 8) | chunk[5]
                                data_words.append(format(word_val, '016b'))

                    logger.info(f"Encoded command_name as string: '{cmd_name}' (up to 12 chars)")
                    command_name_encoded = True

                except Exception as e:
                    logger.error(f"Error encoding command_name string: {e}")
                    raise

            # ENHANCED: Special handling for request_id - store actual UUID
            request_id_encoded = False
            if 'request_id' in metadata and metadata['request_id']:
                # Set flag for request_id
                extended_flags |= FIELD_REQUEST_ID

                # Get request_id as string
                req_id = str(metadata['request_id'])

                # Try to encode the UUID parts directly
                try:
                    # Set flag for extended UUID storage
                    extended_flags |= FIELD_REQUEST_ID_EXT

                    # For UUIDs like "123e4567-e89b-12d3-a456-426614174000"
                    # Extract portions to encode efficiently
                    if len(req_id) >= 36 and '-' in req_id:
                        # Extract first 4 chars and last 4 chars - often sufficient to uniquely identify
                        prefix = req_id[:4]
                        suffix = req_id[-4:]

                        # Encode prefix and suffix as 16-bit values
                        if len(prefix) == 4:
                            prefix_val = (ord(prefix[0]) << 8) | ord(prefix[1])
                            prefix_val2 = (ord(prefix[2]) << 8) | ord(prefix[3])
                            data_words.append(format(prefix_val, '016b'))
                            data_words.append(format(prefix_val2, '016b'))

                        if len(suffix) == 4:
                            suffix_val = (ord(suffix[0]) << 8) | ord(suffix[1])
                            suffix_val2 = (ord(suffix[2]) << 8) | ord(suffix[3])
                            data_words.append(format(suffix_val, '016b'))
                            data_words.append(format(suffix_val2, '016b'))

                        logger.info(f"Encoded request_id prefix/suffix: {prefix}...{suffix}")
                        request_id_encoded = True
                    else:
                        # For non-UUID format, encode first 8 chars maximum
                        if len(req_id) > 8:
                            req_id = req_id[:8]

                        # Pad to ensure even length for 16-bit words
                        padded_req = req_id.ljust(8, '\0')
                        req_bytes = padded_req.encode('utf-8', errors='ignore')

                        # Encode in two 16-bit words
                        for i in range(0, 8, 2):
                            if i+1 < len(req_bytes):
                                word_val = (req_bytes[i] << 8) | req_bytes[i+1]
                                data_words.append(format(word_val, '016b'))

                        logger.info(f"Encoded request_id string: '{req_id}' (up to 8 chars)")
                        request_id_encoded = True
                except Exception as e:
                    logger.error(f"Error encoding request_id string: {e}")
                    raise

            # Add extended metadata word with updated flags
            if extended_flags > 0:
                # Create extended flags word
                ext_word = (extended_flags << 8) | mode_word
                # Insert this word after the type word (position 2)
                data_words.insert(2, format(ext_word, '016b'))
                logger.info(f"Added extended metadata flags: 0x{extended_flags:02x}")

            # Special handling for precipitation data
            if 'command_type' in metadata and metadata['command_type'] == 'precipitation_data':
                # Set special flag indicating precipitation data is present
                field_flags |= FIELD_PRECIPITATION_DATA

                # precip_data must exist regardless of which branch below
                # runs -- it used to only be initialized inside the "do we
                # have raw precipitation data available" check just below.
                # Any command_type='precipitation_data' metadata dict that
                # doesn't itself embed a raw array under 'data'/'weather'/
                # 'precipitation' (e.g. metadata that just tags a message
                # as precipitation-related without carrying the payload
                # here) skipped that whole block, leaving precip_data
                # unset, and then the logging line further down
                # unconditionally referenced it -- confirmed live:
                # "UnboundLocalError: local variable 'precip_data'
                # referenced before assignment". Initialized up front so
                # it's always defined.
                precip_data = []

                # Check if we have precipitation data available
                if 'data' in metadata or 'weather' in metadata or 'precipitation' in metadata:
                    # Extract precipitation data array

                    # Check for data -> weather -> precipitation structure (common in display messages)
                    if 'data' in metadata and isinstance(metadata['data'], dict):
                        if 'weather' in metadata['data'] and isinstance(metadata['data']['weather'], dict) and 'precipitation' in metadata['data']['weather']:
                            precip_data = metadata['data']['weather']['precipitation']
                            logger.info(f"Found precipitation data in data->weather->precipitation structure")
                    # Check for direct weather -> precipitation structure
                    elif 'weather' in metadata and isinstance(metadata['weather'], dict) and 'precipitation' in metadata['weather']:
                        precip_data = metadata['weather']['precipitation']
                        logger.info(f"Found precipitation data in weather->precipitation structure")
                    # Check for direct precipitation field
                    elif 'precipitation' in metadata:
                        precip_data = metadata['precipitation']
                        logger.info(f"Found precipitation data in direct precipitation field")
                    # Finally fall back to data field (if it's not a dict, it might be the precipitation data directly)
                    elif 'data' in metadata and not isinstance(metadata['data'], dict):
                        precip_data = metadata['data']
                        logger.info(f"Found precipitation data in data field")

                    # Log what we found
                    if isinstance(precip_data, list) and len(precip_data) > 0:
                        logger.info(f"Found {len(precip_data)} precipitation data points to encode")
                    else:
                        logger.warning(f"Precipitation data not in expected format: {type(precip_data)}")
                        if not isinstance(precip_data, list):
                            precip_data = [precip_data]  # Convert to list for consistency

                    # Format: Each precipitation data point needs position, type, rate, intensity
                    for point in precip_data:
                        if isinstance(point, dict):
                            # Encode position X (high byte) and Y (low byte) - scaled integers
                            pos_word_bin, x_scaled, y_scaled = MetadataCodec._encode_position_word(point)
                            data_words.append(pos_word_bin)

                            # Encode type (4 bits), rate (6 bits), and intensity (6 bits)
                            type_code = 0  # Default: rain
                            if 'type' in point:
                                type_map = {'rain': 0, 'snow': 1, 'sleet': 2, 'hail': 3}
                                type_code = type_map.get(str(point['type']).lower(), 0)

                            rate = min(63, int(float(point.get('rate', 0)) / 2))  # Scale 0-126 to 0-63
                            intensity = min(63, int(float(point.get('intensity', 0)) * 63))  # Scale 0-1 to 0-63

                            value_word = (type_code << 12) | (rate << 6) | intensity
                            data_words.append(format(value_word, '016b'))
                            logger.info(f"Encoded precipitation point: position=({x_scaled/10},{y_scaled/10}), type={type_code}, rate={rate*2}, intensity={intensity/63}")

                # Log detailed message about precipitation data encoding
                logger.info(f"Encoded precipitation data with {len(precip_data)} points in {len(data_words)} words")

            # Special handling for VIL data
            if 'command_type' in metadata and metadata['command_type'] == 'vil_data':
                # Set special flag indicating VIL data is present
                field_flags |= FIELD_VIL_DATA

                # Check if we have VIL data available
                if 'data' in metadata or 'weather' in metadata or 'vil_data' in metadata or 'vil' in metadata:
                    # Extract VIL data array
                    vil_data = []

                    # Check for different VIL data storage patterns in metadata
                    if 'data' in metadata and isinstance(metadata['data'], dict):
                        if 'weather' in metadata['data'] and isinstance(metadata['data']['weather'], dict) and 'vil' in metadata['data']['weather']:
                            vil_data = metadata['data']['weather']['vil']
                            logger.info(f"Found VIL data in data->weather->vil structure")
                    # Check for direct weather -> VIL structure
                    elif 'weather' in metadata and isinstance(metadata['weather'], dict) and 'vil' in metadata['weather']:
                        vil_data = metadata['weather']['vil']
                        logger.info(f"Found VIL data in weather->vil structure")
                    # Check for direct vil_data field
                    elif 'vil_data' in metadata:
                        vil_data = metadata['vil_data']
                        logger.info(f"Found VIL data in direct vil_data field")
                    # Check for direct vil field
                    elif 'vil' in metadata:
                        vil_data = metadata['vil']
                        logger.info(f"Found VIL data in direct vil field")
                    # Finally fall back to data field (if it's not a dict, it might be the VIL data directly)
                    elif 'data' in metadata and not isinstance(metadata['data'], dict):
                        vil_data = metadata['data']
                        logger.info(f"Found VIL data in data field")

                    # Log what we found
                    if isinstance(vil_data, list) and len(vil_data) > 0:
                        logger.info(f"Found {len(vil_data)} VIL data points to encode")
                    else:
                        logger.warning(f"VIL data not in expected format: {type(vil_data)}")
                        if not isinstance(vil_data, list):
                            vil_data = [vil_data]  # Convert to list for consistency

                    # Format: Each VIL data point needs position, value, and intensity
                    for point in vil_data:
                        if isinstance(point, dict):
                            # Encode position X (high byte) and Y (low byte) - scaled integers
                            pos_word_bin, x_scaled, y_scaled = MetadataCodec._encode_position_word(point)
                            data_words.append(pos_word_bin)

                            # Encode value (10 bits) and intensity (6 bits)
                            value = min(1023, int(float(point.get('value', 0)) * 10))  # Scale 0-102.3 to 0-1023
                            intensity = min(63, int(float(point.get('intensity', 0)) * 63))  # Scale 0-1 to 0-63

                            value_word = (value << 6) | intensity
                            data_words.append(format(value_word, '016b'))
                            logger.info(f"Encoded VIL point: position=({x_scaled/10},{y_scaled/10}), value={value/10}, intensity={intensity/63}")

                # Log detailed message about VIL data encoding
                logger.info(f"Encoded VIL data with {len(vil_data)} points in {len(data_words)} words")

            # Add metadata verification checksum
            # Create a 16-bit checksum from critical fields
            checksum = 0
            for field in ['command_name', 'message_type', 'command_type', 'request_id']:
                if field in metadata and metadata[field]:
                    # XOR hash of field values for a checksum
                    field_hash = hash(str(metadata[field])) & 0xFFFF
                    checksum ^= field_hash

            # Add checksum as final data word
            data_words.append(format(checksum, '016b'))
            logger.info(f"Added metadata checksum: 0x{checksum:04x}")

            # Update first word with field flags and data word count
            # Version (4 bits) | Data word count (4 bits) | Field flags (8 bits)
            first_word = (METADATA_VERSION << 12) | ((len(data_words) - 1) << 8) | (field_flags & 0xFF)
            data_words[0] = format(first_word, '016b')

            # Log summary
            critical_fields = [f for f in ['command_name', 'message_type', 'command_type', 'request_id']
                              if f in metadata and metadata[f]]
            logger.info(f"Encoded {len(critical_fields)} critical fields: {', '.join(critical_fields)}")

            # Detailed logging of the optimized encoding
            logger.info(f"Optimized metadata encoding: {len(data_words)} data words for {len(metadata)} fields")
            logger.info(f"Field flags: 0x{field_flags:02x}, Extended flags: 0x{extended_flags:02x}")
            return data_words

        except Exception as e:
            logger.error(f"Error encoding metadata: {e}")
            raise

    @staticmethod
    def decode_metadata(data_words: List[str]) -> Dict[str, Any]:
        """
        Decode metadata from a list of 16-bit binary strings.
        Uses schema-based approach for consistent decoding.

        Args:
            data_words: List of 16-bit binary strings representing encoded metadata

        Returns:
            Dictionary containing decoded metadata fields
        """
        try:
            # Check if we have at least one data word
            if not data_words or len(data_words) < 1:
                logger.warning("No metadata data words to decode")
                return {}

            # Strip the 3-bit sync prefix from each data word
            cleaned_data_words = []
            for word in data_words:
                if len(word) >= 3:
                    # Strip the first 3 bits (sync bits) and keep only the actual data
                    cleaned_word = word[3:]
                    # Ensure it's still 16 bits by padding if necessary
                    if len(cleaned_word) < 16:
                        cleaned_word = cleaned_word.zfill(16)
                    cleaned_data_words.append(cleaned_word)
                else:
                    cleaned_data_words.append(word)  # Keep as is if too short

            # Use cleaned data words for all further processing
            data_words = cleaned_data_words

            # Parse first metadata word
            first_word = int(data_words[0], 2)
            version = (first_word >> 12) & 0x0F
            data_word_count = (first_word >> 8) & 0x0F
            field_flags = first_word & 0xFF

            # Verify version
            if version != METADATA_VERSION:
                logger.warning(f"Unsupported metadata version: {version}")
                return {}

            # Check if we have enough data words
            if len(data_words) < data_word_count + 1:  # +1 for header word
                logger.warning(f"Incomplete metadata: expected {data_word_count + 1} words, got {len(data_words)}")
                return {}

            # Initialize metadata dictionary
            metadata = {}

            # Load message type map from registry
            message_type_map = MetadataCodec._load_message_types()

            # Load command type map from registry
            command_type_map = MetadataCodec._load_command_types()

            # Process data words based on their position

            # Word 1: message_type and command_type
            if len(data_words) > 1:
                type_word = int(data_words[1], 2)
                message_type_code = type_word & 0xFF
                command_type_code = (type_word >> 8) & 0xFF

                # For debugging, log the actual values extracted
                logger.info(f"[METADATA_CODEC] Extracted message_type_code: {message_type_code}, command_type_code: {command_type_code}")
                logger.info(f"[METADATA_CODEC] From type_word: {bin(type_word)}")

                # Decode message_type if present
                if field_flags & FIELD_MESSAGE_TYPE:
                    # Use same known_types as in encode_metadata to ensure consistency
                    known_types = {
                        1: 'weather_radarCommand',
                        2: 'weather_radarModeChangeRequest',
                        3: 'weather_radarModeChangeResponse',
                        4: 'weather_radarStatusRequest',
                        5: 'weather_radarStatusResponse',
                        6: 'weather_radarVILRequest',
                        7: 'weather_radarVILResponse',
                        8: 'weather_radarPrecipitationRequest',
                        9: 'weather_radarPrecipitationResponse',
                        10: 'weather_radarEchoTopRequest',
                        11: 'weather_radarEchoTopResponse',
                        12: 'weather_radarStormCellRequest',
                        13: 'weather_radarStormCellResponse',
                        14: 'tfr_radarModeChangeRequest',
                        15: 'tfr_radarModeChangeResponse',
                        16: 'sar_radarModeChangeRequest',
                        17: 'sar_radarModeChangeResponse',
                        18: 'targeting_radarModeChangeRequest',
                        19: 'targeting_radarModeChangeResponse',
                        20: 'aewc_radarModeChangeRequest',
                        21: 'aewc_radarModeChangeResponse',
                        22: 'display_show_request',
                        23: 'display_mode_request',
                        24: 'display_data_request',
                        25: 'display_mode_response',
                        26: 'displayCommand',
                        27: 'fmsCommand',
                        28: 'display_mode_change',
                        29: 'display_status_word',
                        30: 'flightManagementSystemCommand',
                        31: 'flight_control_systemCommand',
                        32: 'flight_control_systemStatusRequest',
                        33: 'flight_control_systemStatusResponse',
                        34: 'flight_control_systemModeChangeRequest',
                        35: 'flight_control_systemModeChangeResponse',
                        36: 'flight_control_systemControlInputRequest',
                        37: 'flight_control_systemControlInputResponse',
                        38: 'flight_control_systemOrientationDataRequest',
                        39: 'flight_control_systemOrientationDataResponse',
                        40: 'display_data',
                        41: 'display_vil_data',
                        42: 'targeting_radarCommand',
                        43: 'targeting_radarStatusRequest',
                        44: 'targeting_radarStatusResponse',
                        45: 'targeting_radarTrackRequest',
                        46: 'targeting_radarTrackResponse',
                        47: 'aewc_radarCommand',
                        48: 'aewc_radarStatusRequest',
                        49: 'aewc_radarStatusResponse',
                        50: 'aewc_radarSectorScanRequest',
                        51: 'aewc_radarSectorScanResponse',
                        52: 'sar_radarCommand',
                        53: 'sar_radarStatusRequest',
                        54: 'sar_radarStatusResponse',
                        55: 'sar_radarStripmapRequest',
                        56: 'sar_radarStripmapResponse',
                        57: 'tfr_radarCommand',
                        58: 'tfr_radarStatusRequest',
                        59: 'tfr_radarStatusResponse',
                        60: 'tfr_radarData',
                        61: 'tfr_radarElevationDataRequest',
                        62: 'tfr_radarElevationDataResponse',
                        90: 'flightManagementSystemStatus',
                        91: 'fms_attitudeUpdateRequest',
                        92: 'fms_attitudeUpdateResponse',
                        93: 'fms_navigationUpdateRequest',
                        94: 'fms_navigationUpdateResponse',
                        127: 'raw_text'  # UNKNOWN -> Error
                    }

                    # FALLBACK: If message_type_code is 0, check if this might be a misalignment
                    # and try alternative approaches
                    if message_type_code == 0:
                        logger.warning(f"[METADATA_CODEC] Found message_type_code 0, attempting fallback methods")

                        # Check if metadata dictionary already has message_type
                        if 'metadata' in metadata and isinstance(metadata['metadata'], dict) and 'message_type' in metadata['metadata']:
                            meta_msg_type = metadata['metadata']['message_type']
                            # Find the code for this message type
                            for code, name in known_types.items():
                                if name == meta_msg_type:
                                    logger.warning(f"[METADATA_CODEC] Using message_type from metadata: {meta_msg_type} (code {code})")
                                    message_type_code = code
                                    break

                        # If still 0, use a safe default
                        if message_type_code == 0:
                            logger.warning("[METADATA_CODEC] Using safe default for message_type_code 0")
                            message_type_code = 28  # display_mode_change - common safe default

                    # First check registry-loaded map
                    if message_type_code in message_type_map:
                        metadata['message_type'] = message_type_map[message_type_code]
                    # Then check hardcoded known types
                    elif message_type_code in known_types:
                        metadata['message_type'] = known_types[message_type_code]
                        logger.info(f"[METADATA_CODEC] Using hardcoded message type mapping for code {message_type_code}: {known_types[message_type_code]}")
                    else:
                        # Log error for unknown message type, but DON'T raise an exception
                        logger.error(f"[METADATA_CODEC] Unknown message type code: {message_type_code}")
                        # Use a safe default instead of throwing an error
                        metadata['message_type'] = 'display_mode_change'
                        logger.warning(f"[METADATA_CODEC] Using safe default message_type: display_mode_change")

                # Decode command_type if present
                if field_flags & FIELD_COMMAND_TYPE:
                    # Handle special command type codes directly
                    special_command_types = {
                        9: 'vil_data',
                        10: 'precipitation_data'
                    }

                    if command_type_code in command_type_map:
                        metadata['command_type'] = command_type_map[command_type_code]
                    elif command_type_code in special_command_types:
                        metadata['command_type'] = special_command_types[command_type_code]
                        logger.info(f"Using special command type mapping for code {command_type_code}: {metadata['command_type']}")
                    else:
                        # Log error for unknown command type
                        logger.error(f"[METADATA_CODEC] Unknown command type code: {command_type_code}")
                        raise ValueError(f"Unknown command type code: {command_type_code}")

            # Word 2: Block transfer info (if applicable)
            current_word = 2
            if len(data_words) > current_word:
                # Check if this is a transfer message by examining the data
                transfer_info_word = int(data_words[current_word], 2)
                transfer_type = transfer_info_word & 0x03  # bits 0-1

                if transfer_type > 0:
                    # This is a transfer message
                    if transfer_type == 1:
                        metadata['is_transfer_init'] = True
                    elif transfer_type == 2:
                        metadata['is_transfer_data'] = True
                    elif transfer_type == 3:
                        metadata['is_transfer_complete'] = True

                    # Extract total_messages from bits 2-7
                    metadata['total_messages'] = (transfer_info_word >> 2) & 0x3F

                    # Extract total_frames from bits 8-15
                    metadata['total_frames'] = (transfer_info_word >> 8) & 0xFF

                    current_word += 1

            # Check for extended metadata word
            if len(data_words) > current_word:
                ext_word = int(data_words[current_word], 2)
                ext_flags = (ext_word >> 8) & 0xFF

                # Check if this is an extended metadata word
                if ext_flags > 0:
                    # Extract mode information if present
                    if ext_flags & FIELD_MODE:
                        mode_code = (ext_word >> 8) & 0x0F
                        # Map mode codes back to names
                        mode_map = {
                            0: 'STANDBY',
                            1: 'SURVEILLANCE',
                            2: 'MAPPING',
                            3: 'TURBULENCE',
                            4: 'WINDSHEAR',
                            5: 'NORMAL',
                            6: 'WEATHER',
                            7: 'TEST'
                        }
                        metadata['mode'] = mode_map.get(mode_code, None)

                    # Extract mode_value if present
                    if ext_flags & FIELD_MODE_VALUE:
                        metadata['mode_value'] = ext_word & 0xFF

                    current_word += 1

            # Word 4 or later: Command name hash (if present)
            if field_flags & FIELD_COMMAND_NAME and len(data_words) > current_word:
                # Store the hash value
                command_name_hash = int(data_words[current_word], 2)
                metadata['command_name_hash'] = command_name_hash
                current_word += 1

                # First check if we can derive command_name from message_type and command_type
                # as the schema system expects this field to be populated
                if 'message_type' in metadata and 'command_type' in metadata:
                    message_type = metadata['message_type']
                    command_type = metadata['command_type']

                    # Get schema for this message type
                    schema = get_schema_for_message_type(message_type)

                    # Check if command_name is required in schema
                    if schema and 'command_name' in schema.get('metadata_fields', []):
                        # Use message type and command type to determine the most likely command name
                        # This approach aligns with how the system processes other metadata fields
                        if 'precipitation' in command_type or 'precipitation' in message_type.lower():
                            metadata['command_name'] = 'DISPLAY_PRECIPITATION_DATA'
                            logger.info(f"Resolved command_name 'DISPLAY_PRECIPITATION_DATA' from message/command type patterns")
                        elif 'vil' in command_type or 'vil' in message_type.lower():
                            metadata['command_name'] = 'DISPLAY_VIL_DATA'
                            logger.info(f"Resolved command_name 'DISPLAY_VIL_DATA' from message/command type patterns")
                        elif 'mode_change' in command_type:
                            # Extract radar type from message type if present
                            radar_type = None
                            for prefix in ['weather', 'tfr', 'sar', 'targeting', 'aewc']:
                                if message_type.lower().startswith(f"{prefix}_"):
                                    radar_type = prefix
                                    break

                            if radar_type:
                                if 'response' in message_type.lower() or 'complete' in command_type:
                                    metadata['command_name'] = f"{radar_type.upper()}_RADAR_MODE_CHANGE_COMPLETE"
                                else:
                                    metadata['command_name'] = f"{radar_type.upper()}_RADAR_MODE_CHANGE"
                                logger.info(f"Resolved command_name '{metadata['command_name']}' from mode change patterns")
                            else:
                                # Default to weather radar
                                metadata['command_name'] = 'WEATHER_RADAR_MODE_CHANGE'
                                logger.info(f"Resolved default command_name 'WEATHER_RADAR_MODE_CHANGE' for mode change")

                # BACKUP METHOD: Check against known command registry values
                if 'command_name' not in metadata:
                    # Import command registry only when needed
                    from FMOFP.local_messaging.command_name_registry import COMMAND_NAMES

                    # Check if the hash matches any known command hex values
                    hash_hex = f"0x{command_name_hash:04X}"
                    for name, info in COMMAND_NAMES.items():
                        if info.get('command_hex') == hash_hex:
                            metadata['command_name'] = name
                            logger.info(f"Resolved command_name '{name}' from direct hex match: {hash_hex}")
                            break

                # FALLBACK METHOD: For specific known hash values from logs
                if 'command_name' not in metadata:
                    hash_to_command = {
                        10: 'DISPLAY_PRECIPITATION_DATA',
                        200: 'DISPLAY_VIL_DATA'
                    }

                    if command_name_hash in hash_to_command:
                        metadata['command_name'] = hash_to_command[command_name_hash]
                        logger.info(f"Resolved command_name '{metadata['command_name']}' from known hash value: {command_name_hash}")

            # Request ID hash (if present)
            if len(data_words) > current_word:
                metadata['request_id_hash'] = int(data_words[current_word], 2)

                # If extended flags indicated a request_id, mark it explicitly
                if ext_flags & FIELD_REQUEST_ID:
                    metadata['has_request_id'] = True

            # Special handling for precipitation data
            if 'command_type' in metadata and metadata['command_type'] == 'precipitation_data':
                # Check if we have enough data words for precipitation data
                if len(data_words) >= 4:  # Need at least header word + type word + a few data words
                    logger.info(f"Detected precipitation data message, attempting to decode data")
                    precipitation_data = []

                    # Skip header, type word, and extended flags if present
                    current_pos = 2
                    if ext_flags > 0:
                        current_pos += 1

                    # Process data words in pairs (position + values)
                    while current_pos + 1 < len(data_words):
                        try:
                            # Extract position data
                            pos_word = int(data_words[current_pos], 2)
                            x_scaled = (pos_word >> 8) & 0xFF
                            y_scaled = pos_word & 0xFF

                            # Convert scaled values back to floats
                            x = x_scaled / 10.0
                            y = y_scaled / 10.0

                            # Extract value data
                            value_word = int(data_words[current_pos + 1], 2)
                            type_code = (value_word >> 12) & 0xF
                            rate = ((value_word >> 6) & 0x3F) * 2  # Scale back to 0-126
                            intensity = (value_word & 0x3F) / 63.0  # Scale back to 0-1

                            # Map type code back to string
                            type_map = {0: 'rain', 1: 'snow', 2: 'sleet', 3: 'hail'}
                            type_str = type_map.get(type_code, 'rain')

                            # Create precipitation data point
                            point = {
                                'position': (x, y),
                                'type': type_str,
                                'rate': rate,
                                'intensity': intensity,
                                'show_values': True  # Default to showing values
                            }

                            precipitation_data.append(point)
                            logger.info(f"Decoded precipitation point: position=({x},{y}), type={type_str}, rate={rate}, intensity={intensity}")

                            current_pos += 2  # Move to next position/value pair
                        except Exception as e:
                            logger.error(f"Error decoding precipitation data point: {e}")
                            current_pos += 2  # Skip this pair and continue

                    # Add precipitation data to metadata
                    if precipitation_data:
                        metadata['precipitation'] = precipitation_data
                        logger.info(f"Successfully decoded {len(precipitation_data)} precipitation data points")
                    else:
                        logger.warning("No precipitation data points were successfully decoded")

            # If we have a message_type, use the schema to extract additional fields
            if 'message_type' in metadata:
                message_type = metadata['message_type']
                logger.info(f"Using schema for message type: {message_type}")

                # Get schema for this message type
                schema = get_schema_for_message_type(message_type)
                if schema:
                    # Extract fields according to schema
                    schema_fields = extract_fields_from_data_words(message_type, data_words)

                    # Merge schema-extracted fields with metadata
                    for field, value in schema_fields.items():
                        if field not in metadata or metadata[field] is None:
                            metadata[field] = value

                    # Extract mode value from last word if applicable
                    if 'mode_value' in schema_fields:
                        mode_value = schema_fields['mode_value']
                        if mode_value in MODE_NAME_MAP:
                            metadata['mode'] = MODE_NAME_MAP[mode_value]
                            logger.info(f"Mapped mode value {mode_value} to mode name '{metadata['mode']}'")

                # Extract command from message if present
                if 'command' in metadata:
                    command_str = metadata['command']
                    if isinstance(command_str, str) and command_str.startswith('set_mode'):
                        # Parse the mode name from "set_mode SURVEILLANCE"
                        parts = command_str.split(' ')
                        if len(parts) > 1:
                            mode_str = parts[1]
                            if mode_str in MODE_VALUE_MAP:
                                metadata['mode_value'] = MODE_VALUE_MAP[mode_str]
                                metadata['mode'] = mode_str
                                logger.info(f"Extracted mode '{mode_str}' (value {metadata['mode_value']}) from command string")

            logger.info(f"Decoded metadata with {len(metadata)} fields")
            return metadata

        except Exception as e:
            logger.error(f"Error decoding metadata: {e}")
            raise

    @staticmethod
    def extract_metadata_words(data_words: List[str]) -> Tuple[List[str], List[str]]:
        """
        Extract metadata words from a list of data words.

        Args:
            data_words: List of all data words

        Returns:
            Tuple of (metadata_words, remaining_words)
        """
        try:
            # Check if we have at least one data word
            if not data_words or len(data_words) < 1:
                return [], data_words

            # Check if first word is a metadata word
            first_word = int(data_words[0], 2)
            version = (first_word >> 12) & 0x0F

            # If not a valid metadata version, assume no metadata
            if version != METADATA_VERSION:
                return [], data_words

            # Extract metadata word count
            data_word_count = (first_word >> 8) & 0x0F

            # Calculate total metadata words (header + data)
            total_metadata_words = 1 + data_word_count

            # Ensure we don't exceed available words
            total_metadata_words = min(total_metadata_words, len(data_words))

            # Split into metadata and remaining words
            metadata_words = data_words[:total_metadata_words]
            remaining_words = data_words[total_metadata_words:]

            return metadata_words, remaining_words

        except Exception as e:
            logger.error(f"Error extracting metadata words: {e}")
            raise
