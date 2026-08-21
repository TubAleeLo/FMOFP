"""
Routing Registry

Single source of truth for routing information in the FMOFP system.
Loads system addresses, subaddresses, command types, and message types from XML files.
Uses centralized message type constants for consistency.
"""

import threading
import traceback
from xml.etree import ElementTree as ET

from FMOFP.Utils.logger.sys_logger import get_logger
# Import centralized message type constants
from FMOFP.local_messaging.message_types import (
    WEATHER_RADAR_MODE_CHANGE_REQUEST,
    WEATHER_RADAR_MODE_CHANGE_RESPONSE,
    WEATHER_RADAR_VIL_REQUEST,
    WEATHER_RADAR_VIL_RESPONSE,
    WEATHER_RADAR_PRECIPITATION_REQUEST,
    WEATHER_RADAR_PRECIPITATION_RESPONSE,
    TFR_RADAR_MODE_CHANGE_REQUEST,
    TFR_RADAR_MODE_CHANGE_RESPONSE,
    SAR_RADAR_MODE_CHANGE_REQUEST,
    SAR_RADAR_MODE_CHANGE_RESPONSE,
    TARGETING_RADAR_MODE_CHANGE_REQUEST,
    TARGETING_RADAR_MODE_CHANGE_RESPONSE,
    AEWC_RADAR_MODE_CHANGE_REQUEST,
    AEWC_RADAR_MODE_CHANGE_RESPONSE,
    # Communications message types
    COMMS_STATUS_REQUEST,
    COMMS_STATUS_RESPONSE,
    COMMS_RADIO_FREQ_SET,
    COMMS_RADIO_MODE_SET,
    COMMS_SATCOM_ACQUIRE,
    COMMS_DATALINK_MODE_SET,
    COMMS_TRANSMIT_RADIO,
    COMMS_SEND_SATCOM,
    COMMS_SEND_DATALINK,
    COMMS_DATA_UPDATE,
    # Mission Planning message types
    MISSION_STATUS_REQUEST,
    MISSION_STATUS_RESPONSE,
    MISSION_PHASE_SET,
    MISSION_PHASE_ADVANCE,
    MISSION_WAYPOINT_ADD,
    MISSION_WAYPOINT_REMOVE,
    MISSION_TARGET_DESIGNATE,
    MISSION_TARGET_ENGAGE,
    MISSION_TARGET_BDA,
    MISSION_TARGET_UPDATE,
    MISSION_UNIT_ADD,
    MISSION_UNIT_UPDATE,
    MISSION_ROUTE_OPTIMISE,
    MISSION_OBJECTIVES_SET,
    MISSION_ROE_SET,
    MISSION_INTEL_UPDATE,
    MISSION_DATA_UPDATE,
)
# Import address utilities
from FMOFP.local_messaging.address_utils import get_rt_address, get_subaddress

logger = get_logger()

