"""
FMS Completion Message Handler

Provides a dedicated interface for sending FMS completion messages back to the Bus Controller.
This module ensures that completion messages are properly formatted for the RT_sender
and follow the MIL-STD-1553B protocol.
Uses centralized message type constants for consistency.
"""

from FMOFP.local_messaging.message_types import (
    FMS_MODE_CHANGE_RESPONSE,
    FMS_ATTITUDE_UPDATE_RESPONSE,
    FMS_NAVIGATION_UPDATE_RESPONSE,
    FMS_MANEUVER_RESPONSE,
    FMS_STATUS_RESPONSE,
    COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_MODE_CHANGE_COMPLETE
)

import time
import threading
import traceback
import uuid
from typing import Dict, Any

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.rt_address_config import get_rt_subaddress_pair
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_connect.RT_socket import get_rt_sender
from FMOFP.MIL_STD_1553B.Bus_Controller.BC_messaging.BC_msg import BC_construct

logger = get_logger()

class FMSCompletionMessageHandler:
    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(FMSCompletionMessageHandler, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.bc_construct = BC_construct()
                self.__class__._initialized = True
                logger.info("FMSCompletionMessageHandler initialized")

    def send_completion_message(self,
                               system_name: str,
                               message_type: str,
                               command_type: str,
                               command_name: str,
                               metadata: Dict[str, Any] = None,
                               data: Any = None,
                               request_id: str = None) -> bool:
        """
        Send a completion message to the Bus Controller.

        This method formats the completion message according to the MIL-STD-1553B protocol
        and sends it to the Bus Controller using the RT_sender.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'flightmanagementsystem')
            message_type: The type of message (e.g., 'fms_modeChangeResponse')
            command_type: The type of command (e.g., 'mode_change_completion')
            command_name: The name of the command (e.g., 'FMS_MODE_CHANGE_COMPLETION')
            metadata: Additional metadata to include in the message
            data: The data to include in the message
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            logger.info(f"[COMPLETION] Sending completion message: system={system_name}, type={message_type}")

            # Ensure system name consistency for source system
            actual_system_id = system_name
            if 'fms' in system_name.lower() and 'flightmanagementsystem' not in system_name.lower():
                actual_system_id = 'flightmanagementsystem'
                logger.info(f"[COMPLETION] Using 'flightmanagementsystem' as the system ID for {system_name}")

            # Set RT address and subaddress
            rt_address = None
            sub_address = None

            try:
                # Use our FMS-specific address utilities
                from FMOFP.Systems.flightManagementSys.fms_messaging.address_utils import (
                    get_external_system_address,
                    get_external_subaddress
                )

                # Set destination RT address to displays system (RT address 11)
                # This is where completion messages are sent
                rt_address = get_external_system_address('displays')

                # Set destination subaddress to radar_display (subaddress 14)
                # The radar display handles mode change completions
                sub_address = get_external_subaddress('radar_display')

                logger.info(f"[COMPLETION] Using displays RT address {rt_address} and radar_display subaddress {sub_address}")

            except Exception as e:
                logger.error(f"[COMPLETION] Error getting address pair: {e}")
                # Re-raise the exception to avoid sending to incorrect destination
                raise ValueError(f"Failed to get RT/subaddress for completion message: {e}")

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
                f"[COMPLETION] BUG: status word data_bits has unexpected length "
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
                logger.error(f"[COMPLETION] Invalid status word length: {len(status_word)}")
                raise ValueError("Status word must be 20 bits long")

            logger.info(f"[COMPLETION] Created status word: {status_word}")

            if not request_id:
                raise ValueError("[COMPLETION] No request ID provided")

            # Create a properly formatted message for RT_sender
            # This format is critical for BC_Listener to properly process the message
            formatted_message = {
                'status_word': status_word,
                'request_id': request_id,
                'command_type': command_type,
                'message_type': message_type,
                'command_name': command_name,  # Include command_name for proper routing
                'timestamp': time.time(),
                'rt_address': rt_address,  # OF the DESTINATION SYSTEM! (not the source)
                'source': system_name,  # Source system name
                'destination': 'display_system',  # Default destination for completion messages
                'sub_address': sub_address  # Include subaddress for proper routing
            }

            # Add data if provided
            if data is not None:
                formatted_message['data'] = data

            # Create a combined metadata dictionary with all necessary routing information
            combined_metadata = {
                'system_type': system_name,
                'rt_address': rt_address,
                'subaddress': sub_address,
                'message_type': message_type,
                'command_type': command_type,
                'command_name': command_name,
                'timestamp': time.time(),
                'source': 'completion_message_handler',
                'destination': 'display_system'  # Default destination for completion messages
            }

            # Add user-provided metadata if available
            if metadata:
                combined_metadata.update(metadata)

            # Add the combined metadata to the formatted message
            formatted_message['metadata'] = combined_metadata

            # Get RT_sender instance
            rt_sender = get_rt_sender()

            # Send the formatted message to the BC
            logger.info(f"[COMPLETION] Sending formatted message to BC: {formatted_message}")
            logger.info(f"[COMPLETION] Message trace: RT_sender -> BC_Listener -> Bus_Controller -> Unified Router -> Display System")
            send_result = rt_sender.RT_send_message(formatted_message)

            if send_result:
                logger.info(f"[COMPLETION] Completion message sent successfully with request ID: {request_id}")
                logger.info(f"[COMPLETION] Message successfully sent from RT_sender to BC_Listener")
                return True
            else:
                logger.error(f"[COMPLETION] Failed to send completion message with request ID: {request_id}")
                return False

        except Exception as e:
            logger.error(f"[COMPLETION] Error sending completion message: {e}")
            logger.error(traceback.format_exc())
            return False

    def send_mode_change_completion(self,
                                   system_name: str,
                                   old_mode: str,
                                   new_mode: str,
                                   mode_value: int = None,
                                   request_id: str = None) -> bool:
        """
        Send a mode change completion message to the Bus Controller.

        This is a convenience method that calls send_completion_message with the appropriate
        parameters for a mode change completion message.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'flightmanagementsystem')
            old_mode: The previous mode name
            new_mode: The new mode name
            mode_value: The mode value (optional)
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """

        logger.info(f"[COMPLETION] Preparing mode change completion message: {system_name} mode {old_mode} -> {new_mode}")
        logger.info(f"[COMPLETION] Using request ID: {request_id}")

        # FMS uses its own dedicated message types
        message_type = FMS_MODE_CHANGE_RESPONSE
        command_name = 'FMS_MODE_CHANGE_COMPLETION'

        logger.info(f"[COMPLETION] Using message type: {message_type}")
        logger.info(f"[COMPLETION] Using command name: {command_name}")

        # Create metadata
        metadata = {
            'mode': new_mode,  # Add explicit mode field
            'mode_value': mode_value,
            'source_system': system_name,
            'destination': 'display_system',
            'force_update': True,
            'update_visual': True,
            'message_purpose': 'mode_change',
            'request_id': request_id
        }

        logger.info(f"[COMPLETION] Mode change completion metadata: {metadata}")

        # Send the completion message
        result = self.send_completion_message(
            system_name=system_name,
            message_type=message_type,
            command_type='mode_change_completion',
            command_name=command_name,
            metadata=metadata,
            data=mode_value,
            request_id=request_id
        )

        if result:
            logger.info(f"[COMPLETION] Mode change completion message sent successfully: {old_mode} -> {new_mode}")
        elif request_id is None:
            # Not a failure: send_completion_message() intentionally returns
            # False here because this was an internal/automatic transition
            # with no external request to acknowledge (already logged at
            # DEBUG level inside send_completion_message). Previously this
            # was logged as an ERROR ("Failed to send...") on every single
            # automatic mode change, and callers that also check this return
            # value (e.g. weather_radar.py, aewc_radar.py) logged a second,
            # redundant ERROR of their own. Report success so neither layer
            # raises a false alarm for expected, non-actionable behavior.
            logger.debug(f"[COMPLETION] Mode change completion skipped (no request_id, nothing to acknowledge): {old_mode} -> {new_mode}")
            result = True
        else:
            logger.error(f"[COMPLETION] Failed to send mode change completion message: {old_mode} -> {new_mode}")

        return result

    def send_data_completion(self,
                            system_name: str,
                            data_type: str,
                            data: Any,
                            request_id: str) -> bool:
        """
        Send a data completion message to the Bus Controller.

        This is a convenience method that calls send_completion_message with the appropriate
        parameters for a data completion message.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'flightmanagementsystem')
            data_type: The type of data (e.g., 'attitude', 'navigation')
            data: The data to include in the message
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Determine the message type based on the data type
        data_type_lower = data_type.lower()

        if 'attitude' in data_type_lower:
            message_type = FMS_ATTITUDE_UPDATE_RESPONSE
            command_name = 'FMS_ATTITUDE_UPDATE_COMPLETION'
        elif 'navigation' in data_type_lower:
            message_type = FMS_NAVIGATION_UPDATE_RESPONSE
            command_name = 'FMS_NAVIGATION_UPDATE_COMPLETION'
        elif 'maneuver' in data_type_lower:
            message_type = FMS_MANEUVER_RESPONSE
            command_name = 'FMS_MANEUVER_COMPLETION'
        elif 'status' in data_type_lower:
            message_type = FMS_STATUS_RESPONSE
            command_name = 'FMS_STATUS_COMPLETION'
        else:
            # Raise error for unsupported data types
            error_msg = f"[COMPLETION] Unsupported data type for FMS: {data_type}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Create metadata
        metadata = {
            'data_type': data_type,
            'source_system': system_name,
            'destination': 'display_system',
            'timestamp': time.time()
        }

        # Send the completion message
        return self.send_completion_message(
            system_name=system_name,
            message_type=message_type,
            command_type=f'{data_type}_completion',
            command_name=command_name,
            metadata=metadata,
            data=data,
            request_id=request_id
        )

# Global instance
_fms_completion_message_handler = None

def get_fms_completion_message_handler() -> FMSCompletionMessageHandler:
    """Get the singleton FMSCompletionMessageHandler instance."""
    global _fms_completion_message_handler
    if _fms_completion_message_handler is None:
        _fms_completion_message_handler = FMSCompletionMessageHandler()
    return _fms_completion_message_handler
