"""
Airborne Early Warning and Control (AEWC) Radar System

Handles AEWC radar operations using direct message handling.
"""

import time
import traceback
import threading
import numpy as np
from typing import Dict, List, Tuple, Optional
from Systems.radarManagement.radar_enums import aewc_radarMode
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
# Import radar-local message definitions to enforce system boundaries
from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.aewc_data import (
    AEWCRadarTrackData,
    AEWCRadarSectorScan
)
# Import message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    AEWC_RADAR_TRACK_RESPONSE,
    AEWC_RADAR_SECTOR_SCAN_RESPONSE,
    COMMAND_TYPE_TRACK_DATA,
    COMMAND_TYPE_SECTOR_SCAN_DATA
)
from Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.aewc.aewc_processor import SectorPriorityManager, ElectronicProtection

logger = get_logger()

class Sector:
    def __init__(self, sector_id: str, azimuth_range: Tuple[float, float],
                 elevation_range: Tuple[float, float], priority: int = 1):
        self.sector_id = sector_id
        self.azimuth_range = azimuth_range
        self.elevation_range = elevation_range
        self.priority = priority
        self.scan_progress = 0.0
        self.last_scan_time = 0.0
        self.active_tracks: List[int] = []

class aewc_radar:
    def __init__(self, name: str, radar_control, radar_messenger):
        self.name = name
        self.mode = aewc_radarMode.STANDBY
        self.radar_control = radar_control
        self.radar_messenger = radar_messenger
        self.running = False
        self._lock = threading.Lock()
        self._health_status = True

        # AEWC specific parameters
        self.max_range = 400000  # meters (longer range than targeting radar)
        self.current_targets = {}  # track_id -> target_data
        self.next_track_id = 1
        self.stealth_probability = 0.2  # Probability of detecting stealth aircraft

        # Sector management
        self.sectors: Dict[str, Sector] = {}
        self._initialize_sectors()

        # Environmental conditions
        self.noise_floor = -110  # dBm
        self.clutter_map = {}
        self.interference_zones = []
        self.propagation_conditions = {
            'ducting': False,
            'humidity': 0.5,
            'temperature': 20.0
        }

        # Capability modules
        self.sector_priority = SectorPriorityManager(list(self.sectors.keys()))
        self.ecm_protection  = ElectronicProtection()
        logger.info(f"AEWC radar {name} initialized")

    def _initialize_sectors(self):
        """Initialize default radar coverage sectors."""
        # Create 6 main sectors covering 360 degrees
        for i in range(6):
            sector_id = f"SECTOR_{i+1}"
            azimuth_start = i * 60
            azimuth_end = (i + 1) * 60
            elevation_range = (-15, 45)  # Typical AEWC elevation coverage
            self.sectors[sector_id] = Sector(
                sector_id=sector_id,
                azimuth_range=(azimuth_start, azimuth_end),
                elevation_range=elevation_range,
                priority=1
            )

    def _generate_target(self) -> Dict:
        """Generate a simulated air target."""
        # Random position within range
        r = np.random.uniform(5000, self.max_range)
        theta = np.random.uniform(0, 2*np.pi)
        phi = np.random.uniform(-np.pi/4, np.pi/4)  # Wider elevation angle than targeting radar

        x = r * np.cos(phi) * np.cos(theta)
        y = r * np.cos(phi) * np.sin(theta)
        z = r * np.sin(phi)

        # Random velocity components (realistic aircraft speeds)
        v_mag = np.random.uniform(150, 500)  # m/s (higher speed range)
        v_theta = np.random.uniform(0, 2*np.pi)
        v_phi = np.random.uniform(-np.pi/6, np.pi/6)

        vx = v_mag * np.cos(v_phi) * np.cos(v_theta)
        vy = v_mag * np.cos(v_phi) * np.sin(v_theta)
        vz = v_mag * np.sin(v_phi)

        # Random acceleration components
        a_mag = np.random.uniform(0, 50)  # m/s²
        ax = a_mag * np.random.normal()
        ay = a_mag * np.random.normal()
        az = a_mag * np.random.normal()

        # Determine if target is stealth
        is_stealth = np.random.random() < 0.3  # 30% chance of stealth aircraft

        # Generate RCS based on aircraft type
        if is_stealth:
            rcs = np.random.uniform(0.01, 0.1)  # m² (stealth aircraft)
        else:
            rcs = np.random.uniform(1, 100)  # m² (conventional aircraft)

        # Classification based on speed, altitude, and stealth
        if is_stealth:
            classification = "STEALTH"
        elif v_mag > 400:
            classification = "FIGHTER"
        elif abs(z) > 30000:
            classification = "HIGH_ALT"
        else:
            classification = "UNKNOWN"

        return {
            'position': (float(x), float(y), float(z)),
            'velocity': (float(vx), float(vy), float(vz)),
            'acceleration': (float(ax), float(ay), float(az)),
            'classification': classification,
            'identity': "UNKNOWN",
            'is_stealth': is_stealth,
            'rcs': rcs,
            'snr': 0.0,  # Will be updated during processing
            'last_update': time.time()
        }

    def _get_target_sector(self, target_position: Tuple[float, float, float]) -> Optional[str]:
        """Determine which sector a target is in."""
        x, y, z = target_position
        azimuth = np.degrees(np.arctan2(y, x)) % 360
        elevation = np.degrees(np.arctan2(z, np.sqrt(x*x + y*y)))

        for sector_id, sector in self.sectors.items():
            az_start, az_end = sector.azimuth_range
            el_start, el_end = sector.elevation_range

            if az_start <= azimuth < az_end and el_start <= elevation < el_end:
                return sector_id

        return None

    def _calculate_snr(self, target: Dict) -> float:
        """Calculate Signal-to-Noise Ratio for a target."""
        x, y, z = target['position']
        range_to_target = np.sqrt(x*x + y*y + z*z)

        # Basic radar equation with environmental factors
        tx_power = 100000  # 100 kW
        wavelength = 0.03  # 10 GHz
        antenna_gain = 10000  # 40 dB

        # Calculate received power
        received_power = (tx_power * antenna_gain**2 * wavelength**2 * target['rcs']) / \
                        ((4*np.pi)**3 * range_to_target**4)

        # Convert to dB
        received_power_db = 10 * np.log10(received_power)

        # Account for environmental conditions
        if self.propagation_conditions['ducting']:
            received_power_db += 10

        # Calculate SNR
        snr = received_power_db - self.noise_floor

        return max(0, snr)  # Ensure non-negative SNR

    def _update_targets(self):
        """Update target positions and handle stealth detection."""
        current_time = time.time()

        with self._lock:
            # Clear sector track lists
            for sector in self.sectors.values():
                sector.active_tracks.clear()

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
                    del self.current_targets[track_id]
                    continue

                # Update target state
                target['position'] = (new_x, new_y, new_z)
                target['velocity'] = (new_vx, new_vy, new_vz)
                target['last_update'] = current_time

                # Calculate new SNR
                target['snr'] = self._calculate_snr(target)

                # Handle stealth aircraft detection
                if target['is_stealth']:
                    detection_probability = self.stealth_probability * (target['snr'] / 30)
                    if np.random.random() > detection_probability:
                        continue  # Skip updating stealth target (represents failed detection)

                # Update sector assignment
                sector_id = self._get_target_sector(target['position'])
                if sector_id and sector_id in self.sectors:
                    self.sectors[sector_id].active_tracks.append(track_id)

            # Add new targets randomly in SEARCH mode
            if self.mode == aewc_radarMode.SEARCH and len(self.current_targets) < 10:
                if np.random.random() < 0.1:  # 10% chance per update
                    self.current_targets[self.next_track_id] = self._generate_target()
                    self.next_track_id += 1

            # Update sector scan progress
            for sector in self.sectors.values():
                if current_time - sector.last_scan_time > 1.0:  # 1 second update rate
                    sector.scan_progress = (sector.scan_progress + 0.1) % 1.0
                    sector.last_scan_time = current_time

    def _run_aewc_processing(self) -> None:
        """Run sector prioritisation and ECM assessment on this update cycle."""
        try:
            sector_counts: dict = {sid: 0 for sid in self.sectors}
            sector_hostile: dict = {sid: 0 for sid in self.sectors}
            with self._lock:
                for tdata in self.current_targets.values():
                    sid = self._get_target_sector(tdata.get('position', (0, 0, 0)))
                    if sid:
                        sector_counts[sid] = sector_counts.get(sid, 0) + 1

            jammed = self.ecm_protection.get_jammed_sectors()
            self.sector_priority.update(sector_counts, sector_hostile, jammed)

            import random
            for sid in self.sectors:
                noise = self.noise_floor + random.gauss(0, 3)
                self.ecm_protection.assess_sector(sid, noise)
            self.ecm_protection.cleanup_stale()
        except Exception as exc:
            logger.error(f"[AEWC] AEWC processing error: {exc}")

    def start(self):
        """Start the AEWC radar system."""
        try:
            logger.info(f"Starting AEWC radar {self.name}")
            with self._lock:
                if self.running:
                    logger.warning(f"AEWC radar {self.name} already running")
                    return
                self.running = True
                self.mode = aewc_radarMode.STANDBY
            logger.info(f"AEWC radar {self.name} started")
        except Exception as e:
            logger.error(f"Error starting AEWC radar {self.name}: {str(e)}")
            self._health_status = False

    def stop(self):
        """Stop the AEWC radar system."""
        try:
            logger.info(f"Stopping AEWC radar {self.name}")
            with self._lock:
                if not self.running:
                    logger.warning(f"AEWC radar {self.name} already stopped")
                    return
                self.running = False
                self.mode = aewc_radarMode.STANDBY
            logger.info(f"AEWC radar {self.name} stopped")
        except Exception as e:
            logger.error(f"Error stopping AEWC radar {self.name}: {str(e)}")
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
            logger.info(f"[AEWC_RADAR] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")
            logger.info(f"[AEWC_RADAR] Using request ID: {request_id}")

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()
            if not completion_handler:
                logger.error("[AEWC_RADAR] Cannot send mode change completion - completion handler not available")
                return

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=request_id,
                radar_type='aewc_radar'  # Add explicit radar type
            )

            if success:
                logger.info(f"[AEWC_RADAR] Mode change completion notification sent successfully")
            else:
                logger.error(f"[AEWC_RADAR] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[AEWC_RADAR] Error sending mode change completion: {str(e)}")
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
            if not isinstance(mode, aewc_radarMode):
                raise ValueError(f"Invalid mode type for AEWC radar: {type(mode)}")

            with self._lock:
                old_mode = self.mode
                self.mode = mode
                logger.info(f"AEWC radar {self.name} mode changed from {old_mode.name} to {mode.name}")

                # Clear targets when entering STANDBY
                if mode == aewc_radarMode.STANDBY:
                    self.current_targets.clear()
                    for sector in self.sectors.values():
                        sector.active_tracks.clear()
                        sector.scan_progress = 0.0

                # Send mode change completion notification if requested
                if send_completion:
                    logger.info(f"[AEWC_RADAR] Sending mode change completion notification (send_completion=True)")
                    self._send_mode_change_completion(old_mode, mode, request_id)
                else:
                    logger.info(f"[AEWC_RADAR] Skipping mode change completion notification (send_completion=False)")
        except Exception as e:
            logger.error(f"Error setting mode for AEWC radar {self.name}: {str(e)}")

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
            elif message.message_type == "SECTOR_SCAN_REQUEST":
                self._handle_sector_scan_request(message)
            else:
                logger.debug(f"Unhandled message type: {message.message_type}")

        except Exception as e:
            logger.error(f"Error handling message for AEWC radar {self.name}: {str(e)}")
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
                logger.info(f"[AEWC_RADAR] Extracted mode value: {mode_value} from data: {mode_data}")
                return mode_value
            else:
                logger.error(f"[AEWC_RADAR] Empty mode data")
                return 0
        except Exception as e:
            logger.error(f"[AEWC_RADAR] Error extracting mode value: {e}")
            logger.error(traceback.format_exc())
            # Default to STANDBY (0) on error
            return 0

    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for AEWC radar.

        This is used by the RadarMessenger for direct message handling.
        Required by RadarMessenger.py _message_loop for direct message handling.

        Args:
            message: The message to process

        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            logger.info(f"[AEWC_RADAR] Synchronously processing message with ID: {id(message)}")

            # Log message details for debugging
            if hasattr(message, 'message_type'):
                logger.info(f"[AEWC_RADAR] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                logger.info(f"[AEWC_RADAR] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[AEWC_RADAR] Command name: {message.command_name}")

            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}

            # Mark as processed by AEWC radar
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []

                if 'aewc_radar' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('aewc_radar')

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
                elif message_type == "SECTOR_SCAN_REQUEST" or (hasattr(message, 'command_type') and message.command_type == "sector_scan"):
                    self._handle_sector_scan_request(message)

            # For logging purposes
            logger.info(f"[AEWC_RADAR] Message successfully processed synchronously")
            return True

        except Exception as e:
            logger.error(f"[AEWC_RADAR] Error processing message synchronously: {e}")
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
            logger.info(f"[AEWC_RADAR] Handling mode change with value: {mode_value}, request_id: {request_id}")

            # Convert to enum
            try:
                new_mode = aewc_radarMode(mode_value)
                logger.info(f"[AEWC_RADAR] Processed mode value {mode_value} to enum {new_mode.name}")

                # Save original mode before changing
                old_mode = self.mode

                # Set the mode with completion and pass through the request_id
                self.set_mode(new_mode, send_completion=True, request_id=request_id)
                logger.info(f"[AEWC_RADAR] Set AEWC radar mode to {new_mode.name}")

                return True
            except ValueError as e:
                logger.error(f"[AEWC_RADAR] Invalid mode value: {mode_value} is not a valid aewc_radarMode")
                return False
        except Exception as e:
            logger.error(f"[AEWC_RADAR] Error handling mode change: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_mode_change(self, message: MIL_STD_1553B_Message):
        """Handle mode change messages."""
        try:
            logger.info(f"[AEWC_RADAR] Handling mode change message via parameter extraction")

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
            logger.error(f"[AEWC_RADAR] Invalid mode value in message: {e}")
        except Exception as e:
            logger.error(f"[AEWC_RADAR] Error handling mode change for {self.name}: {e}")
            logger.error(traceback.format_exc())

    def _handle_track_request(self, message: MIL_STD_1553B_Message):
        """Handle track data request messages."""
        try:
            if self.mode == aewc_radarMode.STANDBY:
                logger.warning("Cannot provide track data in STANDBY mode")
                return

            # Update target positions
            self._update_targets()
            self._run_aewc_processing()

            # Send track data for each target
            for track_id, target in self.current_targets.items():
                # Create track data using radar-local message class
                # Including all data in a single message - position, velocity, track info
                track_data = AEWCRadarTrackData(
                    track_uuid=str(time.time()),
                    track_positions=[target['position']],
                    track_velocities=[target['velocity']],
                    track_timestamps=[time.time()],
                    track_id=str(track_id),
                    track_type=target['classification'],
                    track_confidence=target['snr'] / 30,
                    message_header="track_data",
                    sending_system="aewc_radar",
                    destination="radar_handler",
                    command_type=COMMAND_TYPE_TRACK_DATA,
                    command_name="AEWC_RADAR_TRACK"
                )

                # Send consolidated track data through radar messenger
                if self.radar_messenger:
                    self.radar_messenger.send_message(track_data)

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_aewc_data
                import uuid as _uuid
                _track_objects = []
                for _tid, _tgt in self.current_targets.items():
                    _track_objects.append({
                        'position':         _tgt['position'],
                        'velocity':         _tgt['velocity'],
                        'track_id':         str(_tid),
                        'track_type':       _tgt.get('classification', 'UNKNOWN'),
                        'track_confidence': float(_tgt.get('snr', 0)) / 30,
                        'timestamp':        time.time(),
                        'id':               str(_tid),
                    })
                if _track_objects:
                    push_aewc_data(_track_objects, str(_uuid.uuid4()))
                    logger.info(f"[AEWC_RADAR] Bridge: {len(_track_objects)} tracks pushed to display")
            except Exception as _bridge_exc:
                logger.warning(f"[AEWC_RADAR] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

        except Exception as e:
            logger.error(f"Error handling track request: {e}")

    def _handle_sector_scan_request(self, message: MIL_STD_1553B_Message):
        """Handle sector scan request messages."""
        try:
            if self.mode != aewc_radarMode.SEARCH:
                logger.warning("Cannot perform sector scan when not in SEARCH mode")
                return

            # Update all targets and sectors
            self._update_targets()

            # Send sector data for each sector
            for sector_id, sector in self.sectors.items():
                # Create sector scan data using radar-local message class
                sector_scan = AEWCRadarSectorScan(
                    scan_uuid=str(time.time()),
                    sector_data=[],  # Empty list as placeholder for actual sector data
                    sector_bounds={
                        'azimuth_start': sector.azimuth_range[0],
                        'azimuth_end': sector.azimuth_range[1],
                        'elevation_start': sector.elevation_range[0],
                        'elevation_end': sector.elevation_range[1],
                        'scan_progress': sector.scan_progress,
                        'active_tracks': sector.active_tracks
                    },
                    scan_resolution=1.0,  # Assumed default value
                    scan_timestamp=time.time(),
                    message_header="sector_scan",
                    sending_system="aewc_radar",
                    destination="radar_handler",
                    command_type=COMMAND_TYPE_SECTOR_SCAN_DATA,
                    command_name="AEWC_RADAR_SECTOR_SCAN"
                )

                # Send sector scan data
                if self.radar_messenger:
                    self.radar_messenger.send_message(sector_scan)

            # Environmental data is now incorporated into the sector scan messages
            # This consolidates the data and reduces message count

        except Exception as e:
            logger.error(f"Error handling sector scan request: {e}")

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
                'active_tracks': len(self.current_targets),
                'stealth_detection_probability': self.stealth_probability,
                'sectors': {
                    sector_id: {
                        'scan_progress': sector.scan_progress,
                        'active_tracks': len(sector.active_tracks)
                    }
                    for sector_id, sector in self.sectors.items()
                },
                'environmental_conditions': {
                    'noise_floor': self.noise_floor,
                    'propagation': self.propagation_conditions
                }
            }
            return status
