"""
Terrain Following Radar System

Handles terrain following radar operations using direct message handling.
"""

import time
import traceback
import threading
import numpy as np
from typing import Dict, List, Tuple
from Systems.radarManagement.radar_enums import tfr_radarMode
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
# Import radar-local message definitions to enforce system boundaries
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.tfr_data import (
    TFRRadarElevationProfile,
    TFRRadarTerrainWarning
)
# Import message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    TFR_RADAR_ELEVATION_PROFILE,
    TFR_RADAR_TERRAIN_WARNING,
    COMMAND_TYPE_ELEVATION_DATA,
    COMMAND_TYPE_TERRAIN_WARNING
)
# For backward compatibility - to be removed in future releases
from FMOFP.local_messaging.messageConfigurations.tfr_radar_data import (
    tfr_radarElevationProfile as LegacyTFRRadarElevationProfile,
    tfr_radarTerrainWarning as LegacyTFRRadarTerrainWarning
)
from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.terrainFollowing.tfr_processor import PathOptimiser, ClearanceManager

logger = get_logger()

class tfr_radar:
    def __init__(self, name: str, radar_control, radar_messenger):
        self.name = name
        self.mode = tfr_radarMode.STANDBY
        self.radar_control = radar_control
        self.radar_messenger = radar_messenger
        self.running = False
        self._lock = threading.Lock()
        self._health_status = True

        # TFR specific parameters
        self.scan_range = 10000  # meters
        self.scan_width = 2000   # meters
        self.elevation_points = 100
        self.terrain_data = self._initialize_terrain_data()
        self.last_warning_time = 0
        self.warning_interval = 1.0  # seconds

        # Capability modules
        self.path_optimiser    = PathOptimiser()
        self.clearance_manager = ClearanceManager()
        logger.info(f"TFR radar {name} initialized")

    def _initialize_terrain_data(self) -> List[Tuple[float, float]]:
        """Initialize simulated terrain data."""
        distances = np.linspace(0, self.scan_range, self.elevation_points)
        # Generate realistic terrain with hills and valleys
        elevations = 1000 + 500 * np.sin(distances / 1000) + \
                    200 * np.sin(distances / 300) + \
                    np.random.normal(0, 50, self.elevation_points)
        return list(zip(distances, elevations))

    def _check_terrain_warnings(self) -> List[Dict]:
        """Check for terrain warnings based on current data."""
        warnings = []
        current_time = time.time()

        if current_time - self.last_warning_time >= self.warning_interval:
            for distance, elevation in self.terrain_data:
                # Check for dangerous terrain features
                if elevation > 1500:  # High terrain
                    warnings.append({
                        'type': 'HIGH_TERRAIN',
                        'distance': distance,
                        'elevation': elevation
                    })
                elif abs(elevation - 1000) > 300:  # Steep terrain
                    warnings.append({
                        'type': 'STEEP_TERRAIN',
                        'distance': distance,
                        'elevation': elevation
                    })

            self.last_warning_time = current_time

        return warnings

    def start(self):
        """Start the TFR radar system."""
        try:
            logger.info(f"Starting TFR radar {self.name}")
            with self._lock:
                if self.running:
                    logger.warning(f"TFR radar {self.name} already running")
                    return
                self.running = True
                self.mode = tfr_radarMode.STANDBY
            logger.info(f"TFR radar {self.name} started")
        except Exception as e:
            logger.error(f"Error starting TFR radar {self.name}: {str(e)}")
            self._health_status = False

    def stop(self):
        """Stop the TFR radar system."""
        try:
            logger.info(f"Stopping TFR radar {self.name}")
            with self._lock:
                if not self.running:
                    logger.warning(f"TFR radar {self.name} already stopped")
                    return
                self.running = False
                self.mode = tfr_radarMode.STANDBY
            logger.info(f"TFR radar {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping TFR radar {self.name}: {str(e)}")
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
                if isinstance(mode, tfr_radarMode):
                    # Already a valid enum value
                    pass
                elif isinstance(mode, int):
                    # Convert integer to enum value
                    mode = tfr_radarMode(mode)
                elif hasattr(mode, '_value_'):
                    # Handle case where we receive an enum member
                    mode = tfr_radarMode(mode._value_)
                elif mode is tfr_radarMode:
                    # Handle case where we get the actual enum class itself (not an instance/member)
                    logger.info(f"[TFR_RADAR] Received enum class itself, defaulting to NORMAL mode")
                    mode = tfr_radarMode.NORMAL
                else:
                    logger.error(f"[TFR_RADAR] Invalid mode type: {type(mode)}")
                    return
            except ValueError as e:
                logger.error(f"[TFR_RADAR] Invalid mode value: {mode}")
                return
            except Exception as e:
                logger.error(f"[TFR_RADAR] Error converting mode: {str(e)}")
                return

            # Check if we're already in this mode - no need to change or send completion
            if self.mode == mode:
                logger.info(f"[TFR_RADAR] Already in mode {mode.name}, no change needed")
                return

            with self._lock:
                old_mode = self.mode
                self.mode = mode
                logger.info(f"TFR radar {self.name} mode changed from {old_mode.name} to {mode.name}")

                # Update terrain data when entering SEARCH or TRACK mode
                if mode in [tfr_radarMode.SEARCH, tfr_radarMode.TRACK]:
                    self.terrain_data = self._initialize_terrain_data()

                # Send mode change completion notification if requested
                if send_completion:
                    logger.info(f"[TFR_RADAR] Sending mode change completion notification (send_completion=True)")
                    self._send_mode_change_completion(old_mode, mode, request_id)
                else:
                    logger.info(f"[TFR_RADAR] Skipping mode change completion notification (send_completion=False)")
        except Exception as e:
            logger.error(f"Error setting mode for TFR radar {self.name}: {str(e)}")

    def receive_message(self, message: MIL_STD_1553B_Message):
        """Handle incoming messages directly."""
        try:
            if not isinstance(message, MIL_STD_1553B_Message):
                logger.warning(f"Invalid message type received: {type(message)}")
                return

            if message.message_type == "MODE_CHANGE":
                self._handle_mode_change(message)
            elif message.message_type == "DATA":
                self._handle_data_request(message)
            else:
                logger.debug(f"Unhandled message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error handling message for TFR radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())

    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for TFR radar.

        This is used by the RadarMessenger for direct message handling.
        Required by RadarMessenger.py _message_loop for direct message handling.

        Args:
            message: The message to process

        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            logger.info(f"[TFR_RADAR] Synchronously processing message with ID: {id(message)}")

            # Log message details for debugging
            if hasattr(message, 'message_type'):
                logger.info(f"[TFR_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                logger.info(f"[TFR_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[TFR_RADAR] Command name: {message.command_name}")

            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}

            # Mark as processed by TFR radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []

                if 'tfr_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('tfr_radar')

            # Use message type detector to determine how to handle this message
            from FMOFP.Systems.radarManagement.terrainFollowing.tfr_message_type_detector import tfr_message_type_detector
            detector = tfr_message_type_detector()
            handler_type = detector.detect_message_type(message)

            logger.info(f"[TFR_RADAR] Message handler type: {handler_type}")

            if handler_type == "mode_handler":
                # Extract mode value and request_id instead of passing the whole message
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
                return self._handle_mode_change_sync(mode_value, request_id=message_request_id)
            elif handler_type == "elevation_handler":
                return self._handle_elevation_data_sync(message)
            elif handler_type == "terrain_warning_handler":
                return self._handle_terrain_warning_sync(message)
            else:
                # Legacy fallback processing if detector doesn't recognize message
                if hasattr(message, 'message_type'):
                    message_type = message.message_type
                    if message_type == "MODE_CHANGE" or (hasattr(message, 'command_type') and message.command_type == "mode_change"):
                        # Extract mode value and request_id for parameter-based approach
                        mode_data = message.data
                        # Extract request_id for completion tracking
                        message_request_id = None
                        if hasattr(message, 'request_id'):
                            message_request_id = message.request_id
                        elif hasattr(message, 'metadata') and isinstance(message.metadata, dict) and 'request_id' in message.metadata:
                            message_request_id = message.metadata['request_id']

                        # Extract mode value and call handler with parameters
                        mode_value = self._extract_mode_value_from_data(mode_data)
                        return self._handle_mode_change_sync(mode_value, request_id=message_request_id)
                    elif message_type == "DATA" or (hasattr(message, 'command_type') and message.command_type == "data"):
                        return self._handle_data_request(message)

            # For logging purposes
            logger.info(f"[TFR_RADAR] Message successfully processed synchronously")
            return True

        except Exception as e:
            logger.error(f"[TFR_RADAR] Error processing message synchronously: {e}")
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
            logger.info(f"[TFR_RADAR] Handling mode change with value: {mode_value}, request_id: {request_id}")

            # Convert to enum
            try:
                new_mode = tfr_radarMode(mode_value)
                logger.info(f"[TFR_RADAR] Processed mode value {mode_value} to enum {new_mode.name}")

                # Save original mode before changing
                old_mode = self.mode

                # Set the mode directly
                self.set_mode(new_mode, send_completion=True, request_id=request_id)
                logger.info(f"[TFR_RADAR] Set TFR radar mode to {new_mode.name}")

                return True
            except ValueError as e:
                logger.error(f"[TFR_RADAR] Invalid mode value: {mode_value} is not a valid tfr_radarMode")
                return False
        except Exception as e:
            logger.error(f"[TFR_RADAR] Error handling mode change: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_elevation_data_sync(self, message):
        """
        Handle elevation data request synchronously.

        Args:
            message: The elevation data request message

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"[TFR_RADAR] Handling elevation data request synchronously")

            # Get the request parameters
            if hasattr(message, 'data') and isinstance(message.data, dict):
                scan_width = message.data.get('scan_width', self.scan_width)
            else:
                scan_width = self.scan_width

            # Send elevation data
            self._send_elevation_data(scan_width)

            return True
        except Exception as e:
            logger.error(f"[TFR_RADAR] Error handling elevation data request: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_terrain_warning_sync(self, message):
        """
        Handle terrain warning message synchronously.

        Args:
            message: The terrain warning message

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            logger.info(f"[TFR_RADAR] Handling terrain warning message synchronously")

            # Check for terrain warnings and send them
            warnings = self._check_terrain_warnings()

            # Send warnings
            for warning in warnings:
                warning_msg = TFRRadarTerrainWarning(
                    warning_uuid=str(time.time()),
                    warning_type=warning['type'],
                    distance=warning['distance'],
                    elevation=warning['elevation'],
                    message_header="terrain_warning",
                    sending_system="tfr_radar",
                    destination="radar_handler"
                )
                if self.radar_messenger:
                    self.radar_messenger.send_message(warning_msg)
                    logger.info(f"[TFR_RADAR] Sent terrain warning: {warning['type']}")

            return True
        except Exception as e:
            logger.error(f"[TFR_RADAR] Error handling terrain warning message: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_mode_change(self, message: MIL_STD_1553B_Message):
        """Handle mode change messages."""
        try:
            logger.info(f"[TFR_RADAR] Handling mode change message via parameter extraction")

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
            logger.error(f"[TFR_RADAR] Invalid mode value in message: {e}")
        except Exception as e:
            logger.error(f"[TFR_RADAR] Error handling mode change for {self.name}: {e}")
            logger.error(traceback.format_exc())

    def _handle_data_request(self, message: MIL_STD_1553B_Message):
        """Handle data request messages."""
        try:
            # Extract request ID from message
            request_id = None
            if hasattr(message, 'request_id'):
                request_id = message.request_id
            elif hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                request_id = message.metadata.get('request_id')

            logger.info(f"[TFR_RADAR] Data request ID: {request_id}")

            if self.mode not in [tfr_radarMode.SEARCH, tfr_radarMode.TRACK, tfr_radarMode.TERRAIN_FOLLOWING]:
                logger.warning(f"Cannot get data in {self.mode.name} mode")
                return False

            # Parse request parameters
            if hasattr(message, 'data') and isinstance(message.data, dict):
                request_type = message.data.get('request_type')
                if request_type == 'elevation':
                    scan_width = message.data.get('scan_width', self.scan_width)
                    self._send_elevation_data(scan_width, request_id)
                    return True
                elif request_type == 'terrain_following_profile':
                    self._send_terrain_following_profile(request_id)
                    return True
            else:
                # For backward compatibility, assume elevation data request
                self._send_elevation_data(self.scan_width, request_id)
                return True

            return False

        except Exception as e:
            logger.error(f"Error handling data request: {e}")

    def _send_elevation_data(self, scan_width: float, request_id=None):
        """
        Send elevation profile data.

        Args:
            scan_width: Width of the scan in meters
            request_id: The original request ID for completion tracking
        """
        try:
            # Create elevation profile message using radar-local message class
            # Run path optimisation and clearance assessment
            try:
                aircraft_alt_m = 1000.0  # FMS would supply real value
                self.clearance_manager.assess_profile(self.terrain_data, aircraft_alt_m)
                self.path_optimiser.compute_path(self.terrain_data, aircraft_alt_m)
                if self.clearance_manager.master_level == "PULL_UP":
                    logger.warning("[TFR_RADAR] PULL UP — terrain clearance critical")
            except Exception as _tf_exc:
                logger.warning(f"[TFR_RADAR] TFR processing error: {_tf_exc}")

            elevation_profile = TFRRadarElevationProfile(
                data_uuid=str(time.time()),
                profile_data=self.terrain_data,
                scan_width=scan_width,
                message_header="elevation_profile",
                sending_system="tfr_radar",
                destination="radar_handler",
                request_id=request_id
            )

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_tfr_data
                _items = [elevation_profile] + [
                    type('W', (), {
                        'profile_data': None,
                        'warning_type': w['type'],
                        'distance': w['distance'],
                        'elevation': w['elevation'],
                        'timestamp': time.time()
                    })()
                    for w in self._check_terrain_warnings()
                ]
                push_tfr_data([elevation_profile], request_id or elevation_profile.data_uuid)
                logger.info(f"[TFR_RADAR] Bridge: elevation profile pushed to display coordinator")
            except Exception as _bridge_exc:
                logger.warning(f"[TFR_RADAR] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

            # Send elevation data
            if self.radar_messenger:
                self.radar_messenger.send_message(elevation_profile)
                logger.info(f"Sent elevation profile with {len(self.terrain_data)} points")
            warnings = self._check_terrain_warnings()
            for warning in warnings:
                warning_msg = TFRRadarTerrainWarning(
                    warning_uuid=str(time.time()),
                    warning_type=warning['type'],
                    distance=warning['distance'],
                    elevation=warning['elevation'],
                    message_header="terrain_warning",
                    sending_system="tfr_radar",
                    destination="radar_handler"
                )
                if self.radar_messenger:
                    self.radar_messenger.send_message(warning_msg)
                    logger.info(f"Sent terrain warning: {warning['type']}")

        except Exception as e:
            logger.error(f"Error sending elevation data: {e}")

    def is_healthy(self) -> bool:
        """Check if radar is healthy."""
        return self._health_status and self.running

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
            logger.info(f"[TFR_RADAR] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")
            logger.info(f"[TFR_RADAR] Using request ID: {request_id}")

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()
            if not completion_handler:
                logger.error("[TFR_RADAR] Cannot send mode change completion - completion handler not available")
                return

            # Use the request_id parameter that was passed to this method
            # The request_id variable is passed from _handle_mode_change_sync to here
            completion_request_id = request_id
            logger.info(f"[TFR_RADAR] Using request_id from parameter: {completion_request_id}")

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=completion_request_id,  # Use the extracted request ID
                radar_type='tfr_radar'
            )

            if success:
                logger.info(f"[TFR_RADAR] Mode change completion notification sent successfully")
            else:
                logger.error(f"[TFR_RADAR] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[TFR_RADAR] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())

    def _send_terrain_following_profile(self, request_id=None):
        """
        Send terrain following profile data.

        This is specialized terrain data for terrain following operations.

        Args:
            request_id: The original request ID for completion tracking
        """
        try:
            # Filter terrain data to only include points relevant for terrain following
            terrain_following_points = []
            for distance, elevation in self.terrain_data:
                if distance < 5000:  # Focus on the closer terrain
                    terrain_following_points.append((distance, elevation))

            # Create terrain profile message
            profile = TFRRadarElevationProfile(
                data_uuid=str(time.time()),
                profile_data=terrain_following_points,
                scan_width=self.scan_width/2,  # Narrower focus for terrain following
                message_header="terrain_following_profile",
                sending_system="tfr_radar",
                destination="radar_handler",
                request_id=request_id
            )

            # Send terrain following profile
            if self.radar_messenger:
                self.radar_messenger.send_message(profile)
                logger.info(f"[TFR_RADAR] Sent terrain following profile with {len(terrain_following_points)} points and request ID: {request_id}")

                # Import the CompletionMessageHandler for data completion
                from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

                # Get the CompletionMessageHandler instance
                completion_handler = get_completion_message_handler()

                # Send the data completion message SYNCHRONOUSLY
                if completion_handler:
                    success = completion_handler.send_data_completion(
                        system_name='radar',
                        data_type='terrain_following_profile',
                        data=profile,
                        request_id=request_id
                    )

                    if success:
                        logger.info(f"[TFR_RADAR] Sent terrain following profile completion notification with request ID: {request_id}")
                    else:
                        logger.error(f"[TFR_RADAR] Failed to send terrain following profile completion notification")
                else:
                    logger.error("[TFR_RADAR] Cannot send data completion - completion handler not available")

        except Exception as e:
            logger.error(f"[TFR_RADAR] Error sending terrain following profile: {str(e)}")
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
                logger.info(f"[TFR_RADAR] Extracted mode value: {mode_value} from data: {mode_data}")
                return mode_value
            else:
                logger.error(f"[TFR_RADAR] Empty mode data")
                return 0
        except Exception as e:
            logger.error(f"[TFR_RADAR] Error extracting mode value: {e}")
            logger.error(traceback.format_exc())
            # Default to STANDBY (0) on error
            return 0

    def get_status(self) -> Dict:
        """Get radar status."""
        with self._lock:
            return {
                'name': self.name,
                'mode': self.mode.name,
                'running': self.running,
                'healthy': self._health_status,
                'scan_range': self.scan_range,
                'scan_width': self.scan_width
            }
