"""
Completion Message Handler

Provides a generic interface for sending completion messages back to the Bus Controller.
This module ensures that completion messages are properly formatted for the RT_sender
and follow the MIL-STD-1553B protocol.
Uses centralized message type constants for consistency.
"""

from FMOFP.local_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    TFR_RADAR_MODE_CHANGE_RESPONSE,
    SAR_RADAR_MODE_CHANGE_RESPONSE,
    TARGETING_RADAR_MODE_CHANGE_RESPONSE,
    AEWC_RADAR_MODE_CHANGE_RESPONSE,
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

class CompletionMessageHandler:
    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(CompletionMessageHandler, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.bc_construct = BC_construct()
                self.__class__._initialized = True
                logger.info("CompletionMessageHandler initialized")

    def send_completion_message(self,
                               system_name: str,
                               message_type: str,
                               command_type: str,
                               command_name: str,
                               metadata: Dict[str, Any] = None,
                               data: Any = None,
                               request_id: str = None,
                               radar_type: str = None) -> bool:
        """
        Send a completion message to the Bus Controller.

        This method formats the completion message according to the MIL-STD-1553B protocol
        and sends it to the Bus Controller using the RT_sender.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'weather_radar')
            message_type: The type of message (e.g., 'weather_radarModeChangeCompletion')
            command_type: The type of command (e.g., 'mode_change_completion')
            command_name: The name of the command (e.g., 'WEATHER_RADAR_MODE_CHANGE_COMPLETION')
            metadata: Additional metadata to include in the message
            data: The data to include in the message
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        try:
            logger.info(f"[COMPLETION] Sending completion message: system={system_name}, type={message_type}")

            # Determine the appropriate system ID for RT/SA address lookup
            # Radar subsystems (weather_radar, tfr_radar, etc.) are actually subaddresses of the main radar system
            actual_system_id = system_name
            radar_subsystems = ['weather_radar', 'tfr_radar', 'sar_radar', 'targeting_radar', 'aewc_radar']

            # Check if this is a radar subsystem
            if any(subsys in system_name for subsys in radar_subsystems):
                logger.info(f"[COMPLETION] Using 'radar' as the system ID for subsystem {system_name}")
                actual_system_id = 'radar'  # Use the main radar system ID for RT address lookup

            # First set default RT address based on the system ID
            rt_address = None
            sub_address = None

            # Get RT address and subaddress
            try:
                # Import here to avoid circular import issues.
                # NOTE: previously flagged as "create a mirror'd radar-local
                # version" for system separation. Investigated: address_utils
                # is the single shared RT-address/subaddress lookup table
                # that every subsystem (radar, FMS, displays) must agree on -
                # it's the software analog of a physical bus address map, not
                # business logic specific to one subsystem. Duplicating it
                # per-system would let systems independently drift on what a
                # given RT address means, which is exactly the class of bug a
                # real shared 1553B address table prevents. Keeping this as a
                # single shared import is the correct design; not duplicating it.
                from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress

                # First get the RT address for the actual system
                rt_address = get_rt_address(actual_system_id)

                # For radar subsystems, use the corresponding radar subaddress
                if radar_type:
                    # If explicit radar_type parameter is provided, use that
                    logger.info(f"[COMPLETION] Using explicit radar_type: {radar_type} to determine subaddress")
                    if 'weather_radar' in radar_type:
                        sub_address = 1  # Weather radar subaddress
                        logger.info(f"[COMPLETION] Using weather_radar subaddress: {sub_address}")
                    elif 'tfr_radar' in radar_type:
                        sub_address = 2  # TFR radar subaddress
                        logger.info(f"[COMPLETION] Using tfr_radar subaddress: {sub_address}")
                    elif 'sar_radar' in radar_type:
                        sub_address = 3  # SAR radar subaddress
                        logger.info(f"[COMPLETION] Using sar_radar subaddress: {sub_address}")
                    elif 'targeting_radar' in radar_type:
                        sub_address = 4  # Targeting radar subaddress
                        logger.info(f"[COMPLETION] Using targeting_radar subaddress: {sub_address}")
                    elif 'aewc_radar' in radar_type:
                        sub_address = 5  # AEWC radar subaddress
                        logger.info(f"[COMPLETION] Using aewc_radar subaddress: {sub_address}")
                elif any(subsys in system_name for subsys in radar_subsystems):
                    # Fallback to checking system_name if radar_type not provided
                    for subsys in radar_subsystems:
                        if subsys in system_name:
                            sub_address = get_subaddress(subsys)
                            logger.info(f"[COMPLETION] Using radar subsystem '{subsys}' subaddress: {sub_address}")
                            break
                elif 'displays' in actual_system_id:
                    # For display system, use radar_display subaddress
                    sub_address = get_subaddress('radar_display')
                    logger.info(f"[COMPLETION] Using display system radar_display subaddress: {sub_address}")
                else:
                    # Default to mode_codes for other systems
                    sub_address = get_subaddress('mode_codes')
                    logger.info(f"[COMPLETION] Using mode_codes subaddress for system: {actual_system_id}")
            except Exception as e:
                logger.warning(f"[COMPLETION] Error getting address pair: {e}")
                rt_address = None  # Reset so the next block handles it

                if rt_address == 9:
                    # Try to determine appropriate subaddress from system name
                    if 'weather_radar' in system_name:
                        sub_address = 1  # Weather radar subaddress
                    elif 'tfr_radar' in system_name:
                        sub_address = 2  # TFR radar subaddress
                    elif 'sar_radar' in system_name:
                        sub_address = 3  # SAR radar subaddress
                    elif 'targeting_radar' in system_name:
                        sub_address = 4  # Targeting radar subaddress
                    elif 'aewc_radar' in system_name:
                        sub_address = 5  # AEWC radar subaddress
                elif rt_address == 11:
                    if 'pfd' in system_name:
                        sub_address = 11  # PFD subaddress
                    elif 'mfd' in system_name:
                        sub_address = 12
                    elif 'eicas' in system_name:
                        sub_address = 13
                    elif 'radar_display' in system_name:
                        sub_address = 14
                    elif 'tsd' in system_name:
                        sub_address = 15
                    elif 'sms' in system_name:
                        sub_address = 16
                    elif 'fms' in system_name:
                        sub_address = 17

            # If subaddress is still not found, use a default subaddress for completion messages
            if sub_address is None:
                sub_address = 31  # Mode codes subaddress is commonly used for special operations
                logger.info(f"[COMPLETION] Using default subaddress {sub_address} for {system_name}")

            logger.info(f"[COMPLETION] Using RT address {rt_address} and subaddress {sub_address} for system {system_name}")

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

            # Ensure data bits are exactly 16 bits
            if len(data_bits) != 16:
                # data_bits is always exactly 16 bits (5 rt_address + 11 fixed
                # flag bits) so this branch is unreachable.  Large radar data
                # payloads are handled by the block-transfer path in RT_socket.
                assert False, (
                    f"[RADAR_COMP] BUG: status word data_bits has unexpected "
                    f"length {len(data_bits)} — check bit-field construction"
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


            logger.info(f"[COMPLETION] Created status word: {status_word}")

            if not request_id:
                # Automatic/internal mode transitions (initial radar
                # configuration at boot, mission-phase-driven resource
                # management, etc.) call this with request_id=None by
                # design -- there's no external 1553B request to
                # acknowledge, since nothing asked for this change. That's
                # a normal, expected outcome, not a failure: raising here
                # (as this code previously did) gets caught by the broad
                # except below and logged as a full ERROR-level traceback
                # for every single one of these, which is just noise in
                # production logs (confirmed live: fires at boot for each
                # radar's initial mode configuration). Log it quietly and
                # return False -- callers already handle a False return
                # gracefully (see e.g. weather_radar.py's
                # "if success: ... else: ..." after calling
                # send_mode_change_completion()).
                logger.debug(
                    f"[COMPLETION] No request_id provided for {system_name} "
                    f"{command_type} -- this was an internal/automatic "
                    f"transition with no external request to acknowledge; "
                    f"skipping completion message."
                )
                return False
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
                                   request_id: str = None,
                                   radar_type: str = None) -> bool:
        """
        Send a mode change completion message to the Bus Controller.

        This is a convenience method that calls send_completion_message with the appropriate
        parameters for a mode change completion message.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'radar')
            old_mode: The previous mode name
            new_mode: The new mode name
            mode_value: The mode value (optional)
            request_id: The request ID to use
            radar_type: The specific radar type (e.g., 'weather_radar', 'tfr_radar', etc.)

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """

        logger.info(f"[COMPLETION] Preparing mode change completion message: {system_name} mode {old_mode} -> {new_mode}")
        logger.info(f"[COMPLETION] Using request ID: {request_id}")

        # Determine the message type based on radar_type if provided, otherwise use system_name
        if radar_type:
            logger.info(f"[COMPLETION] Using explicit radar_type: {radar_type} to determine message type")
            if 'weather_radar' in radar_type:
                message_type = WEATHER_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'WEATHER_RADAR_MODE_CHANGE_COMPLETION'
            elif 'tfr_radar' in radar_type:
                message_type = TFR_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'TFR_RADAR_MODE_CHANGE_COMPLETION'
            elif 'sar_radar' in radar_type:
                message_type = SAR_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'SAR_RADAR_MODE_CHANGE_COMPLETION'
            elif 'targeting_radar' in radar_type:
                message_type = TARGETING_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'TARGETING_RADAR_MODE_CHANGE_COMPLETION'
            elif 'aewc_radar' in radar_type:
                message_type = AEWC_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'AEWC_RADAR_MODE_CHANGE_COMPLETION'
            else:
                raise ValueError(f"[COMPLETION] Unrecognized system_name: {system_name} and no radar_type provided")
        else:
            # Use existing system_name check for backward compatibility
            logger.info(f"[COMPLETION] No radar_type provided, using system_name: {system_name} for backward compatibility")
            if 'weather_radar' in system_name:
                message_type = WEATHER_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'WEATHER_RADAR_MODE_CHANGE_COMPLETION'
            elif 'tfr_radar' in system_name:
                message_type = TFR_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'TFR_RADAR_MODE_CHANGE_COMPLETION'
            elif 'sar_radar' in system_name:
                message_type = SAR_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'SAR_RADAR_MODE_CHANGE_COMPLETION'
            elif 'targeting_radar' in system_name:
                message_type = TARGETING_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'TARGETING_RADAR_MODE_CHANGE_COMPLETION'
            elif 'aewc_radar' in system_name:
                message_type = AEWC_RADAR_MODE_CHANGE_RESPONSE
                command_name = 'AEWC_RADAR_MODE_CHANGE_COMPLETION'
            else:
                raise ValueError(f"[COMPLETION] Unrecognized system_name: {system_name} and no radar_type provided")

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
            request_id=request_id,
            radar_type=radar_type
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
                            request_id: str,
                            radar_type: str = None) -> bool:
        """
        Send a data completion message to the Bus Controller.

        This is a convenience method that calls send_completion_message with the appropriate
        parameters for a data completion message.

        Args:
            system_name: The name of the system sending the completion message (e.g., 'weather_radar')
            data_type: The type of data (e.g., 'vil', 'precipitation')
            data: The data to include in the message
            request_id: The request ID to use

        Returns:
            bool: True if the message was sent successfully, False otherwise
        """
        # Determine the message type based on the system name and data type using centralized constants
        if 'weather_radar' in system_name:
            if 'vil' in data_type.lower():
                message_type = WEATHER_RADAR_VIL_RESPONSE
                command_name = 'WEATHER_RADAR_VIL_COMPLETION'
            elif 'precip' in data_type.lower():
                message_type = WEATHER_RADAR_PRECIPITATION_RESPONSE
                command_name = 'WEATHER_RADAR_PRECIPITATION_COMPLETION'
            else:
                message_type = f'weather_radar{data_type.capitalize()}Completion'
                command_name = f'WEATHER_RADAR_{data_type.upper()}_COMPLETION'
        else:
            # Default format for other systems
            message_type = f'{system_name}{data_type.capitalize()}Completion'
            command_name = f'{system_name.upper()}_{data_type.upper()}_COMPLETION'

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
            request_id=request_id,
            radar_type=radar_type  # Pass radar_type to ensure correct subaddress
        )

# Global instance
_completion_message_handler = None

def get_completion_message_handler() -> CompletionMessageHandler:
    """Get the singleton CompletionMessageHandler instance."""
    global _completion_message_handler
    if _completion_message_handler is None:
        _completion_message_handler = CompletionMessageHandler()
    return _completion_message_handler