class RoutingRegistry:
    _instance = None
    _lock = threading.RLock()
    _initialized = False

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(RoutingRegistry, cls).__new__(cls)
            return cls._instance

    def __init__(self):
        with self.__class__._lock:
            if not self.__class__._initialized:
                self.systems = {}
                self.rt_addresses = {}
                self.subaddresses = {}
                self.command_types = {}
                self.message_types = {}
                self.special_cases = {}
                self.logger = get_logger()
                self.__class__._initialized = True
                logger.info("RoutingRegistry initialized")

    def load_from_xml(self, address_book_path, command_registry_path):
        """Load routing information from XML files."""
        self._load_address_book(address_book_path)
        self._load_command_registry(command_registry_path)
        self._initialize_special_cases()
        self._initialize_comms_special_cases()
        self._initialize_mission_special_cases()

    def _load_address_book(self, path):
        """Load system addresses and subaddresses from address_book.xml."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Load system addresses
            for system in root.findall('system'):
                system_id = system.get('id')
                system_name = system.find('name').text
                address = int(system.find('address').text)

                self.systems[system_id] = {
                    'name': system_name,
                    'address': address,
                    'subaddresses': {}
                }

                self.rt_addresses[address] = system_id

            # Load subaddresses
            for subaddr in root.findall('subaddress'):
                subaddr_id = subaddr.get('id')
                subaddr_name = subaddr.find('name').text
                subaddr_value = int(subaddr.find('subaddress').text)

                self.subaddresses[subaddr_id] = {
                    'name': subaddr_name,
                    'value': subaddr_value
                }

                # Add to each system
                for system_id, system in self.systems.items():
                    system['subaddresses'][subaddr_id] = subaddr_value

            self.logger.info(f"Loaded {len(self.systems)} systems and {len(self.subaddresses)} subaddresses from address book")

        except Exception as e:
            self.logger.error(f"Error loading address book: {e}")
            self.logger.error(traceback.format_exc())
            raise

    def _load_command_registry(self, path):
        """Load command types and message types from command_registry.xml."""
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            # Load commands
            for command in root.findall('command'):
                command_name = command.find('name').text
                command_value = command.find('value').text

                # Extract system and command type from name
                parts = command_name.split('_')
                if len(parts) >= 2:
                    system_id = parts[0]
                    command_type = '_'.join(parts[1:])

                    # Add to command types
                    if system_id not in self.command_types:
                        self.command_types[system_id] = {}

                    self.command_types[system_id][command_type] = command_value

                    # Add to message types
                    self.message_types[command_name] = {
                        'system_id': system_id,
                        'command_type': command_type,
                        'value': command_value
                    }

            self.logger.info(f"Loaded {len(self.message_types)} message types from command registry")

        except Exception as e:
            self.logger.error(f"Error loading command registry: {e}")
            self.logger.error(traceback.format_exc())
            raise

    def _initialize_special_cases(self):
        """Initialize special case routing rules using centralized constants."""
        # VIL data routing - separate request and response paths
        # VIL REQUEST routing - goes TO radar
        self.special_cases['vil_request'] = {
            'command_names': [
                'radar_vilData',
                'displays_vilData',
                'weather_radar_vilData',
                'WEATHER_RADAR_VIL_DATA'
            ],
            'message_types': [
                WEATHER_RADAR_VIL_REQUEST,  # Use centralized constant
                'weather_radarVILRequest',  # Keep legacy type for compatibility
                'vil_request'
            ],
            'destinations': ['radar'],  # Send requests TO the radar
            'handler': 'vil_handler'
        }

        # VIL RESPONSE routing - comes FROM radar TO display
        self.special_cases['vil_response'] = {
            'command_names': [
                'radar_vilData',
                'displays_vilData',
                'weather_radar_vilData'
            ],
            'message_types': [
                WEATHER_RADAR_VIL_RESPONSE,  # Use centralized constant
                'weather_radarVILResponse',  # Keep legacy type for compatibility
                'vil_data',
                'weather_radarVILDataResponse'
            ],
            'destinations': ['display'],  # Send responses TO the display
            'handler': 'vil_handler'
        }

        # Precipitation data routing
        self.special_cases['precipitation_data'] = {
            'command_names': [
                'radar_precipitationData',
                'displays_precipitationData',
                'weather_radar_precipitationData',
                'WEATHER_RADAR_PRECIP_DATA'  # Added command name to match logs
            ],
            'message_types': [
                WEATHER_RADAR_PRECIPITATION_RESPONSE,  # Use centralized constant
                'weather_radarPrecipitationResponse',  # Keep legacy type for compatibility
                'precipitation_data',
                'weather_radarPrecipitationDataResponse'
            ],
            'destinations': ['display'],  # ONLY route to display, not radar
            'handler': 'precipitation_handler'
        }

        # Precipitation request routing
        self.special_cases['precipitation_request'] = {
            'command_names': [
                'radar_precipitationData',
                'displays_precipitationData',
                'weather_radar_precipitationData',
                'WEATHER_RADAR_PRECIP_DATA'
            ],
            'message_types': [
                WEATHER_RADAR_PRECIPITATION_REQUEST,  # Use centralized constant
                'weather_radarPrecipitationRequest',  # Keep legacy type for compatibility
                'precipitation_request'
            ],
            'destinations': ['radar'],  # Route requests TO the radar
            'handler': 'precipitation_handler'
        }

        # Precipitation completion routing
        self.special_cases['precipitation_completion'] = {
            'command_names': [
                'WEATHER_RADAR_PRECIPITATION_COMPLETION',
                'RADAR_PRECIPITATION_COMPLETION'
            ],
            'message_types': [
                'weather_radarPrecipitationCompletion',
                'radarPrecipitationCompletion',
                'precipitation_completion'
            ],
            'destinations': ['display'],  # Only route to display, not back to radar
            'handler': 'precipitation_handler'  # Reuse existing handler
        }

        # Mode change routing - using centralized constants
        self.special_cases['mode_change'] = {
            'command_names': [
                'radar_modeChange',
                'displays_modeChange',
                'weather_radar_modeChange',
                'tfr_radar_modeChange',
                'sar_radar_modeChange',
                'targeting_radar_modeChange',
                'aewc_radar_modeChange'
            ],
            'message_types': [
                # Use centralized constants
                WEATHER_RADAR_MODE_CHANGE_REQUEST,
                WEATHER_RADAR_MODE_CHANGE_RESPONSE,
                TFR_RADAR_MODE_CHANGE_REQUEST,
                TFR_RADAR_MODE_CHANGE_RESPONSE,
                SAR_RADAR_MODE_CHANGE_REQUEST,
                SAR_RADAR_MODE_CHANGE_RESPONSE,
                TARGETING_RADAR_MODE_CHANGE_REQUEST,
                TARGETING_RADAR_MODE_CHANGE_RESPONSE,
                AEWC_RADAR_MODE_CHANGE_REQUEST,
                AEWC_RADAR_MODE_CHANGE_RESPONSE,
                # Keep legacy types for compatibility
                'weather_radarModeChangeRequest',
                'weather_radarModeChangeResponse',
                'tfr_radarModeChangeRequest',
                'tfr_radarModeChangeResponse',
                'sar_radarModeChangeRequest',
                'sar_radarModeChangeResponse',
                'targeting_radarModeChangeRequest',
                'targeting_radarModeChangeResponse',
                'aewc_radarModeChangeRequest',
                'aewc_radarModeChangeResponse',
                'mode_change',
                'display_mode_request'
            ],
            'destinations': ['radar', 'display'],
            'handler': 'mode_change_handler'
        }

        # Mode change completion routing - separate from regular mode changes
        # This ensures completion messages only go to display, not back to radar
        self.special_cases['mode_change_completion'] = {
            'command_names': [
                'WEATHER_RADAR_MODE_CHANGE_COMPLETION',
                'TFR_RADAR_MODE_CHANGE_COMPLETION',
                'SAR_RADAR_MODE_CHANGE_COMPLETION',
                'TARGETING_RADAR_MODE_CHANGE_COMPLETION',
                'AEWC_RADAR_MODE_CHANGE_COMPLETION'
            ],
            'message_types': [
                'weather_radarModeChangeCompletion',
                'tfr_radarModeChangeCompletion',
                'sar_radarModeChangeCompletion',
                'targeting_radarModeChangeCompletion',
                'aewc_radarModeChangeCompletion',
                'mode_change_completion'
            ],
            'destinations': ['display'],  # Only route to display, not back to radar
            'handler': 'mode_change_handler'  # Use the same handler
        }

        # FMS mode change request routing
        self.special_cases['fms_mode_change_request'] = {
            'command_names': [
                'FMS_MODE_CHANGE',
                'FMS_SET_MODE',
                'fms_modeChange',
                'flightManagementSystem_modeChange'
            ],
            'message_types': [
                'fms_modeChangeRequest',
                'flightManagementSystemCommand',
                'fmsModeChangeRequest'
            ],
            'destinations': ['flightmanagementsystem'],  # Route to FMS
            'handler': 'fms_mode_change_handler'
        }

        # FMS mode change response routing
        self.special_cases['fms_mode_change_response'] = {
            'command_names': [
                'FMS_MODE_CHANGE_COMPLETE',
                'fms_modeChangeComplete',
                'flightManagementSystem_modeChangeComplete'
            ],
            'message_types': [
                'fms_modeChangeResponse',
                'fmsModeChangeResponse',
                'flightManagementSystemResponse'
            ],
            'destinations': ['display'],  # Route to display to update UI
            'handler': 'fms_mode_change_handler'
        }

        # FMS status request routing
        self.special_cases['fms_status_request'] = {
            'command_names': [
                'FMS_STATUS_REQUEST',
                'fms_statusRequest',
                'flightManagementSystem_statusRequest'
            ],
            'message_types': [
                'fms_statusRequest',
                'fmsStatusRequest'
            ],
            'destinations': ['flightmanagementsystem'],  # Route to FMS
            'handler': 'fms_status_handler'
        }

        # FMS status response routing
        self.special_cases['fms_status_response'] = {
            'command_names': [
                'FMS_STATUS_RESPONSE',
                'fms_statusResponse',
                'flightManagementSystem_statusResponse'
            ],
            'message_types': [
                'fms_statusResponse',
                'fmsStatusResponse'
            ],
            'destinations': ['display'],  # Route to display to update UI
            'handler': 'fms_status_handler'
        }

        # FMS attitude update request routing
        self.special_cases['fms_attitude_update'] = {
            'command_names': [
                'FMS_ATTITUDE_UPDATE',
                'fms_attitudeUpdate',
                'flightManagementSystem_attitudeUpdate'
            ],
            'message_types': [
                'fms_attitudeUpdateRequest',
                'fmsAttitudeUpdateRequest'
            ],
            'destinations': ['flightmanagementsystem'],  # Route to FMS
            'handler': 'fms_attitude_handler'
        }

        self.logger.info(f"Initialized {len(self.special_cases)} special case routing rules")

    def _initialize_comms_special_cases(self):
        """Routing rules for the Communications system."""
        # Status request — display or pilot querying comms health
        self.special_cases['comms_status_request'] = {
            'command_names': ['COMMS_STATUS_REQUEST', 'comms_statusRequest'],
            'message_types': [COMMS_STATUS_REQUEST, 'comms_statusRequest'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        # Status response — comms responding to display
        self.special_cases['comms_status_response'] = {
            'command_names': ['COMMS_STATUS_RESPONSE', 'comms_statusResponse'],
            'message_types': [COMMS_STATUS_RESPONSE, 'comms_statusResponse'],
            'destinations': ['display'],
            'handler': 'comms_handler',
        }
        # Radio controls — frequency, mode
        self.special_cases['comms_radio_freq'] = {
            'command_names': ['COMMS_RADIO_FREQ_SET', 'comms_radioFreqSet'],
            'message_types': [COMMS_RADIO_FREQ_SET, 'comms_radioFreqSet'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        self.special_cases['comms_radio_mode'] = {
            'command_names': ['COMMS_RADIO_MODE_SET', 'comms_radioModeSet'],
            'message_types': [COMMS_RADIO_MODE_SET, 'comms_radioModeSet'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        # SatCom acquire command
        self.special_cases['comms_satcom_acquire'] = {
            'command_names': ['COMMS_SATCOM_ACQUIRE', 'comms_satcomAcquire'],
            'message_types': [COMMS_SATCOM_ACQUIRE, 'comms_satcomAcquire'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        # DataLink mode set
        self.special_cases['comms_datalink_mode'] = {
            'command_names': ['COMMS_DATALINK_MODE_SET', 'comms_datalinkModeSet'],
            'message_types': [COMMS_DATALINK_MODE_SET, 'comms_datalinkModeSet'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        # Transmit commands
        self.special_cases['comms_transmit_radio'] = {
            'command_names': ['COMMS_TRANSMIT_RADIO', 'comms_transmitRadio'],
            'message_types': [COMMS_TRANSMIT_RADIO, 'comms_transmitRadio'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        self.special_cases['comms_send_satcom'] = {
            'command_names': ['COMMS_SEND_SATCOM', 'comms_sendSatcom'],
            'message_types': [COMMS_SEND_SATCOM, 'comms_sendSatcom'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        self.special_cases['comms_send_datalink'] = {
            'command_names': ['COMMS_SEND_DATALINK', 'comms_sendDatalink'],
            'message_types': [COMMS_SEND_DATALINK, 'comms_sendDatalink'],
            'destinations': ['comms'],
            'handler': 'comms_handler',
        }
        # Data update — comms pushing state to display
        self.special_cases['comms_data_update'] = {
            'command_names': ['COMMS_DATA_UPDATE', 'comms_dataUpdate'],
            'message_types': [COMMS_DATA_UPDATE, 'comms_dataUpdate'],
            'destinations': ['display'],
            'handler': 'comms_handler',
        }
        self.logger.info(f"Comms special cases registered ({len([k for k in self.special_cases if k.startswith('comms_')])})")

    def _initialize_mission_special_cases(self):
        """Routing rules for the Mission Planning system."""
        # Status request/response
        self.special_cases['mission_status_request'] = {
            'command_names': ['MISSION_STATUS_REQUEST', 'mission_statusRequest'],
            'message_types': [MISSION_STATUS_REQUEST, 'mission_statusRequest'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_status_response'] = {
            'command_names': ['MISSION_STATUS_RESPONSE', 'mission_statusResponse'],
            'message_types': [MISSION_STATUS_RESPONSE, 'mission_statusResponse'],
            'destinations': ['display'],
            'handler': 'mission_handler',
        }
        # Phase management
        self.special_cases['mission_phase_set'] = {
            'command_names': ['MISSION_PHASE_SET', 'mission_phaseSet'],
            'message_types': [MISSION_PHASE_SET, 'mission_phaseSet'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_phase_advance'] = {
            'command_names': ['MISSION_PHASE_ADVANCE', 'mission_phaseAdvance'],
            'message_types': [MISSION_PHASE_ADVANCE, 'mission_phaseAdvance'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        # Route management
        self.special_cases['mission_waypoint_add'] = {
            'command_names': ['MISSION_WAYPOINT_ADD', 'mission_waypointAdd'],
            'message_types': [MISSION_WAYPOINT_ADD, 'mission_waypointAdd'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_waypoint_remove'] = {
            'command_names': ['MISSION_WAYPOINT_REMOVE', 'mission_waypointRemove'],
            'message_types': [MISSION_WAYPOINT_REMOVE, 'mission_waypointRemove'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_route_optimise'] = {
            'command_names': ['MISSION_ROUTE_OPTIMISE', 'mission_routeOptimise'],
            'message_types': [MISSION_ROUTE_OPTIMISE, 'mission_routeOptimise'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        # Target lifecycle
        self.special_cases['mission_target_designate'] = {
            'command_names': ['MISSION_TARGET_DESIGNATE', 'mission_targetDesignate'],
            'message_types': [MISSION_TARGET_DESIGNATE, 'mission_targetDesignate'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_target_engage'] = {
            'command_names': ['MISSION_TARGET_ENGAGE', 'mission_targetEngage'],
            'message_types': [MISSION_TARGET_ENGAGE, 'mission_targetEngage'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_target_bda'] = {
            'command_names': ['MISSION_TARGET_BDA', 'mission_targetBDA'],
            'message_types': [MISSION_TARGET_BDA, 'mission_targetBDA'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_target_update'] = {
            'command_names': ['MISSION_TARGET_UPDATE', 'mission_targetUpdate'],
            'message_types': [MISSION_TARGET_UPDATE, 'mission_targetUpdate'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        # OOB management
        self.special_cases['mission_unit_add'] = {
            'command_names': ['MISSION_UNIT_ADD', 'mission_unitAdd'],
            'message_types': [MISSION_UNIT_ADD, 'mission_unitAdd'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_unit_update'] = {
            'command_names': ['MISSION_UNIT_UPDATE', 'mission_unitUpdate'],
            'message_types': [MISSION_UNIT_UPDATE, 'mission_unitUpdate'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        # Mission data
        self.special_cases['mission_objectives_set'] = {
            'command_names': ['MISSION_OBJECTIVES_SET', 'mission_objectivesSet'],
            'message_types': [MISSION_OBJECTIVES_SET, 'mission_objectivesSet'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_roe_set'] = {
            'command_names': ['MISSION_ROE_SET', 'mission_roeSet'],
            'message_types': [MISSION_ROE_SET, 'mission_roeSet'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        self.special_cases['mission_intel_update'] = {
            'command_names': ['MISSION_INTEL_UPDATE', 'mission_intelUpdate'],
            'message_types': [MISSION_INTEL_UPDATE, 'mission_intelUpdate'],
            'destinations': ['missionplanning'],
            'handler': 'mission_handler',
        }
        # Data update — mission pushing state to display / TSD
        self.special_cases['mission_data_update'] = {
            'command_names': ['MISSION_DATA_UPDATE', 'mission_dataUpdate'],
            'message_types': [MISSION_DATA_UPDATE, 'mission_dataUpdate'],
            'destinations': ['display'],
            'handler': 'mission_handler',
        }
        self.logger.info(f"Mission special cases registered ({len([k for k in self.special_cases if k.startswith('mission_')])})")

    def get_system_by_rt_address(self, rt_address):
        """Get system ID by RT address."""
        return self.rt_addresses.get(rt_address)

    def get_rt_address_by_system(self, system_id):
        """Get RT address by system ID."""
        system = self.systems.get(system_id)
        if system:
            return system['address']
        return None

    def get_subaddress(self, system_id, subaddress_id):
        """Get subaddress value by system ID and subaddress ID."""
        system = self.systems.get(system_id)
        if system and subaddress_id in system['subaddresses']:
            return system['subaddresses'][subaddress_id]
        return None

    def get_command_value(self, system_id, command_type):
        """Get command value by system ID and command type."""
        if system_id in self.command_types and command_type in self.command_types[system_id]:
            return self.command_types[system_id][command_type]
        return None

    def get_message_type_info(self, message_type):
        """Get message type information."""
        return self.message_types.get(message_type)

    def get_special_case(self, message_type):
        """Get special case routing rule by message type."""
        for case_id, case in self.special_cases.items():
            if message_type in case['message_types']:
                return case
        return None

    def is_special_case(self, message):
        """
        Check if a message is a special case that needs custom routing.

        Special cases are messages that don't follow the standard routing pattern
        based on RT address and subaddress.
        """
        # Normalize message_type access for different message formats
        message_type = None
        command_name = None

        # Extract message_type
        if isinstance(message, dict):
            message_type = message.get('message_type', '').lower()
            command_name = message.get('command_name', '')
        elif hasattr(message, 'message_type'):
            message_type = getattr(message, 'message_type', '').lower()
            command_name = getattr(message, 'command_name', '')

        # Check VIL indicators
        if (message_type and ('vil' in message_type or 'type_158' in message_type)) or \
           (command_name and 'VIL' in command_name):
            self.logger.debug(f"Detected VIL special case: {message_type or command_name}")
            return True

        # Check Precipitation indicators
        if (message_type and ('precip' in message_type or 'precipitation' in message_type or 'type_157' in message_type)) or \
           (command_name and ('PRECIP' in command_name or 'PRECIPITATION' in command_name)):
            self.logger.debug(f"Detected Precipitation special case: {message_type or command_name}")
            return True

        # Check mode change indicators
        if (message_type and ('mode' in message_type and ('change' in message_type or 'request' in message_type or 'response' in message_type))) or \
           (command_name and 'MODE_CHANGE' in command_name):
            self.logger.debug(f"Detected Mode Change special case: {message_type or command_name}")
            return True

        # Check FMS indicators
        if (message_type and ('fms' in message_type.lower() or 'flightmanagementsystem' in message_type.lower())) or \
           (command_name and ('FMS' in command_name or 'FLIGHT_MANAGEMENT' in command_name)):
            self.logger.debug(f"Detected FMS special case: {message_type or command_name}")
            return True

        # Standard check for message type against registered special cases
        if message_type:
            for case_id, case in self.special_cases.items():
                if any(msg_type.lower() == message_type for msg_type in case['message_types']):
                    self.logger.debug(f"Matched registered special case {case_id}: {message_type}")
                    return True

        # Standard check for command name against registered special cases
        if command_name:
            for case_id, case in self.special_cases.items():
                if 'command_names' in case and command_name in case['command_names']:
                    self.logger.debug(f"Matched registered special case {case_id} by command name: {command_name}")
                    return True

        return False

def get_routing_registry():
    """Get the singleton instance of RoutingRegistry."""
    return RoutingRegistry()
