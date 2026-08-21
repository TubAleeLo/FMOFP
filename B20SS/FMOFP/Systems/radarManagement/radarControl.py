"""
Radar Management System

Manages various radar systems. Uses direct message handling for
communication between radar components and the main system.
"""
import traceback
import asyncio
import threading
import time
from abc import ABC, abstractmethod
from xml.etree import ElementTree as ET
from typing import Dict, List, Optional
import Utils.common.fetching as fetching
from Systems.radarManagement.weather.weather_radar import weather_radar
from Systems.radarManagement.terrainFollowing.tfr_radar import tfr_radar, tfr_radarMode
from Systems.radarManagement.targeting.targeting_radar import targeting_radar, targeting_radarMode
from Systems.radarManagement.syntheticAperture.sar_radar import sar_radar, sar_radarMode
from Systems.radarManagement.aewc.aewc_radar import aewc_radar, aewc_radarMode
from Systems.radarManagement.radar_enums import RadarMode, MissionPhase, weather_radarMode
from Systems.radarManagement.radar_messaging.radarMessenger import (
    RadarMessenger, get_radar_messenger
)
from Utils.common.thread_manager import thread_manager
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Utils.common.operation_tracker import is_operation_completed, mark_operation_completed
from FMOFP.Systems.radarManagement.radar_data_fusion import get_radar_data_fusion

logger = get_logger()

class AbstractRadar(ABC):
    def __init__(self, name: str, radar_messenger: RadarMessenger):
        self.name = name
        self.mode = RadarMode.STANDBY
        self.radar_messenger = radar_messenger
        self.last_reported_mode = None
        self.last_reported_health = None

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def set_mode(self, mode):
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        pass

    @abstractmethod
    def get_status(self) -> Dict:
        pass

    @abstractmethod
    def get_data(self, data_type: str) -> Dict:
        pass

class RadarFactory:
    @staticmethod
    def create_radar(radar_type: str, radar_control, radar_messenger: RadarMessenger, **kwargs) -> AbstractRadar:
        try:
            name = kwargs.get('name')
            if not name:
                raise ValueError(f"Name parameter is missing for radar type: {radar_type}")

            if radar_type == "weather_radar":
                return weather_radar(name=name, radar_control=radar_control, radar_messenger=radar_messenger)
            elif radar_type == "targeting_radar":
                return targeting_radar(name=name, radar_control=radar_control, radar_messenger=radar_messenger)
            elif radar_type == "sar_radar":
                return sar_radar(name=name, radar_control=radar_control, radar_messenger=radar_messenger)
            elif radar_type == "tfr_radar":
                return tfr_radar(name=name, radar_control=radar_control, radar_messenger=radar_messenger)
            elif radar_type == "aewc_radar":
                return aewc_radar(name=name, radar_control=radar_control, radar_messenger=radar_messenger)
            else:
                raise ValueError(f"Unknown radar type: {radar_type}")
        except Exception as e:
            logger.error(f"Error creating radar of type {radar_type}: {str(e)}")
            logger.error(traceback.format_exc())
            raise

class RadarCommand(ABC):
    @abstractmethod
    def execute(self, radar: AbstractRadar):
        pass

class SetModeCommand(RadarCommand):
    def __init__(self, mode):
        self.mode = mode

    def execute(self, radar: AbstractRadar):
        try:
            radar.set_mode(self.mode)
        except Exception as e:
            logger.error(f"Error executing SetModeCommand for radar {radar.name}: {str(e)}")
            logger.error(traceback.format_exc())

