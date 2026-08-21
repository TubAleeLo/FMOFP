"""
Targeting Radar System

Handles targeting radar operations using direct message handling.
"""

import time
import threading
import traceback
import numpy as np
from typing import Dict, Optional
from Systems.radarManagement.radar_enums import targeting_radarMode
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
# Import radar-local message definitions to enforce system boundaries
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.targeting_data import (
    TargetingRadarTrackData,
    TargetingRadarLockData
)
# Import message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    TARGETING_RADAR_TRACK_RESPONSE,
    TARGETING_RADAR_LOCK_RESPONSE,
    COMMAND_TYPE_TRACK_DATA,
    COMMAND_TYPE_LOCK_DATA
)

from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.targeting.target_processor import TargetProcessor

logger = get_logger()

class targeting_radar:
    def __init__(self, name: str, radar_control, radar_messenger):
        self.name = name
        self.mode = targeting_radarMode.STANDBY
        self.radar_control = radar_control
        self.radar_messenger = radar_messenger
        self.running = False
        self._lock = threading.Lock()
        self._health_status = True

        # Targeting specific parameters
        self.max_range = 100000  # meters
        self.current_targets = {}  # track_id -> target_data
        self.next_track_id = 1
        self.locked_track_id = None
        self.lock_quality = 0.0
        self.jamming_detected = False
        # Signal-processing capability modules
        self.target_processor = TargetProcessor()

        logger.info(f"Targeting radar {name} initialized")

    def _generate_target(self) -> Dict:
        """Generate a simulated target."""
        # Random position within range
        r = np.random.uniform(1000, self.max_range)
        theta = np.random.uniform(0, 2*np.pi)
        phi = np.random.uniform(-np.pi/6, np.pi/6)  # Limited elevation angle

        x = r * np.cos(phi) * np.cos(theta)
        y = r * np.cos(phi) * np.sin(theta)
        z = r * np.sin(phi)

        # Random velocity components (realistic speeds)
        v_mag = np.random.uniform(100, 300)  # m/s
        v_theta = np.random.uniform(0, 2*np.pi)
        v_phi = np.random.uniform(-np.pi/6, np.pi/6)

        vx = v_mag * np.cos(v_phi) * np.cos(v_theta)
        vy = v_mag * np.cos(v_phi) * np.sin(v_theta)
        vz = v_mag * np.sin(v_phi)

        # Random acceleration components
        a_mag = np.random.uniform(0, 30)  # m/s²
        ax = a_mag * np.random.normal()
        ay = a_mag * np.random.normal()
        az = a_mag * np.random.normal()

        # Classification based on speed and altitude
        if v_mag > 250:
            classification = "FIGHTER"
        elif abs(z) > 10000:
            classification = "HIGH_ALT"
        else:
            classification = "UNKNOWN"

        return {
            'position': (float(x), float(y), float(z)),
            'velocity': (float(vx), float(vy), float(vz)),
            'acceleration': (float(ax), float(ay), float(az)),
            'classification': classification,
            'identity': "UNKNOWN",
            'rcs': np.random.uniform(1, 10),  # Radar Cross Section in m²
            'snr': np.random.uniform(10, 30),  # Signal-to-Noise Ratio in dB
            'last_update': time.time()
        }

    def _update_targets(self):
        """Update target positions based on their velocities and accelerations."""
        current_time = time.time()

        with self._lock:
            # Update existing targets
            for track_id, target in list(self.current_targets.items()):
                dt = current_time - target['last_update']

                # Update position based on velocity and acceleration
                px, py, pz = target['position']
                vx, vy, vz = target['velocity']
                ax, ay, az = target['acceleration']

                # Update velocity with acceleration
                new_vx = vx + ax * dt
                new_vy = vy + ay * dt
                new_vz = vz + az * dt

                # Update position with new velocity
                new_x = px + 0.5 * (vx + new_vx) * dt
                new_y = py + 0.5 * (vy + new_vy) * dt
                new_z = pz + 0.5 * (vz + new_vz) * dt

                # Remove targets that are out of range
                if np.sqrt(new_x**2 + new_y**2 + new_z**2) > self.max_range:
                    if track_id == self.locked_track_id:
                        self.locked_track_id = None
                        self.lock_quality = 0.0
                    del self.current_targets[track_id]
                    continue

                # Update target state
                target['position'] = (new_x, new_y, new_z)
                target['velocity'] = (new_vx, new_vy, new_vz)
                target['last_update'] = current_time

                # Update SNR based on range
                range_to_target = np.sqrt(new_x**2 + new_y**2 + new_z**2)
                target['snr'] = 30 - 20 * np.log10(range_to_target / 1000)  # Simple SNR model

            # Add new targets randomly in SEARCH mode
            if self.mode == targeting_radarMode.SEARCH and len(self.current_targets) < 5:
                if np.random.random() < 0.1:  # 10% chance per update
                    self.current_targets[self.next_track_id] = self._generate_target()
                    self.next_track_id += 1

            # Update lock quality for locked target
            if self.locked_track_id is not None and self.locked_track_id in self.current_targets:
                target = self.current_targets[self.locked_track_id]
                self.lock_quality = min(1.0, target['snr'] / 30)  # Simple lock quality model
                self.jamming_detected = np.random.random() < 0.05  # 5% chance of jamming

    def _run_target_processing(self) -> None:
        """Run signature analysis and stealth detection on all active tracks."""
        try:
            with self._lock:
                self.target_processor.process_tracks(self.current_targets)
        except Exception as exc:
            logger.error(f"[TARGETING] Processor error: {exc}")

    def _get_target_range_data(self, track_id: int) -> Optional[Dict]:
        """Get range data for a specific target."""
        if track_id not in self.current_targets:
            return None

        target = self.current_targets[track_id]
        x, y, z = target['position']
        vx, vy, vz = target['velocity']

        # Calculate range and range rate
        range_to_target = np.sqrt(x**2 + y**2 + z**2)
        range_rate = (x*vx + y*vy + z*vz) / range_to_target

        # Calculate angles
        azimuth = np.arctan2(y, x)
        elevation = np.arctan2(z, np.sqrt(x**2 + y**2))

        return {
            'range': range_to_target,
            'range_rate': range_rate,
            'azimuth': azimuth,
            'elevation': elevation
        }

    def start(self):
        """Start the targeting radar system."""
        try:
            logger.info(f"Starting targeting radar {self.name}")
            with self._lock:
                if self.running:
                    logger.warning(f"Targeting radar {self.name} already running")
                    return
                self.running = True
                self.mode = targeting_radarMode.STANDBY
            logger.info(f"Targeting radar {self.name} started")
        except Exception as e:
            logger.error(f"Error starting targeting radar {self.name}: {str(e)}")
            self._health_status = False

    def stop(self):
        """Stop the targeting radar system."""
        try:
            logger.info(f"Stopping targeting radar {self.name}")
            with self._lock:
                if not self.running:
                    logger.warning(f"Targeting radar {self.name} already stopped")
                    return
                self.running = False
                self.mode = targeting_radarMode.STANDBY
            logger.info(f"Targeting radar {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping targeting radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            self._health_status = False

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
            logger.info(f"[TARGETING_RADAR] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")
            logger.info(f"[TARGETING_RADAR] Using request ID: {request_id}")

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()
            if not completion_handler:
                logger.error("[TARGETING_RADAR] Cannot send mode change completion - completion handler not available")
                return

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=request_id,
                radar_type='targeting_radar'  # Add explicit radar type
            )

            if success:
                logger.info(f"[TARGETING_RADAR] Mode change completion notification sent successfully")
            else:
                logger.error(f"[TARGETING_RADAR] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[TARGETING_RADAR] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())

    def set_mode(self, mode, send_completion=True, request_id=None):
        """
        Set radar mode.

        Args:
            mode: The new mode to set
            send_completion: Whether to send a mode change completion notification (default: True)
            request_id: The request ID to include in the completion message
        """
        try:
            if not isinstance(mode, targeting_radarMode):
                raise ValueError(f"Invalid mode type for targeting radar: {type(mode)}")

            with self._lock:
                old_mode = self.mode
                self.mode = mode
                logger.info(f"Targeting radar {self.name} mode changed from {old_mode.name} to {mode.name}")

                # Clear targets when entering STANDBY
                if mode == targeting_radarMode.STANDBY:
                    self.current_targets.clear()
                    self.locked_track_id = None
                    self.lock_quality = 0.0

                # Send mode change completion notification if requested
                if send_completion:
                    logger.info(f"[TARGETING_RADAR] Sending mode change completion notification (send_completion=True)")
                    self._send_mode_change_completion(old_mode, mode, request_id)
                else:
                    logger.info(f"[TARGETING_RADAR] Skipping mode change completion notification (send_completion=False)")
        except Exception as e:
            logger.error(f"Error setting mode for targeting radar {self.name}: {str(e)}")

    def receive_message(self, message: MIL_STD_1553B_Message):
        """Handle incoming messages directly."""
        try:
            if not isinstance(message, MIL_STD_1553B_Message):
                logger.warning(f"Invalid message type received: {type(message)}")
                return

            if message.message_type == "MODE_CHANGE":
                self._handle_mode_change(message)
            elif message.message_type == "TRACK_DATA_REQUEST":
                self._handle_track_request(message)
            elif message.message_type == "LOCK_REQUEST":
                self._handle_lock_request(message)
            else:
                logger.debug(f"Unhandled message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error handling message for targeting radar {self.name}: {str(e)}")
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
                logger.info(f"[TARGETING_RADAR] Extracted mode value: {mode_value} from data: {mode_data}")
                return mode_value
            else:
                logger.error(f"[TARGETING_RADAR] Empty mode data")
                return 0
        except Exception as e:
            logger.error(f"[TARGETING_RADAR] Error extracting mode value: {e}")
            logger.error(traceback.format_exc())
            # Default to STANDBY (0) on error
            return 0

    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for Targeting radar.

        This is used by the RadarMessenger for direct message handling.
        Required by RadarMessenger.py _message_loop for direct message handling.

        Args:
            message: The message to process

        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            logger.info(f"[TARGETING_RADAR] Synchronously processing message with ID: {id(message)}")

            # Log message details for debugging
            if hasattr(message, 'message_type'):
                logger.info(f"[TARGETING_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                logger.info(f"[TARGETING_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[TARGETING_RADAR] Command name: {message.command_name}")

            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}

            # Mark as processed by Targeting radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []

                if 'targeting_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('targeting_radar')

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
                elif message_type == "TRACK_DATA_REQUEST" or (hasattr(message, 'command_type') and message.command_type == "track_data"):
                    self._handle_track_request(message)
                elif message_type == "LOCK_REQUEST" or (hasattr(message, 'command_type') and message.command_type == "lock_request"):
                    self._handle_lock_request(message)

            # For logging purposes
            logger.info(f"[TARGETING_RADAR] Message successfully processed synchronously")
            return True

        except Exception as e:
            logger.error(f"[TARGETING_RADAR] Error processing message synchronously: {e}")
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
            logger.info(f"[TARGETING_RADAR] Handling mode change with value: {mode_value}, request_id: {request_id}")

            # Convert to enum
            try:
                new_mode = targeting_radarMode(mode_value)
                logger.info(f"[TARGETING_RADAR] Processed mode value {mode_value} to enum {new_mode.name}")

                # Save original mode before changing
                old_mode = self.mode

                # Set the mode with completion
                self.set_mode(new_mode, send_completion=True, request_id=request_id)
                logger.info(f"[TARGETING_RADAR] Set targeting radar mode to {new_mode.name}")

                return True
            except ValueError as e:
                logger.error(f"[TARGETING_RADAR] Invalid mode value: {mode_value} is not a valid targeting_radarMode")
                return False
        except Exception as e:
            logger.error(f"[TARGETING_RADAR] Error handling mode change: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_mode_change(self, message: MIL_STD_1553B_Message):
        """Handle mode change messages."""
        try:
            logger.info(f"[TARGETING_RADAR] Handling mode change message via parameter extraction")

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
            logger.error(f"[TARGETING_RADAR] Invalid mode value in message: {e}")
        except Exception as e:
            logger.error(f"[TARGETING_RADAR] Error handling mode change for {self.name}: {e}")
            logger.error(traceback.format_exc())

    def _handle_track_request(self, message: MIL_STD_1553B_Message):
        """Handle track data request messages."""
        try:
            if self.mode == targeting_radarMode.STANDBY:
                logger.warning("Cannot provide track data in STANDBY mode")
                return

            # Update target positions
            self._update_targets()
            # Run signature analysis + stealth detection on enriched tracks
            self._run_target_processing()

            # Send track data for each target
            for track_id, target in self.current_targets.items():
                # Basic track data using radar-local message class
                track_data = TargetingRadarTrackData(
                    track_uuid=str(time.time()),
                    target_position=target['position'],
                    target_velocity=target['velocity'],
                    target_id=str(track_id),
                    confidence=target['snr'] / 30,
                    message_header="track_data",
                    sending_system="targeting_radar",
                    destination="radar_handler",
                    command_type=COMMAND_TYPE_TRACK_DATA,
                    command_name="TARGETING_RADAR_TRACK"
                )

                # Get range data and include it in the track data
                range_data = self._get_target_range_data(track_id)

                # Add lock data if this target is locked
                if self.locked_track_id == track_id:
                    lock_data = TargetingRadarLockData(
                        lock_uuid=str(time.time()),
                        target_position=target['position'],
                        lock_status="LOCKED" if self.lock_quality > 0.5 else "ACQUIRING",
                        target_id=str(track_id),
                        lock_time=time.time(),
                        message_header="lock_data",
                        sending_system="targeting_radar",
                        destination="radar_handler",
                        command_type=COMMAND_TYPE_LOCK_DATA,
                        command_name="TARGETING_RADAR_LOCK"
                    )
                    # Send lock data through radar messenger
                    if self.radar_messenger:
                        self.radar_messenger.send_message(lock_data)

                # Send through radar messenger
                if self.radar_messenger:
                    self.radar_messenger.send_message(track_data)

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            # Push all current targets straight into the UI coordinator so
            # TargetingRadarDisplay receives them on its next paint cycle.
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_targeting_data
                import uuid as _uuid
                _req_id = str(_uuid.uuid4())
                _targets = list(self.current_targets.values())
                push_targeting_data(_targets, _req_id)
                logger.info(f"[TARGETING_RADAR] Bridge: {len(_targets)} targets pushed to display")
            except Exception as _bridge_exc:
                logger.warning(f"[TARGETING_RADAR] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

        except Exception as e:
            logger.error(f"Error handling track request: {e}")

    def _handle_lock_request(self, message: MIL_STD_1553B_Message):
        """Handle lock request messages."""
        try:
            if self.mode != targeting_radarMode.TRACK:
                logger.warning("Cannot lock target when not in TRACK mode")
                return

            # Extract track ID from message
            track_id = int(message.data, 2)

            if track_id in self.current_targets:
                self.locked_track_id = track_id
                self.lock_quality = min(1.0, self.current_targets[track_id]['snr'] / 30)
                logger.info(f"Locked onto track {track_id} with quality {self.lock_quality:.2f}")
            else:
                logger.warning(f"Cannot lock onto non-existent track {track_id}")

        except Exception as e:
            logger.error(f"Error handling lock request: {e}")

    def is_healthy(self) -> bool:
        """Check if radar is healthy."""
        return self._health_status and self.running

    def get_status(self) -> Dict:
        """Get radar status."""
        with self._lock:
            status = {
                'name': self.name,
                'mode': self.mode.name,
                'running': self.running,
                'healthy': self._health_status,
                'max_range': self.max_range,
                'active_tracks': len(self.current_targets)
            }

            if self.locked_track_id is not None:
                status.update({
                    'locked_track': self.locked_track_id,
                    'lock_quality': self.lock_quality,
                    'jamming_detected': self.jamming_detected
                })

            return status
