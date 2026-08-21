"""
Flight Control System Completion Message Handler

Handles sending completion notifications for FCS operations,
ensuring proper synchronization between the FCS and other systems.
Follows the MIL-STD-1553B protocol for message formatting and routing.
"""

import time
import uuid
import threading
import traceback
from typing import Dict, Any, Optional

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_sender
from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_address_config
from FMOFP.Systems.flightManagementSys.fms_messaging.message_types import (
    COMMAND_TYPE_CONTROL_INPUT_COMPLETE,
    COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    FCS_CONTROL_INPUT_RESPONSE,
    FCS_MODE_CHANGE_RESPONSE
)

logger = get_logger()

class FCSCompletionMessageHandler:
    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FCSCompletionMessageHandler, cls).__new__(cls)
            return cls._instance
    """
    Handles sending completion notifications for FCS operations.

    This class manages the creation and sending of completion messages
    to inform other systems that an FCS operation has been completed.
    This is critical for maintaining state synchronization between
    systems in accordance with the MIL-STD-1553B protocol requirements.

    The implementation follows the same pattern as the Radar Completion Message Handler
    to ensure consistent communication across all systems.
    """

    def __init__(self):
        """Initialize the FCS completion message handler"""
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.rt_sender = get_rt_sender()
                self.rt_address = None
                self.subaddresses = {}
                self.address_book = {}
                self._load_addresses()
                self.__class__._initialized = True
                logger.info("[FCS_COMP] FCS Completion Message Handler initialized")

    def _load_addresses(self):
        """Load RT addresses from configuration"""
        try:
            rt_config = get_rt_address_config()
            # Get the Flight Management System address from the RT config - use a fixed value of 12 if not found
            self.rt_address = 12  # Known FMS address from address_book.xml

            # Use fixed subaddresses based on address_book.xml
            self.subaddresses = {
                "flight_management": 15,  # FMS Control from address_book.xml
                "flight_control": 10     # Flight Control from address_book.xml
            }

            # Update address book with addresses from config
            self.address_book = {
                "flightmanagementsystem": self.rt_address,
                "display_system": rt_config.get_rt_address('displays')
            }

            logger.info(f"[FCS_COMP] Address book loaded, using RT address {self.rt_address}")
        except Exception as e:
            logger.error(f"[FCS_COMP] Error loading address book: {e}")
            # Fallback to default addresses exactly as in address_book.xml
            self.rt_address = 12  # FMS address from address_book.xml
            self.subaddresses = {
                "flight_management": 15,  # FMS Control from address_book.xml
                "flight_control": 10     # Flight Control from address_book.xml
            }
            self.address_book = {
                "flightmanagementsystem": 12,  # Matches address_book.xml system id
                "display_system": 11           # Display System has address 11
            }
            logger.warning(f"[FCS_COMP] Using fallback address book with RT address {self.rt_address}")

    def set_messenger(self, messenger):
        """
        Legacy method kept for compatibility. RT sender is now used directly.

        Args:
            messenger: The messenger to use
        """
        logger.info("[FCS_COMP] set_messenger called (legacy method - using RT sender directly)")

    def send_completion_message(self,
                               system_name: str,
                               message_type: str,
                               command_type: str,
                               command_name: str,
                               metadata: Dict[str, Any] = None,
                               data: Any = None,
                               request_id: str = None) -> bool:
        """
        Send a completion message to other systems.

        This method formats the completion message according to the MIL-STD-1553B protocol
        and sends it using the RT_sender.

        Args:
            system_name: The name of the system sending the completion message
            message_type: The type of message
            command_type: The type of command
            command_name: The name of the command
            metadata: Additional metadata to include in the message
            data: The data to include in the message
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            if not request_id:
                request_id = str(uuid.uuid4())
                logger.info(f"[FCS_COMP] Generated new request ID: {request_id}")

            logger.info(f"[FCS_COMP] Sending completion message: system={system_name}, type={message_type}")

            # Use FMS RT address as FCS is a subsystem of it
            rt_address = self.rt_address
            logger.info(f"[FCS_COMP] Using FMS RT address {rt_address} for system {system_name}")

            # Use the Flight Control subaddress from the loaded configuration
            sub_address = self.subaddresses["flight_control"]
            logger.info(f"[FCS_COMP] Using flight_control subaddress {sub_address} from configuration")

            logger.info(f"[FCS_COMP] Using RT address {rt_address} and subaddress {sub_address} for system {system_name}")

            # Create a status word with the correct format (20-bit binary string)
            # Format: [sync bits (3)][16 data bits][parity bit (1)]
            # For status word: sync bits = 100

            # Create the 16 data bits
            rt_address_bits = format(rt_address, '05b')  # 5 bits for RT address
            message_error_bit = '0'  # No message error
            instrumentation_bit = '0'  # No instrumentation
            service_request_bit = '0'  # No service request
            reserved_bits = '000'  # Reserved bits
            broadcast_bit = '0'  # Not a broadcast
            busy_bit = '0'  # Not busy
            subsystem_flag_bit = '0'  # No subsystem flag
            dynamic_bus_control_bit = '0'  # No dynamic bus control
            terminal_flag_bit = '0'  # No terminal flag

            # Combine to form the 16 data bits
            data_bits = f"{rt_address_bits}{message_error_bit}{instrumentation_bit}{service_request_bit}{reserved_bits}{broadcast_bit}{busy_bit}{subsystem_flag_bit}{dynamic_bus_control_bit}{terminal_flag_bit}"

            # NOTE: data_bits is always exactly 16 bits (5 rt_address + 11
            # fixed flag bits) so this guard is unreachable in practice - it's
            # a defensive sanity check on the bit-field construction above,
            # not a sign of missing work. An earlier revision of this comment
            # referenced a "TODO" for handling large *data* payloads here,
            # which was misplaced: block-transfer chunking for large payloads
            # is handled upstream in FMSMessenger._route_to_systems() via
            # _send_as_block_transfer(), not in status word construction.
            assert len(data_bits) == 16, (
                f"[FCS_COMP] BUG: status word data_bits has unexpected length "
                f"{len(data_bits)} — check bit-field construction above"
            )

            # Create the status word without parity (3 Sync + 16 data_bits)
            status_word_without_parity = f"100{data_bits}"

            # Calculate parity bit (odd parity)
            # For odd parity, the total number of 1s (including the parity bit) should be odd
            ones_count = status_word_without_parity.count('1')
            parity_bit = '1' if ones_count % 2 == 0 else '0'  # Set to 1 if count is even, 0 if odd
            status_word = status_word_without_parity + parity_bit

            # Verify status word is exactly 20 bits
            if len(status_word) != 20:
                logger.error(f"[FCS_COMP] Invalid status word length: {len(status_word)}")
                raise ValueError("Status word must be 20 bits long")

            logger.info(f"[FCS_COMP] Created status word: {status_word}")

            # Format data for MIL-STD-1553B compatibility
            # Convert to list of integers or binary string
            formatted_data = None
            if data is not None:
                if isinstance(data, int):
                    # Single integer value - convert to list
                    formatted_data = [data]
                elif isinstance(data, list) and all(isinstance(item, int) for item in data):
                    # Already a list of integers
                    formatted_data = data
                elif isinstance(data, str) and all(c in '01' for c in data):
                    # Already a binary string
                    formatted_data = data
                elif isinstance(data, dict):
                    # If data is a dictionary, convert to binary or list
                    try:
                        # Convert to single integer representing the data
                        if 'value' in data and isinstance(data['value'], (int, float)):
                            formatted_data = [int(data['value'])]
                        elif 'mode_value' in data and isinstance(data['mode_value'], (int, float)):
                            formatted_data = [int(data['mode_value'])]
                        else:
                            # Default to 0 if no usable value found
                            formatted_data = [0]
                    except Exception as e:
                        logger.error(f"[FCS_COMP] Error converting dict data: {e}")
                        formatted_data = [0]  # Default value
                else:
                    # Default to 0 if format is unrecognized
                    formatted_data = [0]
            else:
                # If no data provided, use empty list
                formatted_data = []

            logger.info(f"[FCS_COMP] Formatted data for MIL-STD-1553B: {formatted_data}")

            # Create a properly formatted message for RT_sender
            formatted_message = {
                'status_word': status_word,
                'request_id': request_id,
                'command_type': command_type,
                'message_type': message_type,
                'command_name': command_name,
                'timestamp': time.time(),
                'rt_address': rt_address,
                'source': system_name,
                'destination': 'display_system',
                'sub_address': sub_address,
                'data': formatted_data
            }

            # Create metadata with all necessary routing information
            combined_metadata = {
                'system_type': system_name,
                'rt_address': rt_address,
                'subaddress': sub_address,
                'message_type': message_type,
                'command_type': command_type,
                'command_name': command_name,
                'timestamp': time.time(),
                'source': 'fcs_completion_message_handler',
                'destination': 'display_system'
            }

            # Add user-provided metadata if available
            if metadata:
                combined_metadata.update(metadata)

            # Add the combined metadata to the formatted message
            formatted_message['metadata'] = combined_metadata

            # Send the formatted message
            logger.info(f"[FCS_COMP] Sending formatted message: {formatted_message}")
            logger.info(f"[FCS_COMP] Message trace: RT_sender -> BC_Listener -> Bus_Controller -> Unified Router -> Display System")
            send_result = self.rt_sender.RT_send_message(formatted_message)

            if send_result:
                logger.info(f"[FCS_COMP] Completion message sent successfully with request ID: {request_id}")
                return True
            else:
                logger.error(f"[FCS_COMP] Failed to send completion message with request ID: {request_id}")
                return False

        except Exception as e:
            logger.error(f"[FCS_COMP] Error sending completion message: {e}")
            logger.error(traceback.format_exc())
            return False

    def send_control_input_completion(self, system_name: str,
                                     control_type: str,
                                     value: float,
                                     request_id: Optional[str] = None) -> bool:
        """
        Send a control input completion notification

        Args:
            system_name: The name of the system sending the completion (e.g., 'flight_control_system')
            control_type: The type of control input (e.g., 'aileron', 'elevator')
            value: The final value that was set
            request_id: The ID of the original request (if available)

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            logger.info(f"[FCS_COMP] Preparing control input completion notification: {control_type}={value}")

            # Create metadata
            metadata = {
                'control_type': control_type,
                'value': value,
                'system_name': system_name,
                'destination': 'display_system',
                'status': 'SUCCESS',
                'message': f"Control input {control_type} set to {value}"
            }

            # Send completion message using generic completion_message method
            return self.send_completion_message(
                system_name=system_name,
                message_type=FCS_CONTROL_INPUT_RESPONSE,
                command_type=COMMAND_TYPE_CONTROL_INPUT_COMPLETE,
                command_name='FCS_CONTROL_INPUT_COMPLETION',
                metadata=metadata,
                data=int(value) if isinstance(value, (int, float)) else 0,
                request_id=request_id
            )

        except Exception as e:
            logger.error(f"[FCS_COMP] Error sending control input completion: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def send_mode_change_completion(self, system_name: str,
                                   old_mode: str,
                                   new_mode: str,
                                   mode_value: int = None,
                                   request_id: Optional[str] = None) -> bool:
        """
        Send a mode change completion notification

        Args:
            system_name: The name of the system sending the completion (e.g., 'flight_control_system')
            old_mode: The previous mode
            new_mode: The new mode
            mode_value: The numeric value of the new mode (optional)
            request_id: The ID of the original request (if available)

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            logger.info(f"[FCS_COMP] Preparing mode change completion notification: {old_mode} -> {new_mode}")

            # Determine mode value if not provided
            if mode_value is None and new_mode:
                # Map mode name to value
                mode_map = {
                    "NORMAL": 0,
                    "COMBAT": 1,
                    "PRECISION": 2,
                    "AUTOPILOT": 3,
                    "TERRAIN": 4,
                    "EMERGENCY": 5
                }
                mode_value = mode_map.get(new_mode, 0)

            # Create metadata
            metadata = {
                'mode': new_mode,
                'mode_value': mode_value,
                'old_mode': old_mode,
                'new_mode': new_mode,
                'system_name': system_name,
                'destination': 'display_system',
                'force_update': True,
                'update_visual': True,
                'message_purpose': 'mode_change',
                'status': 'SUCCESS',
                'message': f"Mode changed from {old_mode} to {new_mode}"
            }

            # Send completion message using generic completion_message method
            return self.send_completion_message(
                system_name=system_name,
                message_type=FCS_MODE_CHANGE_RESPONSE,
                command_type=COMMAND_TYPE_MODE_CHANGE_COMPLETE,
                command_name='FCS_MODE_CHANGE_COMPLETION',
                metadata=metadata,
                data=mode_value,
                request_id=request_id
            )

        except Exception as e:
            logger.error(f"[FCS_COMP] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def send_orientation_data_completion(self, system_name: str,
                                        data: Dict[str, Any],
                                        request_id: Optional[str] = None) -> bool:
        """
        Send an orientation data response

        Args:
            system_name: The name of the system sending the data (e.g., 'flight_control_system')
            data: The orientation data to send
            request_id: The ID of the original request (if available)

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            logger.info("[FCS_COMP] Preparing orientation data response")

            # Extract numeric data into a list of integers for MIL-STD-1553B compatibility
            numeric_data = []

            # Process the data to extract numeric values into a list
            if isinstance(data, dict):
                # First word is header (e.g., 0x2000 for orientation data)
                numeric_data.append(0x2000)

                # Extract key numeric values (up to 31 more values - MIL-STD-1553B limit)
                for key, value in data.items():
                    if isinstance(value, (int, float)) and len(numeric_data) < 32:
                        # Convert to integer and limit to 16 bits
                        int_value = int(value) & 0xFFFF
                        numeric_data.append(int_value)
                    elif isinstance(value, dict):
                        # Handle nested dictionaries
                        for subkey, subvalue in value.items():
                            if isinstance(subvalue, (int, float)) and len(numeric_data) < 32:
                                # Convert to integer and limit to 16 bits
                                int_value = int(subvalue) & 0xFFFF
                                numeric_data.append(int_value)

            # If no numeric data was extracted, use a default value
            if not numeric_data:
                numeric_data = [0x2000, 0x0000]  # Header + default data

            logger.info(f"[FCS_COMP] Extracted {len(numeric_data)} numeric values from orientation data")

            # Create metadata
            metadata = {
                'data_type': 'orientation_data',
                'system_name': system_name,
                'destination': 'display_system',
                'status': 'SUCCESS',
                'message': "Orientation data response"
            }

            # Send completion message using generic completion_message method
            return self.send_completion_message(
                system_name=system_name,
                message_type='fcs_orientationDataResponse',
                command_type='orientation_data_response',
                command_name='FCS_ORIENTATION_DATA_COMPLETION',
                metadata=metadata,
                data=numeric_data,
                request_id=request_id
            )

        except Exception as e:
            logger.error(f"[FCS_COMP] Error sending orientation data: {str(e)}")
            logger.error(traceback.format_exc())
            return False
# Global instance
_fcs_completion_message_handler = None

def get_fcs_completion_message_handler():
    """
    Get singleton instance of FCS Completion Message Handler

    Returns:
        FCSCompletionMessageHandler: The singleton instance
    """
    global _fcs_completion_message_handler
    if _fcs_completion_message_handler is None:
        _fcs_completion_message_handler = FCSCompletionMessageHandler()
    return _fcs_completion_message_handler