class RadarManagementSystem:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RadarManagementSystem, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.radars: Dict[str, AbstractRadar] = {}
            self.mission_phase = MissionPhase.PRE_FLIGHT
            self.radar_messenger = None  # Will be set during initialization
            self._running = threading.Event()  # Use Event for thread-safe flag
            self._lock = threading.Lock()
            self._loop = None  # Event loop for async operations
            self._initialized = True
            logger.info("RadarManagementSystem initialized")

    @property
    def running(self) -> bool:
        """Thread-safe access to running state."""
        return self._running.is_set()

    def _run_event_loop(self):
        """Run event loop in a separate thread."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            logger.info("Event loop thread started")
            self._loop.run_forever()
        except Exception as e:
            logger.error(f"Error in event loop thread: {str(e)}")
            logger.error(traceback.format_exc())
        finally:
            self._loop.close()
            self._loop = None
            logger.info("Event loop thread ended")

    def initialize(self):
        """Initialize the Radar Management System."""
        try:
            logger.info("=== Initializing Radar Management System ===")

            # Start event loop in a separate thread
            thread_name = "RadarControlEventLoop"
            thread_manager.add_thread(name=thread_name, target=self._run_event_loop)
            thread_manager.start_thread(thread_name)
            logger.info("Event loop thread started")

            # Wait for event loop to be ready
            while not self._loop:
                time.sleep(0.1)
            logger.info("Event loop is ready")

            # Initialize and start radar messenger
            self.radar_messenger = get_radar_messenger()
            self.radar_messenger.set_radar_control(self)  # Give messenger direct access
            logger.info("Starting RadarMessenger...")
            try:
                self.radar_messenger.start()
                if not self.radar_messenger.running:
                    raise RuntimeError("RadarMessenger failed to start")
                logger.info("RadarMessenger started successfully")
            except Exception as e:
                logger.error(f"Failed to start RadarMessenger: {e}")
                logger.error(traceback.format_exc())
                raise

            # Initialize radars
            self.initialize_radars()
            logger.info("RadarManagementSystem initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing RadarManagementSystem: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def initialize_radars(self):
        """Initialize all radar systems."""
        # Check if radar initialization has already been completed
        if is_operation_completed('radar_init', 'radar_management'):
            logger.info("Radar initialization already completed - skipping")
            # Make sure we still have the necessary radar objects
            if not self.radars:
                logger.info("Recreating radar objects")
                try:
                    radar_configs = self._load_radar_configs()
                    for radar_type, config in radar_configs.items():
                        radar = RadarFactory.create_radar(radar_type, self, self.radar_messenger, **config)
                        self.radars[radar.name] = radar
                except Exception as e:
                    logger.error(f"Error recreating radar objects: {str(e)}")
                    logger.error(traceback.format_exc())
                    raise
            return

        # If not already completed, initialize radars
        try:
            radar_configs = self._load_radar_configs()
            for radar_type, config in radar_configs.items():
                radar = RadarFactory.create_radar(radar_type, self, self.radar_messenger, **config)
                self.radars[radar.name] = radar
            logger.info("All radars initialized successfully")
            # Mark operation as completed
            mark_operation_completed('radar_init', 'radar_management')
            # Start cross-radar data fusion layer
            get_radar_data_fusion().start()
            logger.info("Cross-radar data fusion layer started")
        except Exception as e:
            logger.error(f"Error initializing radars: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _load_radar_configs(self):
        """Load radar configurations with consistent naming."""
        return {
            "weather_radar": {"name": "weather_radar"},
            "targeting_radar": {"name": "targeting_radar"},
            "sar_radar": {"name": "sar_radar"},
            "tfr_radar": {"name": "tfr_radar"},
            "aewc_radar": {"name": "aewc_radar"}
        }

    def _update_loop(self):
        """Main radar control loop - normal thread."""
        thread_id = threading.get_ident()
        logger.info(f"=== Starting RadarMain thread (ID: {thread_id}) ===")

        while self.running:
            try:


                # Update each radar
                for radar in self.radars.values():
                    try:

                        if isinstance(radar, weather_radar):
                            radar.update()
                        # radar.update()            # Will do update for ALL radars.  Reduced to weather radar only for now
                    except Exception as e:
                        logger.error(f"Error updating radar {radar.name}: {e}")
                        logger.error(traceback.format_exc())

                # Check system health.
                #
                # `running` is re-checked FIRST and handled separately from
                # the health verdict. is_healthy() returns
                # `self.running and radar_health`, so once a shutdown clears
                # the _running event this call returns False for a perfectly
                # healthy system — and the branch below reported that as
                # "detected unhealthy system" at ERROR. Because a shutdown
                # can flip the flag while an iteration is already in flight,
                # this fired on essentially every clean run: live-traced at
                # ~107 ms after the NORMAL -> SHUTTING_DOWN transition, and
                # it was the only ERROR left in an otherwise clean boot log.
                # A normal stop is not a fault, so it exits quietly here and
                # the ERROR is reserved for a radar that is genuinely
                # unhealthy while the system is still meant to be running.
                if not self.running:
                    logger.info(
                        f"RadarMain thread (ID: {thread_id}) stopping: "
                        f"system is shutting down"
                    )
                    break

                if not self.is_healthy():
                    logger.error(f"RadarMain thread (ID: {thread_id}) detected unhealthy system")
                    self._running.clear()  # Thread-safe way to stop
                    break

                time.sleep(0.1)  # Prevent tight loop

            except Exception as e:
                logger.error(f"Error in RadarMain thread (ID: {thread_id}): {e}")
                logger.error(traceback.format_exc())
                if not self.running:
                    break
                time.sleep(1)  # Sleep longer on error

        logger.info(f"=== RadarMain thread (ID: {thread_id}) ended ===")

    def update(self):
        """Radar management thread - normal thread."""
        thread_id = threading.get_ident()
        logger.info(f"=== Starting RadarManagement thread (ID: {thread_id}) ===")

        while self.running:
            try:
                # Debug thread state
                logger.debug(f"RadarManagement thread (ID: {thread_id}) running, active: {threading.current_thread().is_alive()}")

                # NOTE: previously this block wrapped the three calls below
                # in an outer `with self._lock:`. self._lock is a plain,
                # non-reentrant threading.Lock, and _manage_radar_resources(),
                # _check_radar_configurations(), and _handle_mode_transitions()
                # each independently acquire the SAME self._lock internally.
                # Acquiring it here first meant every single call to this
                # method immediately self-deadlocked on the very first nested
                # acquisition -- confirmed live: the "RadarManagement"
                # thread's debug log ("... running, active: True") fired
                # exactly once at startup and never again, for the entire
                # process lifetime, because it never got past
                # _manage_radar_resources()'s own `with self._lock:`. This
                # silently made this thread permanently inert from startup
                # (no resource management, config checks, or mode-transition
                # handling ever actually ran) and, separately, made it
                # unjoinable -- hanging graceful shutdown forever, since
                # thread_manager.stop_thread("RadarManagement") does a
                # blocking, timeout-less thread.join(). Each sub-method
                # already acquires self._lock itself, so no outer lock is
                # needed here.
                self._manage_radar_resources()
                self._check_radar_configurations()
                self._handle_mode_transitions()

                time.sleep(0.1)  # Prevent tight loop

            except Exception as e:
                logger.error(f"Error in RadarManagement thread (ID: {thread_id}): {e}")
                logger.error(traceback.format_exc())
                if not self.running:
                    break
                time.sleep(1)  # Sleep longer on error

        logger.info(f"=== RadarManagement thread (ID: {thread_id}) ended ===")

    def start(self):
        """Start the radar system."""
        try:
            logger.info("=== Starting Radar Management System ===")

            # Set running flag before starting threads
            self._running.set()  # Thread-safe way to start

            # Start each radar
            for radar in self.radars.values():
                radar.start()

            # NOTE: each radar (weather/targeting/SAR/TFR/AEWC) already
            # initializes self.mode = <Type>Mode.STANDBY itself in its own
            # __init__/start(), which is the correct, safe default (radars
            # shouldn't auto-activate without an explicit mode-change
            # command). There is no additional initial-mode configuration
            # step needed here; this previously logged "Configuring initial
            # radar modes..." immediately followed by a TODO placeholder
            # with no actual code, which was misleading since no
            # configuration work was ever happening at this level.
            logger.info("Radar Management System running flag set to True")
            logger.info("=== Radar Management System started ===")
        except Exception as e:
            logger.error(f"Error starting Radar Management System: {str(e)}")
            logger.error(traceback.format_exc())
            self._running.clear()  # Thread-safe way to stop
            raise

    async def stop(self):
        """Stop the Radar Management System."""
        try:
            logger.info("=== Stopping Radar Management System ===")
            self._running.clear()  # Thread-safe way to stop

            # Stop cross-radar data fusion layer first
            try:
                get_radar_data_fusion().stop()
                logger.info("Cross-radar data fusion layer stopped")
            except Exception:
                logger.warning("RadarControl: error stopping cross-radar data fusion layer", exc_info=True)

            # Stop each radar
            for radar in self.radars.values():
                radar.stop()

            # Stop radar messenger
            # NOTE: RadarMessenger.stop() is a synchronous method (it does a
            # blocking thread.join() internally), not a coroutine. It was
            # previously awaited here, which raised
            # "TypeError: object NoneType can't be used in 'await' expression"
            # on every shutdown since stop() returns None, not an awaitable.
            if self.radar_messenger:
                logger.info("Stopping RadarMessenger...")
                self.radar_messenger.stop()
                logger.info("RadarMessenger stopped successfully")

            logger.info("Radar Management System running flag set to False")
            logger.info("=== Radar Management System stopped ===")
        except Exception as e:
            logger.error(f"Error stopping Radar Management System: {str(e)}")
            logger.error(traceback.format_exc())

    def is_healthy(self) -> bool:
        """Check if the radar system is healthy."""
        try:
            running = self.running
            radar_health = all(radar.is_healthy() for radar in self.radars.values())
            return running and radar_health
        except Exception as e:
            logger.error(f"Error checking radar health: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _manage_radar_resources(self):
        """Manage radar resources - non-async operations only."""
        with self._lock:
            # Update resource allocation based on mission phase
            self._allocate_radar_resources()

            # Check resource utilization
            for radar in self.radars.values():
                try:
                    self._check_radar_resources(radar)
                except Exception as e:
                    logger.error(f"Error checking radar {radar.name} resources: {e}")

    def update_mission_phase(self, phase: MissionPhase):
        try:
            self.mission_phase = phase
            self._allocate_radar_resources()
            logger.info(f"Updated mission phase: {phase.name}")
        except Exception as e:
            logger.error(f"Error updating mission phase: {str(e)}")
            logger.error(traceback.format_exc())

    def _allocate_radar_resources(self):
        try:
            if self.mission_phase == MissionPhase.TAKEOFF:
                self._configure_airport_departure()
            elif self.mission_phase == MissionPhase.CRUISE:
                self._configure_enroute_surveillance()
            elif self.mission_phase == MissionPhase.APPROACH:
                self._configure_airport_arrival()
        except Exception as e:
            logger.error(f"Error allocating radar resources: {str(e)}")
            logger.error(traceback.format_exc())

    def _configure_airport_departure(self):
        for radar in self.radars.values():
            try:
                # Only pass send_completion=False to weather_radar, as other radar types don't support this parameter YET
                if isinstance(radar, weather_radar):
                    radar.set_mode(weather_radarMode.SURVEILLANCE, send_completion=False)
                elif isinstance(radar, tfr_radar):
                    radar.set_mode(tfr_radarMode.TERRAIN_FOLLOWING)
                else:
                    radar.set_mode(RadarMode.STANDBY)
            except Exception as e:
                logger.error(f"Error configuring {radar.name} for airport departure: {str(e)}")
                logger.error(traceback.format_exc())

    def _configure_enroute_surveillance(self):
        for radar in self.radars.values():
            try:
                # NOTE (production readiness re-analysis, August 2026): this
                # used to only pass send_completion=False to weather_radar,
                # with a "TODO LATER -- other radar types don't support this
                # parameter YET" comment. That's stale: targeting_radar.py,
                # tfr_radar.py, sar_radar.py, and aewc_radar.py all already
                # define set_mode(self, mode, send_completion=True,
                # request_id=None) -- the parameter has been supported
                # everywhere for some time, the comment (and the resulting
                # inconsistency with the near-identical
                # _configure_airport_arrival() method right below, which
                # already passes send_completion=False "for all startup mode
                # changes to prevent unnecessary messages") just never got
                # updated. Passing send_completion=False for all five radar
                # types now, matching that established convention.
                if isinstance(radar, weather_radar):
                    radar.set_mode(weather_radarMode.SURVEILLANCE, send_completion=False)
                elif isinstance(radar, tfr_radar):
                    radar.set_mode(tfr_radarMode.TERRAIN_FOLLOWING, send_completion=False)
                elif isinstance(radar, targeting_radar):
                    radar.set_mode(targeting_radarMode.SEARCH, send_completion=False)
                elif isinstance(radar, sar_radar):
                    radar.set_mode(sar_radarMode.STRIPMAP, send_completion=False)
                elif isinstance(radar, aewc_radar):
                    radar.set_mode(aewc_radarMode.SEARCH, send_completion=False)
            except Exception as e:
                logger.error(f"Error configuring {radar.name} for enroute surveillance: {str(e)}")
                logger.error(traceback.format_exc())

    def _configure_airport_arrival(self):
        for radar in self.radars.values():
            try:
                # Set send_completion=False for all startup mode changes to prevent unnecessary messages
                if isinstance(radar, weather_radar):
                    radar.set_mode(weather_radarMode.SURVEILLANCE, send_completion=False)
                elif isinstance(radar, tfr_radar):
                    radar.set_mode(tfr_radarMode.TERRAIN_FOLLOWING, send_completion=False)
                else:
                    radar.set_mode(RadarMode.STANDBY, send_completion=False)
            except Exception as e:
                logger.error(f"Error configuring {radar.name} for airport arrival: {str(e)}")
                logger.error(traceback.format_exc())

    def _check_radar_configurations(self):
        """Check and validate radar configurations."""
        with self._lock:
            for radar in self.radars.values():
                try:
                    # Validate radar mode against mission phase
                    self._validate_radar_mode(radar)

                    # Check radar parameters
                    self._validate_radar_parameters(radar)
                except Exception as e:
                    logger.error(f"Error checking radar {radar.name} configuration: {e}")

    def _validate_radar_mode(self, radar):
        """Validate radar mode against current mission phase."""
        try:
            current_mode = radar.mode
            expected_mode = self._get_expected_mode(radar)

            if current_mode != expected_mode:
                logger.warning(f"Radar {radar.name} mode mismatch. Expected: {expected_mode}, Current: {current_mode}")
                self._transition_radar_mode(radar)
        except Exception as e:
            logger.error(f"Error validating radar {radar.name} mode: {e}")

    def _validate_radar_parameters(self, radar):
        """Validate radar operating parameters."""
        try:
            # Get radar parameters
            params = radar.get_status()

            # Check each parameter against allowed ranges
            for param, value in params.items():
                if not self._is_parameter_valid(param, value):
                    logger.warning(f"Invalid parameter {param}={value} for radar {radar.name}")
        except Exception as e:
            logger.error(f"Error validating radar {radar.name} parameters: {e}")

    def _get_expected_mode(self, radar):
        """Get expected radar mode based on mission phase."""
        if isinstance(radar, weather_radar):
            if self.mission_phase in [MissionPhase.TAKEOFF, MissionPhase.APPROACH]:
                return weather_radarMode.SURVEILLANCE
            else:
                return weather_radarMode.MAPPING
        # No mission-phase-based expected-mode policy has been implemented
        # yet for targeting/SAR/TFR/AEWC radars (this fallback was never
        # actually reachable before: _manage_radar_resources() /
        # _check_radar_configurations() / _handle_mode_transitions() all
        # deadlocked on their first call due to a since-fixed non-reentrant
        # self._lock double-acquisition, so this code path never ran in
        # practice -- see PLANNING.md). The old fallback of RadarMode.STANDBY
        # is the wrong enum type for every one of these radars (each expects
        # its own typed enum, e.g. targeting_radarMode.STANDBY), so once the
        # deadlock was fixed this fired continuously (confirmed live: ~70
        # "Invalid mode type" errors in an 8s window) and could never
        # succeed. Returning the radar's own current mode is a neutral
        # "no policy defined" default: it makes _needs_mode_transition()
        # correctly report "no transition needed" for these radar types
        # instead of endlessly retrying a transition that was always going
        # to fail, without guessing at mission-phase behavior that was never
        # specified for them.
        return radar.mode

    def _is_parameter_valid(self, param, value):
        """Check if a radar parameter value is valid."""
        # Add parameter validation logic
        return True

    def _handle_mode_transitions(self):
        """Handle radar mode transitions."""
        with self._lock:
            for radar in self.radars.values():
                try:
                    # Check if mode transition is needed
                    if self._needs_mode_transition(radar):
                        # Perform mode transition
                        self._transition_radar_mode(radar)
                except Exception as e:
                    logger.error(f"Error handling mode transition for radar {radar.name}: {e}")

    def _needs_mode_transition(self, radar):
        """Check if radar needs mode transition."""
        try:
            current_mode = radar.mode
            expected_mode = self._get_expected_mode(radar)
            return current_mode != expected_mode
        except Exception as e:
            logger.error(f"Error checking mode transition need for radar {radar.name}: {e}")
            return False

    def _transition_radar_mode(self, radar):
        """Perform radar mode transition."""
        try:
            new_mode = self._get_expected_mode(radar)
            logger.info(f"Transitioning radar {radar.name} to mode {new_mode}")
            radar.set_mode(new_mode)
        except Exception as e:
            logger.error(f"Error transitioning radar {radar.name} mode: {e}")

    def _check_radar_resources(self, radar):
        """Check radar resource utilization."""
        try:
            # Get radar resource usage
            status = radar.get_status()

            # Check resource thresholds
            if status.get('cpu_usage', 0) > 90:
                logger.warning(f"High CPU usage for radar {radar.name}: {status['cpu_usage']}%")
            if status.get('memory_usage', 0) > 90:
                logger.warning(f"High memory usage for radar {radar.name}: {status['memory_usage']}%")
        except Exception as e:
            logger.error(f"Error checking resources for radar {radar.name}: {e}")

# Global instance
radar_management_system = RadarManagementSystem()

def get_radar_management_system():
    """Get the global RadarManagementSystem instance."""
    return radar_management_system
