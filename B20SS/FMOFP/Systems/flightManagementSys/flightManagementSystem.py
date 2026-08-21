import threading
import time
import json
import math
import traceback
from datetime import datetime
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.core.event_driven_communication import get_event_bus
from FMOFP.Systems.flightManagementSys.flightControlSys.flight_control_system import get_flight_control_system
from FMOFP.Systems.flightManagementSys.flightControlSys.flight_dynamics_processor import get_flight_dynamics_processor
from FMOFP.Systems.flightManagementSys.flightControlSys.control_surface_manager import get_control_surface_manager
from FMOFP.Systems.flightManagementSys.flightControlSys.attitude_calculator import get_attitude_calculator
from FMOFP.Systems.nav.gps.globalPositionSystem import GPSSystem
from FMOFP.Systems.nav.dataFusion.fuseData import NavDataFusion

logger = get_logger()

class flightManagementSystem:
    """
    Flight Management System (FMS) for aircraft.

    This system integrates navigation, flight control, and tactical systems
    to provide comprehensive flight management capabilities for operations.
    """
    def __init__(self):
        self.messenger = None
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.event_bus = get_event_bus()
        self.thread = None
        self.update_rate = 0.05  # 20Hz update rate

        # Initialize Flight Control System
        self.flight_control_system = None
        self.init_flight_control_system()

        # Flight parameters with attributes
        self.attitude = {
            'roll': 0,       # Roll angle in degrees
            'pitch': 0,      # Pitch angle in degrees
            'yaw': 0,        # Yaw angle in degrees
            'roll_rate': 0,  # Roll rate in degrees/second
            'pitch_rate': 0, # Pitch rate in degrees/second
            'yaw_rate': 0,   # Yaw rate in degrees/second
        }

        self.velocity = {
            'airspeed': 0,        # Aircraft airspeed in knots
            'ground_speed': 0,    # Ground speed in knots
            'vertical_speed': 0,  # Vertical speed in feet/minute
            'mach': 0,            # Mach number
        }

        self.navigation = {
            'latitude': 0,        # Current latitude
            'longitude': 0,       # Current longitude
            'altitude': 0,        # Current altitude in feet
            'heading': 0,         # Current heading in degrees
            'track': 0,           # Ground track in degrees
            'waypoints': [],      # List of waypoints
            'active_waypoint': 0, # Index of active waypoint
        }

        self.tactical = {
            'g_force': 0,         # Current G-force
            'aoa': 0,             # Angle of attack in degrees
            'sideslip': 0,        # Sideslip angle in degrees
            'energy_state': 0,    # Aircraft energy state
            'mode': 'NORMAL',     # Flight mode: NORMAL, COMBAT, STEALTH, etc.
        }

        # System status
        self.status = {
            'health': 'NOMINAL',  # System health status
            'mode': 'NORMAL',     # Current operating mode
            'initialization': 'COMPLETE',  # Initialization status
            'warnings': [],       # Active warnings
            'errors': [],         # Active errors
        }

        # Navigation sensor systems (GPS + data fusion)
        self.gps_system   = GPSSystem()
        self.nav_fusion   = NavDataFusion()
        self._last_nav_update = time.time()


    def init_flight_control_system(self):
        """Initialize the Flight Control System"""
        try:
            logger.info("Initializing Flight Control System")
            self.flight_control_system = get_flight_control_system("MainFCS")

            # Set reference to FMS in the FCS
            self.flight_control_system.fms_control = self

            logger.info("Flight Control System initialized")
            return True
        except Exception as e:
            logger.error(f"Error initializing Flight Control System: {e}")
            return False

    def set_messenger(self, messenger):
        """Set the messenger for FMS communications"""
        self.messenger = messenger
        logger.info("FMS messenger set")

        # Pass messenger to the Flight Control System
        if self.flight_control_system:
            self.flight_control_system.set_messenger(messenger)
            logger.info("FCS messenger set via FMS")

    def update_flight_data(self):
        """Update flight data with latest sensor readings and calculations"""
        with self.lock:
            # If FCS is available, use it to update attitude
            if self.flight_control_system and self.flight_control_system.running:
                # Get attitude data from FCS
                fcs_attitude = self.flight_control_system.attitude

                # Update attitude from FCS
                self.attitude['roll'] = fcs_attitude['roll']
                self.attitude['pitch'] = fcs_attitude['pitch']
                self.attitude['yaw'] = fcs_attitude['yaw']
                self.attitude['roll_rate'] = fcs_attitude['roll_rate']
                self.attitude['pitch_rate'] = fcs_attitude['pitch_rate']
                self.attitude['yaw_rate'] = fcs_attitude['yaw_rate']

                # Update tactical data from FCS
                self.tactical['aoa'] = fcs_attitude['alpha']
                self.tactical['sideslip'] = fcs_attitude['beta']
                self.tactical['g_force'] = fcs_attitude['g_force']
            else:
                # Fallback to simulated attitude if FCS is not available
                # Simulate basic changes
                self.attitude['roll'] += (math.sin(time.time() * 0.1) * 0.2)
                self.attitude['pitch'] += (math.sin(time.time() * 0.15) * 0.1)
                self.attitude['yaw'] += (math.sin(time.time() * 0.05) * 0.1)

                # Calculate rates (first derivative of attitude angles)
                self.attitude['roll_rate'] = math.cos(time.time() * 0.1) * 0.2 * 10
                self.attitude['pitch_rate'] = math.cos(time.time() * 0.15) * 0.1 * 15
                self.attitude['yaw_rate'] = math.cos(time.time() * 0.05) * 0.1 * 5

                # Keep angles within appropriate ranges
                self.attitude['roll'] = (self.attitude['roll'] + 180) % 360 - 180
                self.attitude['pitch'] = max(-90, min(90, self.attitude['pitch']))
                self.attitude['yaw'] = self.attitude['yaw'] % 360

                # Calculate tactical data (simplified)
                # Calculate G-force based on attitude changes
                pitch_change = abs(self.attitude['pitch_rate']) / 15.0  # normalized
                roll_change = abs(self.attitude['roll_rate']) / 10.0    # normalized
                self.tactical['g_force'] = 1.0 + pitch_change + (roll_change * 0.5)
                self.tactical['g_force'] = round(max(0.1, min(9.0, self.tactical['g_force'])), 2)

                # Calculate angle of attack (simplified)
                self.tactical['aoa'] = self.attitude['pitch'] * 0.2 + (math.sin(time.time() * 0.3) * 0.5)
                self.tactical['aoa'] = round(max(-10, min(25, self.tactical['aoa'])), 2)

                # Calculate sideslip (simplified)
                self.tactical['sideslip'] = math.sin(time.time() * 0.2) * 2.0

            # Update velocity data (with some random variations)
            self.velocity['airspeed'] = 450 + (math.sin(time.time() * 0.1) * 5)
            self.velocity['vertical_speed'] = math.sin(time.time() * 0.2) * 100

            # Calculate Mach number (simplified)
            # In a real system, this would account for altitude and temperature
            altitude_feet = self.navigation['altitude']
            self.velocity['mach'] = self.velocity['airspeed'] / (661.4788 * 0.98) # Simplified conversion at high altitude

            # ── Navigation update (GPS + Kalman fusion) ──────────────────
            now = time.time()
            dt  = now - self._last_nav_update
            self._last_nav_update = now

            # Feed current DR position into GPS receiver (so it can
            # compute realistic pseudoranges against the constellation).
            self.gps_system.update_true_position(
                self.navigation.get('latitude',  0.0),
                self.navigation.get('longitude', 0.0),
                self.navigation.get('altitude',  30_000.0),
            )

            # Derive dead-reckoning rates from current velocity/heading
            heading_rad  = math.radians(self.navigation.get('heading', 0.0))
            gs_kts       = self.velocity.get('ground_speed', self.velocity.get('airspeed', 450.0))
            gs_dps_lat   = (gs_kts * 1.68781) / (111_000 / 0.3048)   # knots→ft/s→°lat/s
            gs_dps_lon   = gs_dps_lat / max(0.001, math.cos(math.radians(
                               self.navigation.get('latitude', 0.0))))
            lat_rate     = gs_dps_lat * math.cos(heading_rad)
            lon_rate     = gs_dps_lon * math.sin(heading_rad)
            alt_rate_fps = self.velocity.get('vertical_speed', 0.0) / 60.0   # fpm→fps

            # Heading dead-reckoning (small drift)
            heading_dr   = (self.navigation.get('heading', 0.0) + 0.01) % 360

            # Kalman predict step
            self.nav_fusion.predict(dt, lat_rate, lon_rate, alt_rate_fps, heading_dr)

            # If a new GPS fix is available, fold it into the filter
            gps_pos = self.gps_system.get_position_wgs84()
            if gps_pos is not None:
                self.nav_fusion.update_gps(*gps_pos)

            # Write fused position back into FMS navigation dict
            fused_lat, fused_lon, fused_alt, fused_hdg = \
                self.nav_fusion.get_fused_position()
            self.navigation['latitude']  = fused_lat
            self.navigation['longitude'] = fused_lon
            self.navigation['altitude']  = fused_alt
            self.navigation['heading']   = fused_hdg
            # ─────────────────────────────────────────────────────────────

            # Calculate energy state (simplified)
            # Energy = Kinetic + Potential
            mass = 15000  # kg, typical for fighter aircraft
            g = 9.81      # m/s^2
            speed_ms = self.velocity['airspeed'] * 0.51444  # knots to m/s
            altitude_m = self.navigation['altitude'] * 0.3048  # feet to meters

            kinetic_energy = 0.5 * mass * (speed_ms ** 2)
            potential_energy = mass * g * altitude_m
            total_energy = kinetic_energy + potential_energy

            # Normalize to a 0-100 scale for tactical display
            self.tactical['energy_state'] = min(100, total_energy / 1e10 * 100)

            # No database operations - FMS should not directly interact with databases

    def send_fms_data(self):
        """Send FMS data to other systems via messenger"""
        if not self.messenger:
            logger.warning("FMS messenger not set, cannot send data")
            return False

        try:
            # Prepare data for transmission
            fms_data = {
                'attitude': self.attitude,
                'velocity': self.velocity,
                'navigation': self.navigation,
                'tactical': self.tactical,
                'status': self.status,
                'timestamp': time.time()
            }

            # Convert dict to a list of integers for MIL-STD-1553B transmission
            # Each integer will represent a 16-bit data word
            data_words = []

            # Add a simple header word to identify data type
            data_words.append(0x1000)  # FMS data identifier (0x1000 identifies FMS data)

            # We can only send a limited number of words, so we'll prioritize key flight data
            # Attitude data (roll, pitch, yaw)
            roll_int = int(self.attitude['roll'] * 100) & 0xFFFF  # Scale and limit to 16 bits
            pitch_int = int(self.attitude['pitch'] * 100) & 0xFFFF
            yaw_int = int(self.attitude['yaw'] * 100) & 0xFFFF
            data_words.extend([roll_int, pitch_int, yaw_int])

            # Velocity data (airspeed, vertical speed)
            airspeed_int = int(self.velocity['airspeed']) & 0xFFFF
            vertical_speed_int = int(self.velocity['vertical_speed']) & 0xFFFF
            data_words.extend([airspeed_int, vertical_speed_int])

            # Navigation data (altitude, heading)
            altitude_int = int(self.navigation['altitude']) & 0xFFFF
            heading_int = int(self.navigation['heading'] * 10) & 0xFFFF
            data_words.extend([altitude_int, heading_int])

            # Tactical data (g-force, aoa, energy state)
            g_force_int = int(self.tactical['g_force'] * 100) & 0xFFFF
            aoa_int = int(self.tactical['aoa'] * 100) & 0xFFFF
            energy_state_int = int(self.tactical['energy_state']) & 0xFFFF
            data_words.extend([g_force_int, aoa_int, energy_state_int])

            # Status word (mode packed into a 16-bit integer)
            mode_int = 0
            if self.tactical['mode'] == "NORMAL":
                mode_int = 0
            elif self.tactical['mode'] == "COMBAT":
                mode_int = 1
            elif self.tactical['mode'] == "STEALTH":
                mode_int = 2
            elif self.tactical['mode'] == "TRAINING":
                mode_int = 3
            elif self.tactical['mode'] == "EMERGENCY":
                mode_int = 4
            data_words.append(mode_int)

            # Send data via messenger with properly formatted data words
            self.messenger.send_fms_data(data_words)
            return True
        except Exception as e:
            logger.error(f"Error sending FMS data: {e}")
            return False

    def update(self):
        """Main update loop for the FMS"""
        logger.info("FMS update loop started")

        while not self.running.is_set():
            try:
                start_time = time.time()

                # Update flight data (but don't send it automatically)
                # This follows MIL-STD-1553B protocol where Remote Terminals
                # only respond to Bus Controller requests
                self.update_flight_data()

                # Calculate time to sleep to maintain update rate
                elapsed = time.time() - start_time
                sleep_time = max(0, self.update_rate - elapsed)
                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"Error in FMS update loop: {e}")
                time.sleep(1)  # Sleep longer on error to avoid error flood

        logger.info("FMS update loop ended")

    def start(self):
        """Start the FMS"""
        # Guarded against the same TOCTOU race documented and fixed on
        # every other subsystem singleton this round -- see
        # PowerManagementSystem.start()
        # (Systems/powerManagement/elec/powerManagementSystem.py) for the
        # full writeup. Especially worth guarding here: an unguarded
        # double-call wouldn't just duplicate one polling thread like the
        # simpler subsystems -- it would start a second
        # flight_control_system, a second GPS update thread, and a second
        # FMS update thread all at once, since FMS is the central,
        # heavily-depended-on component every other subsystem's lazy-init
        # reaches via get_flightManagementSystem(). Reuses the existing
        # self.lock; start() never touches the data fields it guards
        # elsewhere (set_flight_parameters(), etc.), so no reentrancy risk.
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                logger.info("Starting Flight Management System")
                self.running.clear()

                # Start the Flight Control System if available
                if self.flight_control_system:
                    logger.info("Starting Flight Control System")
                    fcs_started = self.flight_control_system.start()
                    if fcs_started:
                        logger.info("Flight Control System started successfully")
                    else:
                        logger.warning("Failed to start Flight Control System")

                # Start GPS update thread (fix: was incorrectly started in
                # __main__ of globalPositionSystem.py — now started here)
                self.gps_system.start_thread()
                logger.info("GPS system thread started")

                # Start FMS update thread
                self.thread = threading.Thread(target=self.update, daemon=True, name="FMS_Update")
                # daemon=True added (August 2026 re-analysis round, Round
                # 13, thread daemon-flag consistency sweep): this was the
                # one exception among ~25 structurally-identical subsystem
                # update-loop threads repo-wide (ECU, TMS, FDM, PMS, NAV,
                # COMMS, FCC, Airframe, ECS, Hydraulics, GCAS, PerfMonitoring,
                # DefensiveService, SensorService, MissionService,
                # ScenarioEngine, etc. -- all daemon=True) that left the
                # daemon flag unset. Since `daemon` defaults to inheriting
                # the creating thread's daemon status, and this is started
                # from system_manager's boot sequence on the main (non-daemon)
                # thread, this flight-management-system update thread was
                # live-confirmed non-daemon (`fms.thread.daemon == False`)
                # before this fix. flightManagementSystem is boot-critical
                # (started via system_manager.py::start_async_component) and
                # every other subsystem in this codebase relies on its own
                # background loop being a daemon thread as a safety net so a
                # stuck/slow stop() (e.g. its bounded `.join(timeout=2.0)`
                # not actually completing in time) can't block final process
                # exit -- this was the one thread in the whole codebase
                # without that same safety net. Live-verified: daemon status
                # is now True immediately after thread creation, matching
                # every sibling subsystem thread.
                self.thread.start()
                logger.info("Flight Management System started")
                return True
            else:
                logger.warning("FMS is already running")
                return False

    def stop(self):
        """Stop the FMS"""
        logger.info("Stopping Flight Management System")
        self.running.set()

        # Stop GPS thread
        self.gps_system.stop()

        # Stop the Flight Control System if available
        if self.flight_control_system:
            logger.info("Stopping Flight Control System")
            self.flight_control_system.stop()

        # Stop FMS update thread
        if self.thread:
            self.thread.join(timeout=2.0)  # Wait up to 2 seconds for clean shutdown
            if self.thread.is_alive():
                logger.warning("FMS thread did not terminate cleanly")
            self.thread = None
        logger.info("Flight Management System stopped")

    def set_flight_parameters(self, parameters):
        """
        Set flight parameters from external source

        parameters: dict containing attitude, velocity, navigation, tactical data
        """
        with self.lock:
            # Update attitude
            if 'attitude' in parameters:
                for key, value in parameters['attitude'].items():
                    if key in self.attitude:
                        self.attitude[key] = value

            # Update velocity
            if 'velocity' in parameters:
                for key, value in parameters['velocity'].items():
                    if key in self.velocity:
                        self.velocity[key] = value

            # Update navigation
            if 'navigation' in parameters:
                for key, value in parameters['navigation'].items():
                    if key in self.navigation:
                        self.navigation[key] = value

            # Update tactical
            if 'tactical' in parameters:
                for key, value in parameters['tactical'].items():
                    if key in self.tactical:
                        self.tactical[key] = value

            logger.info("Flight parameters updated from external source")

            # No database operations - FMS should not directly interact with databases

    def set_mode(self, mode):
        """Set the FMS operating mode"""
        valid_modes = ["NORMAL", "COMBAT", "STEALTH", "TRAINING", "EMERGENCY"]

        if mode not in valid_modes:
            logger.warning(f"Invalid FMS mode: {mode}")
            return False

        old_mode = self.tactical['mode']
        self.tactical['mode'] = mode
        self.status['mode'] = mode
        logger.info(f"FMS mode changed from {old_mode} to {mode}")

        # Update FCS mode if available
        if self.flight_control_system:
            # Map FMS modes to FCS modes
            fcs_mode_map = {
                "NORMAL": "NORMAL",
                "COMBAT": "COMBAT",
                "STEALTH": "PRECISION",
                "TRAINING": "NORMAL",
                "EMERGENCY": "EMERGENCY"
            }

            fcs_mode = fcs_mode_map.get(mode, "NORMAL")
            logger.info(f"Setting FCS mode to {fcs_mode} based on FMS mode {mode}")
            self.flight_control_system.set_mode(fcs_mode, send_completion=False)

        return True

    def update_navigation(self, latitude: float = None, longitude: float = None,
                          altitude: float = None, heading: float = None,
                          pitch: float = None, roll: float = None) -> None:
        """Update navigation state from an external source (NavService / GPS-INS fusion)."""
        with self.lock:
            if latitude  is not None: self.navigation['latitude']  = latitude
            if longitude is not None: self.navigation['longitude'] = longitude
            if altitude  is not None: self.navigation['altitude']  = altitude
            if heading   is not None: self.navigation['heading']   = heading
            if pitch     is not None: self.attitude['pitch']       = pitch
            if roll      is not None: self.attitude['roll']        = roll

    def get_flight_data(self):
        """Get current flight data"""
        with self.lock:
            return {
                'attitude': self.attitude.copy(),
                'velocity': self.velocity.copy(),
                'navigation': self.navigation.copy(),
                'tactical': self.tactical.copy(),
                'status': self.status.copy(),
                'timestamp': time.time()
            }

    def add_waypoint(self, name, latitude, longitude, altitude, waypoint_type="NORMAL"):
        """Add a waypoint to the flight plan"""
        with self.lock:
            waypoint_id = len(self.navigation['waypoints'])

            waypoint = {
                'id': waypoint_id,
                'name': name,
                'latitude': latitude,
                'longitude': longitude,
                'altitude': altitude,
                'type': waypoint_type
            }

            self.navigation['waypoints'].append(waypoint)
            logger.info(f"Waypoint {name} added to flight plan")
            return True

    def activate_waypoint(self, waypoint_id):
        """Activate a specific waypoint in the flight plan"""
        with self.lock:
            if 0 <= waypoint_id < len(self.navigation['waypoints']):
                self.navigation['active_waypoint'] = waypoint_id
                logger.info(f"Activated waypoint {waypoint_id}")
                return True
            else:
                logger.warning(f"Invalid waypoint ID: {waypoint_id}")
                return False

    def receive_message(self, message):
        """
        Process incoming messages from other systems

        This method only handles the receipt of messages and delegates
        actual processing to the FMS message processor.

        Args:
            message: The message to process

        Returns:
            bool: True if message was processed successfully, False otherwise
        """
        logger.debug(f"FMS received message: {message}")

        # Import message processor here to avoid circular imports
        from FMOFP.Systems.flightManagementSys.fms_message_processor import get_fms_message_processor

        # Get or create processor instance with reference to self
        processor = get_fms_message_processor(self)

        # Delegate processing to the message processor
        return processor.process_message(message)

    def receive_message_sync(self, message):
        """
        Synchronously process an incoming message for the Flight Management System.

        This is used by the RadarMessenger for direct message handling.
        Required by the messaging system for proper synchronous message handling.

        Args:
            message: The message to process

        Returns:
            True if the message was processed successfully, False otherwise
        """
        try:
            logger.info(f"[FMS] Synchronously processing message with ID: {id(message)}")

            # Log message details for debugging
            if hasattr(message, 'message_type'):
                logger.info(f"[FMS] Message type: {message.message_type}")
            if hasattr(message, 'command_type'):
                logger.info(f"[FMS] Command type: {message.command_type}")
            if hasattr(message, 'command_name'):
                logger.info(f"[FMS] Command name: {message.command_name}")

            # Set metadata if not present
            if not hasattr(message, 'metadata'):
                message.metadata = {}

            # Mark as processed by FMS
            if isinstance(message.metadata, dict):
                if 'processed_by' not in message.metadata:
                    message.metadata['processed_by'] = []

                if 'flightManagementSystem' not in message.metadata['processed_by']:
                    message.metadata['processed_by'].append('flightManagementSystem')

            # Process the message using the regular receive_message method
            # This maintains a single code path for message processing
            return self.receive_message(message)

        except Exception as e:
            logger.error(f"[FMS] Error processing message synchronously: {e}")
            logger.error(traceback.format_exc())
            return False

    def check_health(self):
        """Check the health of the FMS"""
        # In a real implementation, this would perform thorough diagnostics
        if not self.thread or not self.thread.is_alive():
            self.status['health'] = 'OFFLINE'
            return False

        if self.status['errors']:
            self.status['health'] = 'DEGRADED'
            return False

        self.status['health'] = 'NOMINAL'
        return True

# Singleton instance
_flightManagementSystem = None

def get_flightManagementSystem():
    """Get the singleton instance of the Flight Management System"""
    global _flightManagementSystem
    if _flightManagementSystem is None:
        _flightManagementSystem = flightManagementSystem()
    return _flightManagementSystem
