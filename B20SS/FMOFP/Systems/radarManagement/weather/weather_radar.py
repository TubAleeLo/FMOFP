"""
Weather Radar System

Handles weather radar operations using direct message handling.
"""

import os
import time
import traceback
import threading
import xml.etree.ElementTree as ET
import numpy as np
import uuid
import FMOFP.Utils.common.fetching as fetching
from typing import Dict, Any
from FMOFP.Systems.radarManagement.radar_enums import weather_radarMode
from FMOFP.MIL_STD_1553B.mil_std_1553B import MIL_STD_1553B_Message
# Use centralized address utilities
from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress, get_rt_subaddress_pair
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.radarManagement.weather.reflectivity_simulator import ReflectivitySimulator
from FMOFP.Systems.radarManagement.weather.vil_data_generator_sync import VILDataGenerator
from FMOFP.Systems.radarManagement.weather.precipitation_data_generator_sync import PrecipitationDataGenerator
from FMOFP.Systems.radarManagement.radar_message_adapter import get_radar_message_adapter
from FMOFP.Systems.radarManagement.radar_messaging.stormCellTracking import StormCellTracker
from FMOFP.Systems.radarManagement.radar_messaging.precipitation_analysis import PrecipitationAnalyzer
from FMOFP.Systems.radarManagement.weather.weather_processor import WindShearProcessor, TurbulenceProcessor
from FMOFP.Utils.common.operation_tracker import track_operation, is_operation_completed
from FMOFP.Systems.radarManagement.weather.weather_message_type_detector import weather_message_type_detector
# Import centralized message type constants
from FMOFP.Systems.radarManagement.radar_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST,
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    WEATHER_RADAR_COMMAND,
    WEATHER_RADAR_DATA,
    COMMAND_TYPE_MODE_CHANGE,
    COMMAND_TYPE_MODE_CHANGE_COMPLETE,
    COMMAND_TYPE_DATA_REQUEST,
    COMMAND_TYPE_VIL_DATA,
    COMMAND_TYPE_PRECIPITATION_DATA,
    get_message_type,
    is_message_type,
    is_vil_message,
    is_precipitation_message,
    is_mode_change_message
)

logger = get_logger()

