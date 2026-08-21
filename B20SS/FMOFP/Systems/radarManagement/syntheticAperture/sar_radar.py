"""
Synthetic Aperture Radar System

Handles SAR operations using direct message handling.
"""

import time
import traceback
import threading
import numpy as np
from typing import Dict
from Systems.radarManagement.radar_enums import sar_radarMode
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
# Import radar-local message definitions to enforce system boundaries
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.sar_data import SARRadarImagery
# Import message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    SAR_RADAR_IMAGERY_RESPONSE,
    SAR_RADAR_IMAGERY_REQUEST
)
# For backward compatibility - to be removed in future releases
from FMOFP.local_messaging.messageConfigurations.SARRadarImagery import sar_radarImagery as LegacySARRadarImagery
from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.syntheticAperture.sar_processor import ChangeDetector

logger = get_logger()

class sar_radar:
    def __init__(self, name: str, radar_control, radar_messenger):
        self.name = name
        self.mode = sar_radarMode.STANDBY
        self.radar_control = radar_control
        self.radar_messenger = radar_messenger
        self.running = False
        self._lock = threading.Lock()
        self._health_status = True

        # SAR specific parameters
        self.image_width = 1024    # pixels
        self.image_height = 1024   # pixels
        self.resolution = 1.0      # meters per pixel
        self.corner_points = [
            (-5000, -5000),  # Bottom left
            (-5000, 5000),   # Top left
            (5000, 5000),    # Top right
            (5000, -5000)    # Bottom right
        ]

        # Capability modules
        self.change_detector = ChangeDetector()
        logger.info(f"SAR radar {name} initialized")

    def _generate_imagery_data(self) -> np.ndarray:
        """Generate simulated SAR imagery data."""
        try:
            # Create a simulated ground image with features
            image = np.zeros((self.image_height, self.image_width), dtype=np.uint8)

            # Add terrain features based on current mode
            if self.mode == sar_radarMode.STRIPMAP:
                # Long linear features
                for i in range(5):
                    x = np.random.randint(0, self.image_width)
                    image[:, x:x+10] = 200

            elif self.mode == sar_radarMode.SPOTLIGHT:
                # Circular target area
                center_x = self.image_width // 2
                center_y = self.image_height // 2
                radius = min(self.image_width, self.image_height) // 4

                y, x = np.ogrid[-center_y:self.image_height-center_y, -center_x:self.image_width-center_x]
                mask = x*x + y*y <= radius*radius
                image[mask] = 200

            elif self.mode == sar_radarMode.SCANSAR:
                # Multiple swath patterns
                for i in range(3):
                    start_y = i * (self.image_height // 3)
                    end_y = (i + 1) * (self.image_height // 3)
                    image[start_y:end_y, :] = np.random.randint(100, 200, (end_y-start_y, self.image_width))

            # Add some noise
            noise = np.random.normal(0, 10, image.shape)
            image = np.clip(image + noise, 0, 255).astype(np.uint8)

            return image

        except Exception as e:
            logger.error(f"Error generating SAR imagery: {e}")
            return bytes()

    def start(self):
        """Start the SAR radar system."""
        try:
            logger.info(f"Starting SAR radar {self.name}")
            with self._lock:
                if self.running:
                    logger.warning(f"SAR radar {self.name} already running")
                    return
                self.running = True
                self.mode = sar_radarMode.STANDBY
            logger.info(f"SAR radar {self.name} started")
        except Exception as e:
            logger.error(f"Error starting SAR radar {self.name}: {str(e)}")
            self._health_status = False

    def stop(self):
        """Stop the SAR radar system."""
        try:
            logger.info(f"Stopping SAR radar {self.name}")
            with self._lock:
                if not self.running:
                    logger.warning(f"SAR radar {self.name} already stopped")
                    return
                self.running = False
                self.mode = sar_radarMode.STANDBY
            logger.info(f"SAR radar {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping SAR radar {self.name}: {str(e)}")
            self._health_status = False

    def set_mode(self, mode, send_completion=True, request_id=None):
        """
        Set radar mode.

        Args:
            mode: The new mode to set
            send_completion: Whether to send a mode change completion notification (default: True)
            request_id: The request ID to include in the completion message
        """
        try:
            # Handle different input types
            try:
                if isinstance(mode, sar_radarMode):
                    # Already a valid enum value
                    pass
                elif isinstance(mode, int):
                    # Convert integer to enum value
                    mode = sar_radarMode(mode)
                elif hasattr(mode, '_value_'):
                    # Handle case where we receive an enum member
                    mode = sar_radarMode(mode._value_)
                elif mode is sar_radarMode:
                    # Handle case where we get the actual enum class itself (not an instance/member)
                    logger.info(f"[SAR_RADAR] Received enum class itself, defaulting to STRIPMAP mode")
                    mode = sar_radarMode.STRIPMAP
                else:
                    logger.error(f"[SAR_RADAR] Invalid mode type: {type(mode)}")
                    return
            except ValueError as e:
                logger.error(f"[SAR_RADAR] Invalid mode value: {mode}")
                return
            except Exception as e:
                logger.error(f"[SAR_RADAR] Error converting mode: {str(e)}")
                return

            # Check if we're already in this mode - no need to change or send completion
            if self.mode == mode:
                logger.info(f"[SAR_RADAR] Already in mode {mode.name}, no change needed")
                return

            with self._lock:
                old_mode = self.mode
                self.mode = mode
                logger.info(f"SAR radar {self.name} mode changed from {old_mode.name} to {mode.name}")

                # Send mode change completion notification if requested
                if send_completion:
                    logger.info(f"[SAR_RADAR] Sending mode change completion notification (send_completion=True)")
                    self._send_mode_change_completion(old_mode, mode, request_id)
                else:
                    logger.info(f"[SAR_RADAR] Skipping mode change completion notification (send_completion=False)")
        except Exception as e:
            logger.error(f"Error setting mode for SAR radar {self.name}: {str(e)}")

    def receive_message(self, message: MIL_STD_1553B_Message):
        """Handle incoming messages directly."""
        try:
            if not isinstance(message, MIL_STD_1553B_Message):
                logger.warning(f"Invalid message type received: {type(message)}")
                return

            if message.message_type == "MODE_CHANGE":
                self._handle_mode_change(message)
            elif message.message_type == "IMAGERY_DATA_REQUEST":
                self._handle_imagery_request(message)
            else:
                logger.debug(f"Unhandled message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error handling message for SAR radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())

    def _send_mode_change_completion(self, old_mode, new_mode, request_id=None):
        """
        Send a mode change completion notification.

        This is critical for proper synchronization between radar and display systems.
        The completion message ensures that the display system knows when the radar
        has actually completed the mode change.

        Args:
            old_mode: The previous mode
            new_mode: The new mode
            request_id: The original request ID
        """
        try:
            # Import the CompletionMessageHandler
            from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

            # Log the mode change completion
            logger.info(f"[SAR_RADAR] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")
            logger.info(f"[SAR_RADAR] Using request ID: {request_id}")

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()
            if not completion_handler:
                logger.error("[SAR_RADAR] Cannot send mode change completion - completion handler not available")
                return

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=request_id,
                radar_type='sar_radar'
            )

            if success:
                logger.info(f"[SAR_RADAR] Mode change completion notification sent successfully")
            else:
                logger.error(f"[SAR_RADAR] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[SAR_RADAR] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())

    def _extract_mode_value_from_data(self, mode_data):
        """
        Extract mode value from binary data.

        Args:
            mode_data: Binary data string containing mode information

        Returns:
            int: The extracted mode value
        """
        try:
            # Convert binary string to integer
            if mode_data:
                # Convert 8-bit chunks to bytes, handle odd-length strings
                if len(mode_data) % 8 != 0:
                    # Pad to multiple of 8 bits
                    mode_data = mode_data.zfill((len(mode_data) + 7) // 8 * 8)

                # Convert 8-bit chunks to bytes
                mode_bytes = bytes([int(mode_data[i:i+8], 2) for i in range(0, len(mode_data), 8)])
                # Convert bytes to integer
                mode_value = int.from_bytes(mode_bytes, byteorder='big')
                logger.info(f"[SAR_RADAR] Extracted mode value: {mode_value} from data: {mode_data}")
                return mode_value
            else:
                logger.error(f"[SAR_RADAR] Empty mode data")
                return 0
        except Exception as e:
            logger.error(f"[SAR_RADAR] Error extracting mode value: {e}")
            logger.error(traceback.format_exc())
            # Default to STANDBY (0) on error
            return 0

    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for SAR radar.

        This is used by the RadarMessenger for direct message handling.
        Required by RadarMessenger.py _message_loop for direct message handling.

        Args:
            message: The message to process

        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            logger.info(f"[SAR_RADAR] Synchronously processing message with ID: {id(message)}")

            # Log message details for debugging
            if hasattr(message, 'message_type'):
                logger.info(f"[SAR_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                logger.info(f"[SAR_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[SAR_RADAR] Command name: {message.command_name}")

            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}

            # Mark as processed by SAR radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []

                if 'sar_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('sar_radar')

            # Process the message based on its type using parameter-based approach
            if hasattr(message, 'message_type'):
                message_type = message.message_type
                if message_type == "MODE_CHANGE" or (hasattr(message, 'command_type') and message.command_type == "mode_change"):
                    # Extract parameters instead of passing the whole message
                    mode_data = message.data

                    # Extract request_id for completion tracking
                    message_request_id = None
                    if hasattr(message, 'request_id'):
                        message_request_id = message.request_id
                    elif hasattr(message, 'metadata') and isinstance(message.metadata, dict) and 'request_id' in message.metadata:
                        message_request_id = message.metadata['request_id']

                    # Extract mode value from binary data
                    mode_value = self._extract_mode_value_from_data(mode_data)

                    # Call handler with extracted parameters instead of raw message
                    return self._handle_mode_change_sync(mode_value, message_request_id)
                elif message_type == "IMAGERY_DATA_REQUEST" or (hasattr(message, 'command_type') and message.command_type == "imagery_data"):
                    return self._handle_imagery_data_sync(message)

            # For logging purposes
            logger.info(f"[SAR_RADAR] Message successfully processed synchronously")
            return True

        except Exception as e:
            logger.error(f"[SAR_RADAR] Error processing message synchronously: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_imagery_data_sync(self, message):
        """
        Handle imagery data request synchronously.

        Args:
            message: The imagery data request message

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"[SAR_RADAR] Handling imagery data request synchronously")

            # Extract request ID from message
            request_id = None
            if hasattr(message, 'request_id'):
                request_id = message.request_id
            elif hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                request_id = message.metadata.get('request_id')

            logger.info(f"[SAR_RADAR] Imagery data request ID: {request_id}")

            # Check if we're in standby mode
            if self.mode == sar_radarMode.STANDBY:
                logger.warning("[SAR_RADAR] Cannot generate imagery in STANDBY mode")
                return False

            # Generate imagery based on current mode
            image_data = self._generate_imagery_data()

            # Run change detection on the new frame
            if isinstance(image_data, np.ndarray) and image_data.size > 0:
                try:
                    change_events = self.change_detector.process(image_data)
                    sig = [e for e in change_events if e.is_significant]
                    if sig:
                        logger.info(
                            f"[SAR_RADAR] {len(sig)} significant change(s) "
                            f"detected in imagery frame"
                        )
                except Exception as _cd_exc:
                    logger.warning(f"[SAR_RADAR] Change detection error: {_cd_exc}")

            # Create imagery data message using radar-local message definitions
            imagery_data = SARRadarImagery(
                image_uuid=str(time.time()),
                image_data=image_data,
                resolution=self.resolution,
                geo_reference={
                    'corner_points': self.corner_points,
                    'image_width': self.image_width,
                    'image_height': self.image_height
                },
                message_header="sar_imagery",
                sending_system="sar_radar",
                destination="radar_handler",
                command_type="imagery_data",
                command_name="SAR_RADAR_IMAGERY",
                request_id=request_id  # Include request ID
            )

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_sar_data
                push_sar_data([imagery_data], request_id or str(time.time()))
                logger.info(f"[SAR_RADAR] Bridge: imagery data pushed to display coordinator")
            except Exception as _bridge_exc:
                logger.warning(f"[SAR_RADAR] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

            # Send response through radar messenger
                self.radar_messenger.send_message(imagery_data)
                logger.info(f"[SAR_RADAR] Sent imagery data response with request ID: {request_id}")

                # Import the CompletionMessageHandler
                from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

                # Get the CompletionMessageHandler instance
                completion_handler = get_completion_message_handler()

                # Send the data completion message SYNCHRONOUSLY
                if completion_handler:
                    success = completion_handler.send_data_completion(
                        system_name='radar',
                        data_type='imagery',
                        data=imagery_data,
                        request_id=request_id
                    )

                    if success:
                        logger.info(f"[SAR_RADAR] Sent imagery data completion notification with request ID: {request_id}")
                    else:
                        logger.error(f"[SAR_RADAR] Failed to send imagery data completion notification")
                else:
                    logger.error("[SAR_RADAR] Cannot send data completion - completion handler not available")

            return True

        except Exception as e:
            logger.error(f"[SAR_RADAR] Error handling imagery data request: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_mode_change_sync(self, mode_value, request_id=None):
        """
        Handle mode change using direct parameter-based inputs.

        Args:
            mode_value: The extracted mode value (integer)
            request_id: The request ID for completion tracking

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"[SAR_RADAR] Handling mode change with value: {mode_value}, request_id: {request_id}")

            # Convert to enum
            try:
                new_mode = sar_radarMode(mode_value)
                logger.info(f"[SAR_RADAR] Processed mode value {mode_value} to enum {new_mode.name}")

                # Save original mode before changing
                old_mode = self.mode

                # Set the mode with completion
                self.set_mode(new_mode, send_completion=True, request_id=request_id)
                logger.info(f"[SAR_RADAR] Set SAR radar mode to {new_mode.name}")

                return True
            except ValueError as e:
                logger.error(f"[SAR_RADAR] Invalid mode value: {mode_value} is not a valid sar_radarMode")
                return False
        except Exception as e:
            logger.error(f"[SAR_RADAR] Error handling mode change: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_mode_change(self, message: MIL_STD_1553B_Message):
        """Handle mode change messages."""
        try:
            logger.info(f"[SAR_RADAR] Handling mode change message via parameter extraction")

            # Extract mode value and request_id
            mode_data = message.data

            # Extract request_id for completion tracking
            message_request_id = None
            if hasattr(message, 'request_id'):
                message_request_id = message.request_id
            elif hasattr(message, 'metadata') and isinstance(message.metadata, dict) and 'request_id' in message.metadata:
                message_request_id = message.metadata['request_id']

            # Extract mode value from binary data
            mode_value = self._extract_mode_value_from_data(mode_data)

            # Handle via the parameter-based synchronized method
            return self._handle_mode_change_sync(mode_value, message_request_id)

        except ValueError as e:
            logger.error(f"[SAR_RADAR] Invalid mode value in message: {e}")
        except Exception as e:
            logger.error(f"[SAR_RADAR] Error handling mode change for {self.name}: {e}")
            logger.error(traceback.format_exc())

    def _handle_imagery_request(self, message: MIL_STD_1553B_Message):
        """Handle imagery data request messages."""
        try:
            # Handle via the synchronized method
            return self._handle_imagery_data_sync(message)

        except Exception as e:
            logger.error(f"Error handling imagery request: {e}")

    def is_healthy(self) -> bool:
        """Check if radar is healthy."""
        return self._health_status and self.running

    def get_status(self) -> Dict:
        """Get radar status."""
        with self._lock:
            return {
                'name': self.name,
                'mode': self.mode.name,
                'running': self.running,
                'healthy': self._health_status,
                'resolution': self.resolution,
                'image_dimensions': (self.image_width, self.image_height)
            }