class weather_radar:
    def __init__(self, name: str, radar_control, radar_messenger):
        self.name = name
        self.mode = weather_radarMode.STANDBY
        self.radar_control = radar_control
        self.radar_messenger = radar_messenger
        self.running = False
        self._lock = threading.Lock()
        self._health_status = True
        self._last_update = time.time()
        self._update_interval = 0.1  # seconds
        self._resource_usage = {
            'cpu_usage': 0,
            'memory_usage': 0,
            'disk_usage': 0
        }

        # Flag to track startup state and ignore startup messages
        self._in_startup = True
        self._startup_complete_time = None
        self._startup_timeout = 5.0  # seconds

        # Initialize configuration
        self.config = self._get_default_config()
        self.config.update(self._load_radar_config())

        # Initialize radar parameters
        self.tilt = self.config['tilt_range']['min']
        self.range = self.config['scan_range']['min']

        # Initialize reflectivity simulator, VIL data generator, and precipitation data generator
        self.reflectivity_simulator = ReflectivitySimulator(self.config)
        self.vil_data_generator = VILDataGenerator(self.config)
        self.precipitation_data_generator = PrecipitationDataGenerator(self.config)
        self.msg_type_detector = weather_message_type_detector()

        # Capability modules (previously orphaned — now connected)
        self.storm_cell_tracker = StormCellTracker()
        self.precip_analyzer    = PrecipitationAnalyzer()
        self.windshear_proc     = WindShearProcessor()
        self.turbulence_proc    = TurbulenceProcessor()

        logger.info(f"[WEATHER] Weather radar {name} initialized")

    def start(self):
        """Start the weather radar system."""
        try:
            logger.info(f"[WEATHER] Starting weather radar {self.name}")
            with self._lock:
                if self.running:
                    logger.info(f"[WEATHER] Weather radar {self.name} already initialized")  # Changed from warning
                    return

                # Set startup flag to true
                self._in_startup = True
                self._startup_complete_time = time.time() + self._startup_timeout

                self.running = True
                self.mode = weather_radarMode.STANDBY
                # Allow time for system initialization
                # Transition to operational mode if radar control exists
                if hasattr(self, 'radar_control') and self.radar_control:
                    logger.info(f"[WEATHER] Weather radar {self.name} transitioning to operational mode")

                    # Set the radar mode to NORMAL after startup
                    self.set_mode(weather_radarMode.NORMAL, send_completion=True, request_id=str(uuid.uuid4()))

                # Set startup flag to false after initialization
                self._in_startup = False
                logger.info(f"[WEATHER] Weather radar {self.name} startup complete, now accepting messages")

            logger.info(f"[WEATHER] Weather radar {self.name} started and configured")
        except Exception as e:
            logger.error(f"[WEATHER] Error starting weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            self._health_status = False

    def stop(self):
        """Stop the weather radar system."""
        try:
            logger.info(f"Stopping weather radar {self.name}")
            with self._lock:
                if not self.running:
                    logger.info(f"[WEATHER] Weather radar {self.name} already stopped")  # Changed from warning
                    return
                self.running = False
                self.mode = weather_radarMode.STANDBY
            logger.info(f"[WEATHER] Weather radar {self.name} stopped")
        except Exception as e:
            logger.error(f"[WEATHER] Error stopping weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            self._health_status = False

    def _load_message_rates(self):
        def _load_message_rates_impl():
            # Default message rates in case loading fails
            message_rates = {
                'status_msg': 1,
                'alert_msg': 5,
                'data_msg': 10,
                'command_msg': 2,
                'log_msg': 0.5
            }

            # Load message rates from file
            config_file = os.path.join(fetching.fetch_fmofp_path(), 'messageRateConfig.xml')
            logger.info(f"[WEATHER] Attempting to load message rates from: {config_file}")

            try:
                if not os.path.exists(config_file):
                    logger.error(f"[WEATHER] Configuration file not found: {config_file}")
                    return message_rates

                tree = ET.parse(config_file)
                root = tree.getroot()
                for msg_type in root.findall('message_rates/*'):
                    msg_name = msg_type.tag
                    rate_hz = float(msg_type.find('rate_hz').text)
                    message_rates[msg_name] = rate_hz

                logger.info("[WEATHER] Successfully loaded message rate configurations")

            except ET.ParseError as e:
                logger.error(f"[WEATHER] XML parsing error in configuration file: {e}")
                # Use default rates if parsing fails

            except Exception as e:
                logger.error(f"[WEATHER] Failed to load message rate configurations: {e}")
                # Use default rates if loading fails

            logger.info(f"[WEATHER] Using message rates: {message_rates}")
            return message_rates

        # Use the operation tracker to ensure this only happens once
        result = track_operation('message_rates_load', 'weather_radar', _load_message_rates_impl)
        if result is None:
            # If already loaded, we need to get the result from a previous call
            # Since we can't directly access the previous result, we'll check if the tracking file exists
            if is_operation_completed('message_rates_load', 'weather_radar'):
                logger.info("[WEATHER] Message rates already loaded, using cached values")
                # We need to load the rates again, but this is just to get the data
                return _load_message_rates_impl()
        return result

    def _load_radar_config(self):
        config_file = os.path.join(os.path.dirname(__file__), '..', 'rmConfig.xml')
        try:
            if not os.path.exists(config_file):
                logger.error(f"[WEATHER] Radar configuration file not found: {config_file}")
                return self._get_default_config()

            tree = ET.parse(config_file)
            root = tree.getroot()
            weather_radar = root.find('weather_radar')
            if weather_radar is None:
                logger.error("[WEATHER] 'weather_radar' section not found in the configuration file")
                return self._get_default_config()

            config = {
                'pulse_width': {'min': 0.1, 'max': 10},  # microseconds
                'prf': {'min': 100, 'max': 2000},  # Hz
                'antenna_gain': 30,  # dB
                'frequency': 9.345,  # GHz
                'tilt_range': {'min': 0, 'max': 90},  # degrees
                'scan_range': {'min': 10, 'max': 200},  # kilometers
                'vcp': {
                    'surveillance': {'elevs': (0.5, 1.5, 2.4, 3.4), 'update_rate': 20},
                    'mapping': {'elevs': (0.5, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0), 'update_rate': 120}
                },
                'vil_params': {'a': 2.55e-6, 'b': 0.55},
                'shear_params': {'threshold': 5},
                'turb_params': {'threshold': 15},
                'simulated': weather_radar.get('simulated', 'false').lower() == 'true'
            }
            return config
        except Exception as e:
            logger.error(f"[WEATHER] Error loading radar configuration: {e}")
            return self._get_default_config()

    def load_config(self, config):
        if config:
            self.config.update(config)
        logger.info(f"[WEATHER] Weather radar configuration loaded: {self.config}")

    def update(self):
        """Update weather radar state."""
        try:
            if not self.running:
                return

            current_time = time.time()
            if current_time - self._last_update < self._update_interval:
                return

            with self._lock:
                # Update resource usage
                self._update_resource_usage()

                # Update health status
                self._check_health()

                # Update radar state based on mode
                self._update_radar_state()

                self._last_update = current_time

        except Exception as e:
            logger.error(f"[WEATHER] Error updating weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            self._health_status = False

    def _update_resource_usage(self):
        """Update simulated resource usage."""
        try:
            # Simulate resource usage
            self._resource_usage['cpu_usage'] = 30  # Example CPU usage
            self._resource_usage['memory_usage'] = 40  # Example memory usage
            self._resource_usage['disk_usage'] = 20  # Example disk usage
        except Exception as e:
            logger.error(f"[WEATHER] Error updating resource usage for {self.name}: {str(e)}")

    def _check_health(self):
        """Check radar health status."""
        try:
            # Check resource thresholds
            if (self._resource_usage['cpu_usage'] > 90 or
                self._resource_usage['memory_usage'] > 90 or
                self._resource_usage['disk_usage'] > 90):
                self._health_status = False
                logger.warning(f"[WEATHER] Weather radar {self.name} resource usage too high")
            else:
                self._health_status = True
        except Exception as e:
            logger.error(f"[WEATHER] Error checking health for {self.name}: {str(e)}")
            self._health_status = False

    def _update_radar_state(self):
        """Update radar state based on current mode."""
        try:
            if self.mode == weather_radarMode.STANDBY:
                # Minimal processing in standby
                pass
            elif self.mode == weather_radarMode.SURVEILLANCE:
                # Process surveillance data
                self._process_surveillance_data()
            elif self.mode == weather_radarMode.MAPPING:
                # Process mapping data
                self._process_mapping_data()
            elif self.mode == weather_radarMode.TURBULENCE:
                self._process_turbulence_data()
            elif self.mode == weather_radarMode.WINDSHEAR:
                self._process_windshear_data()
            elif self.mode == weather_radarMode.NORMAL:
                # Process normal data
                pass
            else:
                logger.warning(f"[WEATHER] Unknown mode {self.mode} for weather radar {self.name}")
        except Exception as e:
            logger.error(f"[WEATHER] Error updating radar state for {self.name}: {str(e)}")

    def _process_surveillance_data(self):
        """Process weather surveillance data — run storm cell tracker and push to display."""
        try:
            elevation_angles = self.config['vcp'].get(
                'surveillance', {}).get('elevs', (0.5,))
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                'surveillance', elevation_angles)
            self.storm_cell_tracker.process_radar_data(
                reflectivity, elevation_angles=elevation_angles)
            cells = self.storm_cell_tracker.get_active_cells()
            if cells:
                try:
                    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_cells_data
                    push_cells_data(cells, str(uuid.uuid4()))
                    logger.debug(f"[WEATHER] Surveillance: {len(cells)} storm cells pushed to display")
                except Exception as _bridge_exc:
                    logger.warning(f"[WEATHER] Surveillance cell bridge push failed: {_bridge_exc}")
        except Exception as e:
            logger.error(f"[WEATHER] Error processing surveillance data for {self.name}: {str(e)}")

    def _process_mapping_data(self):
        """Process weather mapping data — run precipitation analyser and push to display."""
        try:
            elevation_angles = self.config['vcp'].get(
                'mapping', {}).get('elevs', (0.5,))
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                'mapping', elevation_angles)
            # generate_reflectivity() always returns a 3D array
            # (azimuth, elevation, range), but PrecipitationAnalyzer expects
            # a 2D (azimuth, range) array - it does np.argwhere() on a mask
            # of it and unpacks the result as exactly (center_y, center_x).
            # Passing the raw 3D array here made every centroid have 3
            # coordinates instead of 2, raising "too many values to unpack
            # (expected 2)" on every single call. Collapse to a 2D composite
            # first, same approach already used for the other
            # precip_analyzer.process_radar_data() call site below. Also fixes
            # elevation_angles previously landing in the temperature_data
            # positional slot instead of scan_elevation.
            reflectivity_2d = reflectivity.max(axis=1)
            lowest_elev = float(elevation_angles[0]) if elevation_angles else 0.5
            self.precip_analyzer.process_radar_data(
                reflectivity_data=reflectivity_2d,
                scan_elevation=lowest_elev
            )
            enriched = self.precip_analyzer.get_precipitation_data()
            if enriched:
                try:
                    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_precipitation_data
                    push_precipitation_data(enriched, str(uuid.uuid4()))
                    logger.debug(f"[WEATHER] Mapping: {len(enriched)} precip points pushed to display")
                except Exception as _bridge_exc:
                    logger.warning(f"[WEATHER] Mapping precip bridge push failed: {_bridge_exc}")
        except Exception as e:
            logger.error(f"[WEATHER] Error processing mapping data for {self.name}: {str(e)}")

    def _process_turbulence_data(self):
        """Process TURBULENCE mode data via TurbulenceProcessor."""
        try:
            elevation_angles = self.config['vcp'].get(
                self.mode.name.lower(), {}).get('elevs', (0.5,))
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                self.mode.name.lower(), elevation_angles)
            cells = self.turbulence_proc.process(
                reflectivity, elevation_angles)
            if cells:
                logger.info(
                    f"[WEATHER] Turbulence: {len(cells)} cells, "
                    f"max category={self.turbulence_proc.max_category()}")
                try:
                    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_turbulence_data
                    cell_dicts = []
                    for c in cells:
                        pos_nm = getattr(c, 'position_nm', (0.0, 0.0))
                        cell_dicts.append({
                            'position':     (float(pos_nm[0]), float(pos_nm[1])),
                            'intensity':    float(getattr(c, 'intensity', 0.0)),
                            'spectrum_width': float(getattr(c, 'spectrum_width', 0.0)),
                            'cell_id':      int(getattr(c, 'cell_id', 0)),
                            'category':     str(getattr(c, 'category', 'LIGHT')),
                            'altitude_ft':  float(getattr(c, 'altitude_ft', 0.0)),
                        })
                    push_turbulence_data(cell_dicts, str(uuid.uuid4()))
                    logger.info(f"[WEATHER] Turbulence: {len(cell_dicts)} cells pushed to display")
                except Exception as _bridge_exc:
                    logger.warning(f"[WEATHER] Turbulence bridge push failed: {_bridge_exc}")
        except Exception as exc:
            logger.error(f"[WEATHER] Turbulence processing error: {exc}")

    def _process_windshear_data(self):
        """Process WINDSHEAR mode data via WindShearProcessor."""
        try:
            elevation_angles = self.config['vcp'].get(
                self.mode.name.lower(), {}).get('elevs', (0.5,))
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                self.mode.name.lower(), elevation_angles)
            events = self.windshear_proc.process(
                reflectivity, elevation_angles)
            if self.windshear_proc.has_microburst():
                logger.warning("[WEATHER] MICROBURST DETECTED")
            if events:
                try:
                    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_windshear_data
                    event_dicts = []
                    for ev in events:
                        pos_nm = getattr(ev, 'position_nm', (0.0, 0.0))
                        event_dicts.append({
                            'position':      (float(pos_nm[0]), float(pos_nm[1])),
                            'intensity':     min(1.0, float(getattr(ev, 'shear_knots', 0.0)) / 60.0),
                            'shear_knots':   float(getattr(ev, 'shear_knots', 0.0)),
                            'severity':      str(getattr(ev, 'severity', 'LOW')),
                            'is_microburst': bool(getattr(ev, 'is_microburst', False)),
                            'altitude_ft':   float(getattr(ev, 'altitude_ft', 0.0)),
                            'event_id':      int(getattr(ev, 'event_id', 0)),
                        })
                    push_windshear_data(event_dicts, str(uuid.uuid4()))
                    logger.info(f"[WEATHER] Windshear: {len(events)} events pushed to display")
                except Exception as _bridge_exc:
                    logger.warning(f"[WEATHER] Windshear bridge push failed: {_bridge_exc}")
        except Exception as exc:
            logger.error(f"[WEATHER] Windshear processing error: {exc}")

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
                if isinstance(mode, weather_radarMode):
                    # Already a valid enum value
                    pass
                elif isinstance(mode, int):
                    # Convert integer to enum value
                    mode = weather_radarMode(mode)
                elif hasattr(mode, '_value_'):
                    # Handle case where we receive an enum member
                    mode = weather_radarMode(mode._value_)
                elif mode is weather_radarMode:
                    # Handle case where we get the actual enum class itself (not an instance/member)
                    logger.info(f"[WEATHER] Received enum class itself, defaulting to SURVEILLANCE mode")
                    mode = weather_radarMode.SURVEILLANCE
                else:
                    logger.error(f"[WEATHER] Invalid mode type: {type(mode)}")
                    return
            except ValueError as e:
                logger.error(f"[WEATHER] Invalid mode value: {mode}")
                return
            except Exception as e:
                logger.error(f"[WEATHER] Error converting mode: {str(e)}")
                return


            # Check if we're already in this mode - no need to change or send completion
            if self.mode == mode:
                logger.info(f"[WEATHER] Already in mode {mode.name}, no change needed")
                #self._send_mode_change_completion(self.mode, mode)
                return

            logger.info(f"[WEATHER] Setting mode to: {mode.name}")

            old_mode = self.mode
            self.mode = mode

            logger.info(f"[WEATHER] Weather radar mode changed from {old_mode.name} to {mode.name}")
            logger.info("[WEATHER] Mode change completed")
            logger.debug(f"[WEATHER] Radar name: {self.name}")  # Keep radar name in debug log

            # Send mode change completion notification only if requested and modes are different
            if send_completion:
                logger.info(f"[WEATHER] Sending mode change completion notification (send_completion=True)")
                self._send_mode_change_completion(old_mode, mode, request_id)
            else:
                logger.info(f"[WEATHER] Skipping mode change completion notification (send_completion=False)")
        except Exception as e:
            logger.error(f"[WEATHER] Error setting mode for weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())

    def _send_mode_change_completion(self, old_mode, new_mode, request_id=None):
        """Send mode change completion notification to display system.

        This is critical for proper synchronization between radar and display systems.
        According to MIL-STD-1553B protocol, this separate completion message ensures
        that the display system knows when the radar has actually completed the mode change,
        rather than just acknowledging receipt of the command.

        Args:
            old_mode: The previous radar mode
            new_mode: The new radar mode
            request_id: The original request ID to include in the completion message
        """
        try:
            # Check if we're in startup mode - don't send messages during startup
            if self._in_startup:
                logger.info(f"[WEATHER] Skipping mode change completion notification during startup: {old_mode.name} -> {new_mode.name}")
                return

            # Only send if we have a radar messenger
            if not hasattr(self, 'radar_messenger') or not self.radar_messenger:
                logger.error("[WEATHER] Cannot send mode change completion - radar_messenger not available")
                return

            # Import the CompletionMessageHandler
            from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()

            # Log the mode change completion notification
            logger.info(f"[WEATHER] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=request_id,
                radar_type='weather_radar'
            )

            if success:
                logger.info(f"[WEATHER] Mode change completion notification sent successfully")
            else:
                logger.error(f"[WEATHER] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[WEATHER] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())

    def receive_message_sync(self, message: MIL_STD_1553B_Message):
        """
        Synchronous wrapper for receive_message.
        This method is called directly by RadarMessenger to avoid asyncio issues.
        """
        try:
            # Check if we're in startup mode and should discard messages
            if self._in_startup:
                current_time = time.time()
                if self._startup_complete_time and current_time < self._startup_complete_time:
                    logger.info(f"[WEATHER] Discarding message during startup: {message.message_type if hasattr(message, 'message_type') else None}")
                    return False
                else:
                    # Startup timeout has passed, set startup to false
                    self._in_startup = False
                    logger.info("[WEATHER] Startup period complete, now accepting messages")

            # Enhanced logging with more detailed message information
            logger.info(f"[WEATHER] *** RECEIVED MESSAGE ***")
            logger.info(f"[WEATHER] Message ID: {id(message)}")
            logger.info(f"[WEATHER] Message address: rt={message.rt_address}, sub={message.sub_address}")
            logger.info(f"[WEATHER] Message data: {message.data}")
            logger.info(f"[WEATHER] Message type: {message.message_type if hasattr(message, 'message_type') else None}")
            logger.info(f"[WEATHER] Command type: {message.command_type if hasattr(message, 'command_type') else None}")

            # Log all message attributes for detailed debugging
            logger.info(f"[WEATHER] Message attributes:")
            for attr_name in dir(message):
                if not attr_name.startswith('_') and not callable(getattr(message, attr_name)):
                    attr_value = getattr(message, attr_name)
                    logger.info(f"[WEATHER]   - {attr_name}: {attr_value}")

            # Process the message synchronously
            handler_was_called = self._process_message_sync(message)
            return handler_was_called
        except Exception as e:
            logger.error(f"[WEATHER] Error handling message synchronously for weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            return False


    async def receive_message_async(self, message: MIL_STD_1553B_Message):
        """
        Synchronous wrapper for receive_message.
        This method is called directly by RadarMessenger to avoid asyncio issues.
        """
        try:
            # Check if we're in startup mode and should discard messages
            if self._in_startup:
                current_time = time.time()
                if self._startup_complete_time and current_time < self._startup_complete_time:
                    logger.info(f"[WEATHER] Discarding message during startup: {message.message_type if hasattr(message, 'message_type') else None}")
                    return False
                else:
                    # Startup timeout has passed, set startup to false
                    self._in_startup = False
                    logger.info("[WEATHER] Startup period complete, now accepting messages")

            # Enhanced logging with more detailed message information
            logger.info(f"[WEATHER] *** RECEIVED MESSAGE ***")
            logger.info(f"[WEATHER] Message ID: {id(message)}")
            logger.info(f"[WEATHER] Message address: rt={message.rt_address}, sub={message.sub_address}")
            logger.info(f"[WEATHER] Message data: {message.data}")
            logger.info(f"[WEATHER] Message type: {message.message_type if hasattr(message, 'message_type') else None}")
            logger.info(f"[WEATHER] Command type: {message.command_type if hasattr(message, 'command_type') else None}")

            # Log all message attributes for detailed debugging
            logger.info(f"[WEATHER] Message attributes:")
            for attr_name in dir(message):
                if not attr_name.startswith('_') and not callable(getattr(message, attr_name)):
                    attr_value = getattr(message, attr_name)
                    logger.info(f"[WEATHER]   - {attr_name}: {attr_value}")

            # Process the message synchronously
            handler_was_called = self._process_message_sync(message)
            return handler_was_called
        except Exception as e:
            logger.error(f"[WEATHER] Error handling message synchronously for weather radar {self.name}: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _process_message_sync(self, message: MIL_STD_1553B_Message):
        """Process message synchronously."""
        try:
            # Extract request_id and command_name from original message before normalization
            original_request_id = getattr(message, 'request_id', None)
            original_command_name = getattr(message, 'command_name', None)
            logger.info(f"[WEATHER] Original message request_id: {original_request_id}, command_name: {original_command_name}")

            # Check for request_uuid from BaseMessage if request_id not found
            if original_request_id is None and hasattr(message, 'request_uuid'):
                original_request_id = getattr(message, 'request_uuid')
                logger.info(f"[WEATHER] Found request_uuid in original message: {original_request_id}")

            # Check metadata for request_id or request_uuid
            if original_request_id is None and hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                metadata = message.metadata
                if 'request_id' in metadata:
                    original_request_id = metadata['request_id']
                    logger.info(f"[WEATHER] Found request_id in metadata: {original_request_id}")
                elif 'request_uuid' in metadata:
                    original_request_id = metadata['request_uuid']
                    logger.info(f"[WEATHER] Found request_uuid in metadata: {original_request_id}")

            type = self.msg_type_detector.detect_message_type(message)
            logger.info(f"[WEATHER] Detected message type: {type}")

            radar_adapter = get_radar_message_adapter()
            normalized_message = radar_adapter.normalize_message(message)

            # Log normalized message fields
            logger.info(f"[WEATHER] Normalized message request_id: {normalized_message.get('request_id')}")
            logger.info(f"[WEATHER] Normalized message command_name: {normalized_message.get('command_name')}")

            # Use original request_id if normalized message lost it
            if not normalized_message.get('request_id') and original_request_id:
                normalized_message['request_id'] = original_request_id
                logger.info(f"[WEATHER] Restored request_id from original message: {original_request_id}")

            # Use original command_name if normalized message lost it
            if not normalized_message.get('command_name') and original_command_name:
                normalized_message['command_name'] = original_command_name
                logger.info(f"[WEATHER] Restored command_name from original message: {original_command_name}")
            try:
                if type == 'mode_handler':
                    # Handle mode change message synchronously
                    mode = message.data
                    # 16 bit bin to integer conversion
                    mode_bytes = bytes([int(mode[i:i+8], 2) for i in range(0, len(mode), 8)])
                    mode = int.from_bytes(mode_bytes, byteorder='big')
                    # Pass request_id to the handler
                    self._handle_mode_change_sync(mode, send_completion=True, request_id=normalized_message.get('request_id'))
                    return True
                elif type == 'vil_handler':
                    # Handle VIL data message synchronously - pass normalized message with preserved request_id
                    self._handle_vil_data_sync(message, request_id=normalized_message.get('request_id'))
                    return True
                elif type == 'precipitation_handler':
                    # Handle precipitation data message synchronously - pass normalized message with preserved request_id
                    self._handle_precipitation_data_sync(message, request_id=normalized_message.get('request_id'))
                    return True
            except Exception as e:
                logger.error(f"[WEATHER] Error processing message type {type}: {str(e)}")
                logger.error(traceback.format_exc())
                return False
            else:
                logger.warning(f"[WEATHER] Unknown message type: {type}")
                return False




        except Exception as e:
            logger.error(f"[WEATHER] Error processing message synchronously: {str(e)}")
            logger.error(traceback.format_exc())

    def _send_mode_change_completion_sync(self, old_mode, new_mode, request_id=None):
        """Send mode change completion notification synchronously."""
        try:
            # Check if we're in startup mode - don't send messages during startup
            if self._in_startup:
                logger.info(f"[WEATHER] Skipping mode change completion notification during startup: {old_mode.name} -> {new_mode.name}")
                return

            # Import the CompletionMessageHandler
            from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

            # Get the CompletionMessageHandler instance
            completion_handler = get_completion_message_handler()

            # Log the mode change completion notification
            logger.info(f"[WEATHER] Sending mode change completion notification: {old_mode.name} -> {new_mode.name}")

            # Send the mode change completion message SYNCHRONOUSLY
            success = completion_handler.send_mode_change_completion(
                system_name='radar',
                old_mode=old_mode.name,
                new_mode=new_mode.name,
                mode_value=new_mode.value,
                request_id=request_id,
                radar_type='weather_radar'
            )

            if success:
                logger.info(f"[WEATHER] Mode change completion notification sent successfully")
            else:
                logger.error(f"[WEATHER] Failed to send mode change completion notification")

        except Exception as e:
            logger.error(f"[WEATHER] Error sending mode change completion: {str(e)}")
            logger.error(traceback.format_exc())

    def _handle_mode_change_sync(self, mode, send_completion=True, request_id=None):
        """Handle mode change message synchronously."""
        try:
            logger.info(f"[WEATHER] Handling mode change message: {mode}, request_id: {request_id}")
            self.set_mode(mode, send_completion=True, request_id=request_id)
        except Exception as e:
            logger.error(f"[WEATHER] Error handling mode change message: {str(e)}")
            logger.error(traceback.format_exc())

    def _handle_vil_data_sync(self, message, request_id=None):
        """
        Synchronous version of _handle_vil_data.
        Handles VIL data message and generates realistic VIL data response.
        """
        try:
            logger.info("[WEATHER][VIL_FLOW] Generating VIL data response")
            logger.info("[WEATHER][VIL_FLOW] Handling VIL data message")
            logger.info("[WEATHER][VIL_FLOW] Processing VIL data")

            # Check if we're in standby mode
            if self.mode == weather_radarMode.STANDBY:
                logger.info("[WEATHER] Radar in STANDBY mode, no VIL data generated")
                return

            # Use RadarMessageAdapter to normalize the message
            radar_adapter = get_radar_message_adapter()

            # Add additional validation and debugging
            logger.info(f"[WEATHER] Raw message type: {type(message).__name__}")
            logger.info(f"[WEATHER] Message content: {message}")

            logger.info("[WEATHER] Processing confirmed VIL request")

            # Normalize the message to extract key information
            normalized_message = radar_adapter.normalize_message(message)
            logger.info(f"[WEATHER] Normalized message type: {normalized_message['message_type']}")
            logger.info(f"[WEATHER] Normalized command type: {normalized_message['command_type']}")
            logger.info(f"[WEATHER] Normalized RT address: {normalized_message['rt_address']}")
            logger.info(f"[WEATHER] Normalized subaddress: {normalized_message['subaddress']}")

            # Extract request ID with enhanced error handling
            original_request_id = normalized_message.get('request_id')

            if not original_request_id:

                raise ValueError("[WEATHER] No request ID found in message")

            # Get elevation angles for current mode
            elevation_angles = self.config['vcp'][self.mode.name.lower()]['elevs']

            # Generate simulated reflectivity data based on current radar state
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                self.mode.name.lower(),
                elevation_angles
            )

            # --- STORM CELL TRACKER -------------------------------------------
            # Feed reflectivity into the StormCellTracker (now connected).
            # Use the max-over-elevation 2D slice so the tracker sees the
            # composite reflectivity picture rather than a single tilt.
            try:
                reflectivity_2d = reflectivity.max(axis=1)  # (az, range)
                lowest_elev = float(elevation_angles[0]) if elevation_angles else 0.5
                self.storm_cell_tracker.process_radar_data(
                    reflectivity_data=reflectivity_2d,
                    scan_elevation=lowest_elev
                )
                cells = self.storm_cell_tracker.get_active_cells()
                if cells:
                    from FMOFP.local_messaging.routing.radar_to_display_bridge import push_cells_data
                    push_cells_data(cells, original_request_id)
                    logger.info(f"[WEATHER] Storm cell tracker: {len(cells)} active cells pushed to display")
            except Exception as _sct_exc:
                logger.warning(f"[WEATHER] Storm cell tracker failed (non-fatal): {_sct_exc}")
            # ------------------------------------------------------------------

            # Calculate VIL from reflectivity
            vil_data_array = self.vil_data_generator.calculate_vil(
                reflectivity,
                elevation_angles
            )

            # Generate VIL data objects with the original request ID
            vil_objects = self.vil_data_generator.generate_vil_data_objects(
                vil_data_array,
                original_request_id
            )

            # Create response message with the original request ID and current mode
            response = self.vil_data_generator.create_vil_response(
                vil_objects,
                original_request_id,
                self.mode.name  # Add current mode to response
            )

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            # Push data straight into the UI coordinator so the display
            # gets it immediately, independently of the 1553B routing path.
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_vil_data
                bridge_ok = push_vil_data(vil_objects, original_request_id)
                if bridge_ok:
                    logger.info(f"[WEATHER] Bridge: VIL data pushed to display coordinator")
                else:
                    logger.warning("[WEATHER] Bridge: push_vil_data returned False — coordinator may be unavailable")
            except Exception as _bridge_exc:
                logger.warning(f"[WEATHER] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

            # Send VIL data response
            logger.info(f"[WEATHER][VIL_FLOW] VIL data generated")
            logger.info(f"[WEATHER][VIL_STORE] Storing data")

            # Get RT address and subaddress from configuration
            rt_address, sub_address = get_rt_subaddress_pair('radar', 'weather_radar')

            # Route response through messaging system - SYNCHRONOUS VERSION
            if hasattr(self, 'radar_messenger') and self.radar_messenger:
                # First, send the actual VIL data using the radar messenger
                try:
                    # Send the VIL data response using the DataResponseSender
                    # This properly converts the MIL_STD_1553B_Message to the dictionary format expected by RT_sender
                    logger.info(f"[WEATHER] Sending VIL data message with {len(vil_objects)} data points")

                    # Import the DataResponseSender
                    from FMOFP.Systems.radarManagement.radar_messaging.data_response_sender import get_data_response_sender

                    # Get the DataResponseSender instance
                    data_sender = get_data_response_sender()

                    # Send the VIL data response using the data sender
                    data_result = data_sender.send_vil_data(
                        response,
                        rt_address=rt_address,
                        sub_address=sub_address,
                        request_id=original_request_id
                    )

                    if data_result:
                        logger.info(f"[WEATHER] Successfully sent VIL data message with {len(vil_objects)} data points")
                    else:
                        logger.error("[WEATHER] Failed to send VIL data message")

                except Exception as e:
                    logger.error(f"[WEATHER] Error sending VIL data message: {str(e)}")
                    logger.error(traceback.format_exc())

                # Then, send the completion message as before
                from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

                # Get the CompletionMessageHandler instance
                completion_handler = get_completion_message_handler()

                # Send the data completion message SYNCHRONOUSLY
                success = completion_handler.send_data_completion(
                    system_name='radar',
                    data_type='vil',
                    data=response,
                    request_id=original_request_id
                )

                if success:
                    logger.info(f"[WEATHER] Sent VIL data response with {len(vil_objects)} data points and request ID: {original_request_id}")
                else:
                    logger.error(f"[WEATHER] Failed to send VIL data response with request ID: {original_request_id}")
            else:
                logger.error("[WEATHER] Cannot send response - radar_messenger not available")

        except Exception as e:
            logger.error(f"Error handling VIL data synchronously: {str(e)}")
            logger.error(traceback.format_exc())

    def _run_precipitation_data_generator_sync(self, precip_data_array, request_id):
        """
        Direct call to the fully synchronous precipitation data generator.

        This implementation has built-in limits and optimizations to prevent performance issues.

        Args:
            precip_data_array: The precipitation data array
            request_id: The request ID

        Returns:
            List of precipitation data objects or empty list if error occurs
        """
        # Measure execution time
        start_time = time.time()

        try:
            # Log the input array details
            if precip_data_array is not None:
                logger.debug(f"[WEATHER] Generating precipitation data from array shape: {precip_data_array.shape}")
            else:
                logger.debug("[WEATHER] Generating precipitation data from None array")

            # Log which implementation we're using for debugging
            logger.info(f"[WEATHER] Using precipitation data generator: {self.precipitation_data_generator.__class__.__module__}")

            # Call the synchronous implementation directly
            result = self.precipitation_data_generator.generate_precipitation_data_objects(
                precip_data_array, request_id
            )

            # Check if result is a coroutine
            if hasattr(result, '__await__'):
                logger.error(f"[WEATHER] Error: precipitation data generator returned a coroutine instead of data points")
                # Return empty list as fallback
                return []

            # Log performance metrics
            elapsed_time = time.time() - start_time
            if result:
                logger.debug(f"[WEATHER] Precipitation data generator completed in {elapsed_time:.3f} seconds, produced {len(result)} objects")
            else:
                logger.warning(f"[WEATHER] Precipitation data generator completed in {elapsed_time:.3f} seconds but returned no results")

            return result
        except Exception as e:
            logger.error(f"[WEATHER] Error in precipitation data generator: {str(e)}")
            logger.error(traceback.format_exc())

            # Return empty list on error instead of fallback object
            logger.warning(f"[WEATHER] Returning empty list due to error in precipitation data generator")
            return []

    def _handle_precipitation_data_sync(self, message, request_id=None):
        """
        Synchronous version of _handle_precipitation_data.
        Handles precipitation data message and generates realistic precipitation data response.
        """
        total_start_time = time.time()

        try:
            logger.info("[WEATHER][PRECIP_FLOW] Generating precipitation data response")
            logger.info("[WEATHER][PRECIP_FLOW] Handling precipitation data message")
            logger.info("[WEATHER][PRECIP_FLOW] Processing precipitation data")

            # Check if we're in standby mode
            if self.mode == weather_radarMode.STANDBY:
                logger.info("[WEATHER] Radar in STANDBY mode, no precipitation data generated")
                return

            # Use RadarMessageAdapter to normalize the message
            message_start_time = time.time()
            radar_adapter = get_radar_message_adapter()

            # Add additional validation and debugging
            logger.info(f"[WEATHER] Raw message type: {type(message).__name__}")
            logger.info(f"[WEATHER] Message content: {message}")

            logger.info("[WEATHER] Processing confirmed precipitation request")

            # Normalize the message to extract key information
            normalized_message = radar_adapter.normalize_message(message)
            logger.info(f"[WEATHER] Normalized message type: {normalized_message['message_type']}")
            logger.info(f"[WEATHER] Normalized command type: {normalized_message['command_type']}")
            logger.info(f"[WEATHER] Normalized RT address: {normalized_message['rt_address']}")
            logger.info(f"[WEATHER] Normalized subaddress: {normalized_message['subaddress']}")

            # Extract request ID with enhanced error handling
            original_request_id = normalized_message.get('request_id')


            message_process_time = time.time() - message_start_time
            logger.debug(f"[WEATHER] Message processing completed in {message_process_time:.3f} seconds")

            # Get elevation angles for current mode
            elevation_angles = self.config['vcp'][self.mode.name.lower()]['elevs']

            # Generate simulated reflectivity data based on current radar state
            reflectivity_start_time = time.time()
            reflectivity = self.reflectivity_simulator.generate_reflectivity(
                self.mode.name.lower(),
                elevation_angles
            )
            reflectivity_time = time.time() - reflectivity_start_time
            logger.debug(f"[WEATHER] Reflectivity generation completed in {reflectivity_time:.3f} seconds")

            # --- PRECIPITATION ANALYZER --------------------------------------
            # Run the richer PrecipitationAnalyzer (Marshall-Palmer Z-R,
            # type classification) alongside the existing generator.
            try:
                reflectivity_2d_p = reflectivity.max(axis=1)  # composite
                lowest_elev_p = float(elevation_angles[0]) if elevation_angles else 0.5
                self.precip_analyzer.process_radar_data(
                    reflectivity_data=reflectivity_2d_p,
                    scan_elevation=lowest_elev_p
                )
                enriched = self.precip_analyzer.get_precipitation_data()
                if enriched:
                    logger.info(
                        f"[WEATHER] PrecipitationAnalyzer produced "
                        f"{len(enriched)} enriched precipitation points "
                        f"(types: {set(p.type for p in enriched)})"
                    )
            except Exception as _pa_exc:
                logger.warning(f"[WEATHER] PrecipitationAnalyzer failed (non-fatal): {_pa_exc}")
            # ------------------------------------------------------------------

            # Calculate precipitation from reflectivity
            precip_calc_start_time = time.time()
            precip_data_array = self.precipitation_data_generator.calculate_precipitation(
                reflectivity,
                elevation_angles
            )
            precip_calc_time = time.time() - precip_calc_start_time
            logger.debug(f"[WEATHER] Precipitation calculation completed in {precip_calc_time:.3f} seconds")

            # Generate precipitation data objects with the original request ID
            precip_objects_start_time = time.time()
            precip_objects = self._run_precipitation_data_generator_sync(
                precip_data_array,
                original_request_id
            )
            precip_objects_time = time.time() - precip_objects_start_time
            logger.info(f"[WEATHER] Precipitation objects generation completed in {precip_objects_time:.3f} seconds")

            # Create response message with the original request ID and current mode
            response_start_time = time.time()
            response = self.precipitation_data_generator.create_precipitation_response(
                precip_objects,
                original_request_id,
                self.mode.name  # Add current mode to response
            )
            response_time = time.time() - response_start_time
            logger.debug(f"[WEATHER] Response creation completed in {response_time:.3f} seconds")

            # Check if precip_objects is a coroutine
            if hasattr(precip_objects, '__await__'):
                logger.error(f"[WEATHER][PRECIP_DETAIL] Error: precipitation data generator returned a coroutine instead of data points")
                # Get a safe placeholder value
                logger.error(f"[WEATHER] Generated 0 precipitation data points (coroutine error) with request ID: {original_request_id}")
            else:
                logger.info(f"[WEATHER] Generated {len(precip_objects)} precipitation data points with request ID: {original_request_id}")
            logger.info(f"[WEATHER][PRECIP_FLOW] Precipitation data generated")

            # --- DIRECT DISPLAY BRIDGE -----------------------------------
            # Push data straight into the UI coordinator (same pattern as VIL).
            try:
                from FMOFP.local_messaging.routing.radar_to_display_bridge import push_precipitation_data
                bridge_ok = push_precipitation_data(precip_objects, original_request_id)
                if bridge_ok:
                    logger.info(f"[WEATHER] Bridge: precipitation data pushed to display coordinator")
                else:
                    logger.warning("[WEATHER] Bridge: push_precipitation_data returned False")
            except Exception as _bridge_exc:
                logger.warning(f"[WEATHER] Bridge push failed (non-fatal): {_bridge_exc}")
            # -------------------------------------------------------------

            # Get RT address and subaddress from configuration
            rt_address, sub_address = get_rt_subaddress_pair('radar', 'weather_radar')

            # Route response through messaging system - SYNCHRONOUS VERSION
            message_send_start_time = time.time()
            if hasattr(self, 'radar_messenger') and self.radar_messenger:
                # First, send the actual precipitation data using the radar messenger
                try:
                    # Send the precipitation data response using the DataResponseSender
                    # This properly converts the MIL_STD_1553B_Message to the dictionary format expected by RT_sender
                    logger.info(f"[WEATHER] Sending precipitation data message with {len(precip_objects)} data points")
                    for i in range(len(precip_objects)):
                        logger.info(f"[WEATHER] Precipitation object {i}: {precip_objects[i]}")


                    # Import the DataResponseSender
                    from FMOFP.Systems.radarManagement.radar_messaging.data_response_sender import get_data_response_sender

                    # Get the DataResponseSender instance
                    data_sender = get_data_response_sender()

                    # Send the precipitation data response using the data sender
                    data_result = data_sender.send_precipitation_data(
                        response,
                        rt_address=rt_address,
                        sub_address=sub_address,
                        request_id=original_request_id
                    )

                    if data_result:
                        logger.info(f"[WEATHER] Successfully sent precipitation data message with {len(precip_objects)} data points")
                    else:
                        logger.error("[WEATHER] Failed to send precipitation data message")

                except Exception as e:
                    logger.error(f"[WEATHER] Error sending precipitation data message: {str(e)}")
                    logger.error(traceback.format_exc())

                # Then, send the completion message as before
                from FMOFP.Systems.radarManagement.radar_messaging.completion_message_handler import get_completion_message_handler

                # Get the CompletionMessageHandler instance
                completion_handler = get_completion_message_handler()

                # Send the data completion message SYNCHRONOUSLY
                success = completion_handler.send_data_completion(
                    system_name='radar',
                    data_type='precipitation',
                    data=response,
                    request_id=original_request_id
                )

                if success:
                    logger.info(f"[WEATHER] Sent precipitation data response with {len(precip_objects)} data points and request ID: {original_request_id}")
                else:
                    logger.error(f"[WEATHER] Failed to send precipitation data response with request ID: {original_request_id}")
            else:
                logger.error("[WEATHER] Cannot send response - radar_messenger not available")

            message_send_time = time.time() - message_send_start_time
            logger.debug(f"[WEATHER] Message sending completed in {message_send_time:.3f} seconds")

            # Report total processing time
            total_time = time.time() - total_start_time
            logger.info(f"[WEATHER] Total precipitation data processing completed in {total_time:.3f} seconds")

        except Exception as e:
            # Total error handling time
            total_error_time = time.time() - total_start_time
            logger.error(f"Error handling precipitation data synchronously: {str(e)}")
            logger.error(traceback.format_exc())
            logger.error(f"[WEATHER] Precipitation data processing failed after {total_error_time:.3f} seconds")


    def _get_default_config(self):
        """Return default configuration."""
        return {
            'pulse_width': {'min': 0.1, 'max': 10},
            'prf': {'min': 100, 'max': 2000},
            'antenna_gain': 30,
            'frequency': 9.345,
            'tilt_range': {'min': 0, 'max': 90},
            'scan_range': {'min': 10, 'max': 200},
            'vcp': {
                'surveillance': {'elevs': (0.5, 1.5, 2.4, 3.4), 'update_rate': 20},
                'mapping': {'elevs': (0.5, 1.5, 3.0, 4.5, 6.0, 7.5, 9.0), 'update_rate': 120}
            },
            'vil_params': {'a': 2.55e-6, 'b': 0.55},
            'shear_params': {'threshold': 5},
            'turb_params': {'threshold': 15},
            'simulated': True
        }

    def _is_vil_request(self, message: Any, normalized_message: Dict[str, Any] = None) -> bool:
        """
        Determine if a message is a VIL data request using the centralized helper function.

        Args:
            message: The message to check
            normalized_message: Optional pre-normalized message (used for compatibility)

        Returns:
            bool: True if the message is a VIL data request, False otherwise
        """
        try:
            # Use the standardized helper from the centralized message_types module
            result = is_vil_message(message)
            logger.info(f"[WEATHER][VIL_FLOW] is_vil_message helper result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error checking if message is VIL request: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    def _is_precipitation_request(self, message: Any, normalized_message: Dict[str, Any] = None) -> bool:
        """
        Determine if a message is a precipitation data request using the centralized helper function.

        Args:
            message: The message to check
            normalized_message: Optional pre-normalized message (used for compatibility)

        Returns:
            bool: True if the message is a precipitation data request, False otherwise
        """
        try:
            # Use the standardized helper from the centralized message_types module
            result = is_precipitation_message(message)
            logger.info(f"[WEATHER][PRECIP_FLOW] is_precipitation_message helper result: {result}")
            return result
        except Exception as e:
            logger.error(f"Error checking if message is precipitation request: {str(e)}")
            logger.error(traceback.format_exc())
            return False

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
                **self._resource_usage
            }

    def get_data(self, data_type: str) -> Dict:
        """Get radar data."""
        with self._lock:
            if data_type == "surveillance":
                return self._get_surveillance_data()
            elif data_type == "mapping":
                return self._get_mapping_data()
            else:
                logger.warning(f"Unknown data type requested: {data_type}")
                return {}

    def set_range(self, range_km):
        with self._lock:
            self.range = range_km

    def scan(self):
        if self.mode == weather_radarMode.STANDBY:
            return

        with self._lock:
            # Perform radar scan and signal processing to generate products
            ref, vel, width = self._process_raw_data()
            vil = self._calculate_vil(ref)
            shear = self._detect_wind_shear(vel, width)
            turb = self._detect_turbulence(width)
            echo_tops = self._calculate_echo_tops(ref)
            self._send_weather_products(ref, vel, vil, shear, turb, echo_tops)

    def _process_raw_data(self):
        # Simulate raw reflectivity, velocity, spectrum width data
        # using radar parameters and weather simulation
        ref = None
        vel = None
        width = None
        return ref, vel, width

    def _calculate_vil(self, ref):
        """Calculate Vertically Integrated Liquid (VIL) from reflectivity volume scan."""
        if ref is None:
            return None

        # Use the VIL data generator to calculate VIL
        elevation_angles = self.config['vcp'][self.mode.name.lower()]['elevs']
        return self.vil_data_generator.calculate_vil(ref, elevation_angles)

    def _detect_wind_shear(self, vel, width):
        # Detect wind shear signatures from velocity and spectrum width data
        if vel is None or width is None:
            return None

        shear = np.zeros(vel.shape[::2])  # Initialize shear array

        for az in range(vel.shape[0]):
            for r in range(1, vel.shape[2] - 1):
                # Calculate radial shear
                radial_shear = (vel[az, :, r+1] - vel[az, :, r-1]) / 2
                # Calculate azimuthal shear
                az_next = (az + 1) % vel.shape[0]
                az_prev = (az - 1) % vel.shape[0]
                azimuthal_shear = (vel[az_next, :, r] - vel[az_prev, :, r]) / 2

                # Combine radial and azimuthal shear
                total_shear = np.sqrt(radial_shear**2 + azimuthal_shear**2)

                # Check if shear exceeds threshold and spectrum width is significant
                shear[az, r] = np.any((total_shear > self.config['shear_params']['threshold']) &
                                      (width[az, :, r] > self.config['turb_params']['threshold']))

        return shear

    def _detect_turbulence(self, width):
        # Detect turbulence from spectrum width data
        if width is None:
            return None
        turb = width > self.config['turb_params']['threshold']
        return turb

    def _calculate_echo_tops(self, ref):
        # Calculate height of storm echo tops from reflectivity data
        if ref is None:
            return None

        echo_tops = np.zeros((ref.shape[0], ref.shape[2]))  # Initialize echo tops array

        # Assuming each elevation step represents 1 km in height (adjust as needed)
        height_per_step = 1.0

        for az in range(ref.shape[0]):
            for r in range(ref.shape[2]):
                # Find the highest elevation where reflectivity exceeds a threshold (e.g., 18 dBZ)
                echo_top = np.argwhere(ref[az, :, r] > 18)
                if echo_top.size > 0:
                    echo_tops[az, r] = (echo_top[-1][0] + 1) * height_per_step

        return echo_tops

    def _get_surveillance_data(self) -> Dict:
        """Get surveillance data."""
        return {
            'type': 'surveillance',
            'timestamp': time.time(),
            'data': {}  # Add actual data here
        }

    def _get_mapping_data(self) -> Dict:
        """Get mapping data."""
        return {
            'type': 'mapping',
            'timestamp': time.time(),
            'data': {}  # Add actual data here
        }

    def update_real(self):
        """Update real radar system."""
        try:
            # Adjust tilt and range based on aircraft altitude and speed
            self._update_tilt_and_range()

            # Perform radar scan
            self.scan()

        except Exception as e:
            logger.error(f"weather_radar {self.name}: Error in real update: {e}")
            raise

    def update_simulated(self):
        """Update simulated radar system."""
        try:
            # Generate simulated data
            ref = self._get_simulated_reflectivity()
            vel = self._get_simulated_velocity()
            width = self._get_simulated_spectrum_width()

            # Process simulated data
            vil = self._calculate_vil(ref)
            shear = self._detect_wind_shear(vel, width)
            turb = self._detect_turbulence(width)
            echo_tops = self._calculate_echo_tops(ref)

            # Send processed data
            self._send_weather_products(ref, vel, vil, shear, turb, echo_tops)

        except Exception as e:
            logger.error(f"weather_radar {self.name}: Error in simulated update: {e}")
            raise

    def _get_simulated_reflectivity(self):
        """Generate a 3D volume of simulated reflectivity data using the reflectivity simulator."""
        elevation_angles = self.config['vcp'][self.mode.name.lower()]['elevs']
        return self.reflectivity_simulator.generate_reflectivity(self.mode.name.lower(), elevation_angles)

    def _get_simulated_velocity(self):
        # Generate a 3D volume of simulated velocity data
        azimuth_steps = 360
        elevation_steps = len(self.config['vcp'][self.mode.name.lower()]['elevs'])
        range_steps = 1000

        # Create a 3D array to store velocity values
        velocity = np.zeros((azimuth_steps, elevation_steps, range_steps))

        # Generate realistic velocity patterns
        for az in range(azimuth_steps):
            for el in range(elevation_steps):
                for r in range(range_steps):
                    # Simulate wind patterns
                    base_velocity = 10 * np.sin(2 * np.pi * az / azimuth_steps)  # Sinusoidal wind pattern
                    altitude_factor = 1 + (el / elevation_steps)  # Increase wind speed with altitude
                    range_factor = 1 - (r / range_steps) * 0.5  # Decrease wind speed with range

                    velocity[az, el, r] = base_velocity * altitude_factor * range_factor

                    # Add some randomness to create more realistic patterns
                    velocity[az, el, r] += np.random.normal(0, 2)

        # Ensure velocity values are within a realistic range (e.g., -50 to 50 m/s)
        velocity = np.clip(velocity, -50, 50)

        return velocity

    def _get_simulated_spectrum_width(self):
        # Generate a 3D volume of simulated spectrum width data
        azimuth_steps = 360
        elevation_steps = len(self.config['vcp'][self.mode.name.lower()]['elevs'])
        range_steps = 1000

        # Create a 3D array to store spectrum width values
        spectrum_width = np.zeros((azimuth_steps, elevation_steps, range_steps))

        # Generate realistic spectrum width patterns
        for az in range(azimuth_steps):
            for el in range(elevation_steps):
                for r in range(range_steps):
                    # Simulate turbulence
                    base_width = 2 + 3 * np.random.random()  # Base spectrum width between 2 and 5 m/s
                    altitude_factor = 1 + (el / elevation_steps) * 0.5  # Increase turbulence with altitude
                    range_factor = 1 - (r / range_steps) * 0.3  # Slight decrease in turbulence with range

                    spectrum_width[az, el, r] = base_width * altitude_factor * range_factor

                    # Add some randomness to create more realistic patterns
                    spectrum_width[az, el, r] += np.random.normal(0, 0.5)

        # Ensure spectrum width values are within a realistic range (e.g., 0 to 10 m/s)
        spectrum_width = np.clip(spectrum_width, 0, 10)

        return spectrum_width

    def _update_tilt_and_range(self):
        with self._lock:
            if hasattr(self.radar_control, 'aircraft'):
                altitude_km = self.radar_control.aircraft.altitude / 1000
                speed_km_s = self.radar_control.aircraft.speed / 1000

                self.tilt = max(self.config['tilt_range']['min'],
                                min(self.config['tilt_range']['max'],
                                    altitude_km))
                self.range = max(self.config['scan_range']['min'],
                                min(self.config['scan_range']['max'],
                                    speed_km_s * 60))

    def _convert_reflectivity_data(self, ref_data):
        # Convert reflectivity data format
        # This will depend on how reflectivity is represented in the simulation state
        # For now, we'll assume it's already in the correct format
        return ref_data

    def _convert_velocity_data(self, vel_data):
        # Convert velocity data format
        # This will depend on how wind velocity is represented in the simulation state
        # For now, we'll assume it's already in the correct format
        return vel_data

    def _convert_turbulence_to_spectrum_width(self, turb_data):
        # Convert turbulence data to spectrum width
        # This will involve modeling the spectral broadening caused by turbulence
        # For simplicity, we'll use a linear relationship for now
        return turb_data * 0.1  # Arbitrary scaling factor

    def _dict_to_xml(self, root_name, data_dict):
        root = ET.Element(root_name)
        for key, value in data_dict.items():
            child = ET.SubElement(root, key)
            child.text = str(value)
        return root

    def _send_weather_products(self, ref, vel, vil, shear, turb, echo_tops):
        """Send processed weather products."""
        try:
            # Package data
            products = {
                'reflectivity': ref,
                'velocity': vel,
                'vil': vil,
                'shear': shear,
                'turbulence': turb,
                'echo_tops': echo_tops
            }
            # Log products
            logger.debug(f"Weather products generated: {list(products.keys())}")
        except Exception as e:
            logger.error(f"Error sending weather products: {e}")
