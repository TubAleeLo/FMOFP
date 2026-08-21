"""
Burst version of the system-level test for combined precipitation and VIL data flow from weather radar to display.
"""

import asyncio
import sys
import logging
import io
import traceback
import time
import re
import uuid
from typing import List, Optional, Dict, Tuple

# Import setup environment
from FMOFP.Tests.setup_env import setup_environment
setup_environment()

from FMOFP.core.system_manager import get_system_manager
from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Interfaces.userInterface.messaging.interface_display_message_handler import get_interface_display_message_handler as get_display_message_handler
from FMOFP.local_messaging.messageConfigurations.weather_radar_data import (
    WeatherRadarVILData,
    PrecipitationData,
    weather_radarPrecipitationRequest,
    weather_radarPrecipitationResponse,
    weather_radarVILRequest,
    weather_radarVILResponse
)
from Systems.radarManagement.radar_enums import weather_radarMode

logger = get_logger()

class TestCombinedPrecipitationVILFlow:
    """System test for combined precipitation and VIL data flow from weather radar to display"""
    
    def __init__(self):
        """Initialize test using existing system infrastructure"""
        # Get system manager to access existing components
        self.system_manager = get_system_manager()
        
        # Get components from system manager
        self.radar_handler = self.system_manager.components.get('radar_message_handler')
        self.async_handler = self.system_manager.components.get('async_message_handler')
        self.display_handler = self.system_manager.components.get('display_message_handler')
        
        # Get message routing service
        from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
        self.routing_service = get_message_routing_service()
        
        # Setup logging capture
        self.log_capture = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture)
        self.log_handler.setLevel(logging.DEBUG)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add handlers
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        logger.logger.addHandler(self.log_handler)
        
        logger.info("Combined precipitation and VIL flow test initialized")

    async def initialize(self):
        """Verify system initialization"""
        try:
            logger.info("Verifying system initialization")
            
            # Verify required components
            if not all([self.radar_handler, self.async_handler, self.display_handler]):
                missing = [name for name, comp in {
                    'radar_message_handler': self.radar_handler,
                    'async_message_handler': self.async_handler,
                    'display_message_handler': self.display_handler
                }.items() if not comp]
                raise RuntimeError(f"Missing required components: {', '.join(missing)}")
            logger.info("Message handlers verified")
            
            # Verify AsyncMessageHandler is running
            if not (self.radar_handler.async_handler and self.radar_handler.async_handler.started):
                raise RuntimeError("RadarMessageHandler's AsyncMessageHandler is not properly initialized")
            logger.info("AsyncMessageHandler verified")
            
            # Verify routing service
            if not self.routing_service:
                raise RuntimeError("Message routing service not available")
            logger.info("Message routing service verified")
            
            logger.info("System initialization verification complete")
            
        except Exception as e:
            logger.error(f"Error during test initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def test_combined_data_flow(self) -> Tuple[bool, bool]:
        """Test combined precipitation and VIL data flow sending requests back-to-back"""
        try:
            
            # Create precipitation request
            logger.info("[TEST] Creating precipitation data request")
            precip_uuid = str(uuid.uuid4())
            precip_request = weather_radarPrecipitationRequest(
                message_header="data_request",
                sending_system="TestSystem",
                destination="weather_radar",
                request_uuid=precip_uuid,
                scan_parameters={"mode": "SURVEILLANCE"}
            )
            precip_request.command_type = "precipitation_data"
            precip_request.metadata = {
                "source": "precipitation_test",
                "data_type": "precipitation",
                "test_identifier": f"precip_test_{precip_uuid[-8:]}",
                "unified_router_test": True
            }
            
            # Create VIL request
            logger.info("[TEST] Creating VIL data request")
            vil_uuid = str(uuid.uuid4())
            vil_request = weather_radarVILRequest(
                message_header="data_request",
                sending_system="TestSystem",
                destination="weather_radar",
                request_uuid=vil_uuid,
                scan_parameters={"mode": "SURVEILLANCE"}
            )
            vil_request.command_type = "vil_data"
            vil_request.metadata = {
                "source": "vil_test",
                "data_type": "vil",
                "message_type": "weather_radarVILRequest",
                "test_identifier": f"vil_test_{vil_uuid[-8:]}",
                "unified_router_test": True
            }

            logger.info("Testing combined precipitation and VIL data flow...")
            
            # Clear logs
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Set the radar to SURVEILLANCE mode
            surveillance_mode = weather_radarMode.SURVEILLANCE
            logger.info("Setting weather radar to SURVEILLANCE mode")
            mode_request_id = await self.radar_handler.send_request(
                radar_name="weather_radar",
                request_type="mode_change",
                data=surveillance_mode
            )
            
            if not mode_request_id:
                raise AssertionError("Failed to get mode change request ID")
            time.sleep(1.5) 

           
            # # Send precipitation request
            # logger.info("[TEST] Sending precipitation data request")
            precip_request_id = await self.radar_handler.send_request(
            "weather_radar",  # Target system
            "data",          # Command type
            precip_request   # Send request object
            )
            # logger.info(f"[TEST] Precipitation request sent with ID: {precip_request_id}")
            
            # Wait minimally between requests
            await asyncio.sleep(0.01)
            
            # Send VIL request immediately after
            # NOTE (production readiness re-analysis, August 2026): the actual VIL
            # send below has been commented out since the initial commit (confirmed
            # via git history -- no prior version of this file ever had it enabled),
            # so despite this test's name and the VIL request object built above,
            # only the precipitation request is actually exercised. Left disabled
            # rather than guessing at why -- enabling it would be new test behavior,
            # not a verification fix, and could not be corroborated against any
            # documented intent. Tracked as a known limitation rather than "fixed."
            # logger.info("[TEST] Sending VIL data request")
            # vil_request_id = await self.radar_handler.send_request(
            # "weather_radar",  # Target system
            # "data",          # Command type
            # vil_request      # Send request object
            # )
            # logger.info(f"[TEST] VIL request sent with ID: {vil_request_id}")

            # NOTE (production readiness re-analysis, August 2026): this method's
            # success path previously had no explicit return here, so it fell off
            # the end and implicitly returned None despite its own `Tuple[bool, bool]`
            # return-type annotation -- and the caller (run_tests(), below) discarded
            # the return value entirely, so this false-y/None result was never even
            # inspected. Combined with userCLI.py's combined_precipitation_vil_flow_test()
            # also discarding run_tests()'s result and unconditionally logging "Test
            # completed successfully!", a user running this test via the CLI always
            # saw a success message regardless of what actually happened inside this
            # method. Now returns an explicit, meaningful result on the success path.
            # The second element is None (not False) to distinguish "VIL was never
            # exercised" from "VIL was exercised and failed" -- VIL send is disabled
            # above, so this method cannot honestly claim to have tested it either way.
            return precip_request_id is not None, None

        except Exception as e:
            logger.error(f"Error in combined data flow test: {str(e)}")
            traceback.print_exc()
            return False, None

    async def run_tests(self):
        """Run the combined precipitation and VIL flow test"""
        try:
            # Initialize system
            await self.initialize()

            precip_ok, vil_ok = await self.test_combined_data_flow()
            # vil_ok is intentionally excluded from overall_success: VIL send is
            # currently disabled in test_combined_data_flow() (see NOTE above), so
            # vil_ok is always None ("not exercised") rather than True/False, and a
            # not-exercised check must not silently count as a pass. Only the part
            # of the flow that's actually exercised (precip) determines the result.
            overall_success = bool(precip_ok)
            logger.info(
                f"Combined Precipitation/VIL Flow Test: "
                f"{'PASSED' if overall_success else 'FAILED'} "
                f"(precip_ok={precip_ok}, vil_ok={vil_ok} [VIL send currently disabled, not exercised])"
            )
            return overall_success

        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            traceback.print_exc()
            return False
        finally:
            # Clean up logging
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)
            logger.logger.removeHandler(self.log_handler)
            self.log_capture.close()

def test():
    """Function to be called from test runner"""
    test_instance = TestCombinedPrecipitationVILFlow()
    result = asyncio.run(test_instance.run_tests())
    return result

if __name__ == '__main__':
    # This test is designed to be run from the user CLI
    # It should not be run directly as it requires the system to be initialized
    logger.warning("This test should be run via the user CLI 'test' command")
    sys.exit(1)

# """
# System-level test for combined precipitation and VIL data flow from weather radar to display.
# Tests the automatic routing of both precipitation and VIL data through the complete message flow.

# This test first runs weather_radar_surveillance_mode_test.py to ensure the radar is in SURVEILLANCE mode.
# Then it sends the precipitation data request, waits 5 seconds, and then sends the VIL data request.
# """

# import asyncio
# import sys
# import logging
# import io
# import traceback
# import time
# import re
# import uuid
# from typing import List, Optional, Dict, Tuple

# # Import setup environment
# from FMOFP.Tests.setup_env import setup_environment
# setup_environment()

# from FMOFP.core.system_manager import get_system_manager
# from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
# from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
# from FMOFP.Utils.logger.sys_logger import get_logger
# from FMOFP.Interfaces.userInterface.messaging.interface_display_message_handler import get_interface_display_message_handler as get_display_message_handler
# from FMOFP.local_messaging.messageConfigurations.weather_radar_data import (
#     WeatherRadarVILData,
#     PrecipitationData,
#     weather_radarPrecipitationRequest,
#     weather_radarPrecipitationResponse,
#     weather_radarVILRequest,
#     weather_radarVILResponse
# )
# from Systems.radarManagement.radar_enums import weather_radarMode

# logger = get_logger()

# class TestCombinedPrecipitationVILFlow:
#     """System test for combined precipitation and VIL data flow from weather radar to display"""
    
#     def __init__(self):
#         """Initialize test using existing system infrastructure"""
#         # Get system manager to access existing components
#         self.system_manager = get_system_manager()
        
#         # Get components from system manager
#         self.radar_handler = self.system_manager.components.get('radar_message_handler')
#         self.async_handler = self.system_manager.components.get('async_message_handler')
#         self.display_handler = self.system_manager.components.get('display_message_handler')
        
#         # Get message routing service
#         from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
#         self.routing_service = get_message_routing_service()
        
#         # Setup logging capture
#         self.log_capture = io.StringIO()
#         self.log_handler = logging.StreamHandler(self.log_capture)
#         self.log_handler.setLevel(logging.DEBUG)
#         self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
#         # Add handlers
#         root_logger = logging.getLogger()
#         root_logger.addHandler(self.log_handler)
#         logger.logger.addHandler(self.log_handler)
        
#         logger.info("Combined precipitation and VIL flow test initialized")

#     async def initialize(self):
#         """Verify system initialization"""
#         try:
#             logger.info("Verifying system initialization")
            
#             # Verify required components
#             if not all([self.radar_handler, self.async_handler, self.display_handler]):
#                 missing = [name for name, comp in {
#                     'radar_message_handler': self.radar_handler,
#                     'async_message_handler': self.async_handler,
#                     'display_message_handler': self.display_handler
#                 }.items() if not comp]
#                 raise RuntimeError(f"Missing required components: {', '.join(missing)}")
#             logger.info("Message handlers verified")
            
#             # Verify AsyncMessageHandler is running
#             if not (self.radar_handler.async_handler and self.radar_handler.async_handler.started):
#                 raise RuntimeError("RadarMessageHandler's AsyncMessageHandler is not properly initialized")
#             logger.info("AsyncMessageHandler verified")
            
#             # Verify routing service
#             if not self.routing_service:
#                 raise RuntimeError("Message routing service not available")
#             logger.info("Message routing service verified")
            
#             logger.info("System initialization verification complete")
            
#         except Exception as e:
#             logger.error(f"Error during test initialization: {str(e)}")
#             logger.error(traceback.format_exc())
#             raise

#     def _verify_precipitation_flow(self, log_output: str) -> Tuple[bool, List[str]]:
#         """Verify precipitation data flow in logs"""
#         missing_patterns = []
        
#         # Add debug logging
#         logger.info(f"[VERIFY] Checking precipitation data flow")
#         logger.info(f"[VERIFY] Log capture content length: {len(log_output)}")
#         logger.info("[VERIFY] Last 500 characters of log:")
#         logger.info(log_output[-500:] if len(log_output) > 500 else log_output)
        
#         # Define patterns to check for complete precipitation data flow
#         patterns = [
              
#             #  Precipitation Data Processing - Support both original and new patterns
#             (r"\[PRECIP_FLOW\]|\[LOC_PRECIP_RPNS_SERV_PRECIP_FLOW\]", 
#                 "Precipitation response service handling data"),
#             (r"(Processing precipitation data|Precipitation data being stored)", 
#                 "Precipitation data extracted from response"),
#             (r"\[PRECIP_STORE\] Storing data|\[PRECIP_RSPNS_SERV_STORE\] Storing data", 
#                 "Precipitation data being stored"),
                
                
#             #  Display Processing - Support both original and new patterns
#             (r"\[DISPLAY_HANDLER\] Message enqueued:|\[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW\]", 
#                 "Display handler received precipitation data"),
#             (r"\[WEATHER_DISPLAY\] Processing precipitation data|\[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW\] DisplayMessageHandler received precipitation data", 
#                 "Display processing precipitation data"),
#             (r"\[WEATHER_DISPLAY\] Stored \d+ precipitation data points|\[LOCAL_DISP_MSG_HDR_PRECIPITATION_FLOW\] Completed precipitation data handling", 
#                 "Display stored precipitation data"),
                
#             #  New Unified Router Patterns (at least one of these should be present)
#             (r"\[UNIFIED ROUTER\]|\[PRECIP_HANDLER\]|\[ROUTE\]", 
#                 "Message routed through unified router"),
                
#             # UUID Preservation Checks (critical for message tracking)
#             (r"request_uuid.*?request_id|request_id.*?request_uuid|message_uuid.*?preserved", 
#                 "UUID preservation between systems"),
#             (r"command_name.*?PRECIPITATION|PRECIPITATION.*?command_name", 
#                 "Command name preserved in message flow"),
#             (r"metadata.*?request_uuid|metadata.*?command_name", 
#                 "Metadata preservation in message flow")
#         ]
        
#         for pattern, desc in patterns:
#             if not re.search(pattern, log_output, re.IGNORECASE):
#                 logger.error(f"[VERIFY] Missing {desc}")
#                 missing_patterns.append(desc)
#             else:
#                 logger.info(f"[VERIFY] Found {desc}")
        
#         success = len(missing_patterns) == 0
#         logger.info(f"[VERIFY] Verification {'succeeded' if success else 'failed'}")
#         if not success:
#             logger.error(f"[VERIFY] Missing patterns: {missing_patterns}")
        
#         return success, missing_patterns
            
#     def _verify_vil_flow(self, log_output: str) -> Tuple[bool, List[str]]:
#         """Verify VIL data flow in logs"""
#         missing_patterns = []
        
#         # Add debug logging
#         logger.info(f"[VERIFY] Checking VIL data flow")
#         logger.info(f"[VERIFY] Log capture content length: {len(log_output)}")
#         logger.info("[VERIFY] Last 500 characters of log:")
#         logger.info(log_output[-500:] if len(log_output) > 500 else log_output)
        
#         # Define patterns to check for complete VIL data flow - support multiple patterns
#         patterns = [
#             # VIL Data Processing Patterns
#             (r"\[VIL_FLOW\]|\[LOC_VIL_RPNS_SERV_VIL_FLOW\]|\[WEATHER\] Identified VIL message from", 
#                 "VIL response service handling data"),
#             (r"Processing VIL data|\[WEATHER\] Routing VIL data", 
#                 "VIL data identified and processed"),
#             (r"\[VIL\] Routed VIL data|\[VIL_RSPNS_SERV_STORE\]|\[VIL\] Sent status word acknowledgment", 
#                 "VIL data properly routed and acknowledged"),
            
#             # Display Processing Patterns
#             (r"\[DISPLAY_HANDLER\]|\[LOCAL_DISP_MSG_HDR_VIL_FLOW\]|\[WEATHER_DISPLAY\] Retrieved", 
#                 "Display handler received VIL data"),
#             (r"\[WEATHER_DISPLAY\].*drawn_vil_count|\[LOCAL_DISP_MSG_HDR_VIL_FLOW\]|\[WEATHER_DISPLAY\] Drawing VIL", 
#                 "Display node updating with VIL data"),
            
#             # Unified Router or Message Routing Patterns
#             (r"\[UNIFIED ROUTER\]|\[ROUTE\]|\[MSG_Q_MGR\]|\[VIL_HANDLER\]", 
#                 "Message routed through unified router")
#         ]
        
#         for pattern, desc in patterns:
#             if not re.search(pattern, log_output, re.IGNORECASE):
#                 logger.error(f"[VERIFY] Missing {desc}")
#                 missing_patterns.append(desc)
#             else:
#                 logger.info(f"[VERIFY] Found {desc}")
        
#         success = len(missing_patterns) == 0
#         logger.info(f"[VERIFY] Verification {'succeeded' if success else 'failed'}")
#         if not success:
#             logger.error(f"[VERIFY] Missing patterns: {missing_patterns}")
        
#         return success, missing_patterns

#     async def setup_prerequisites(self) -> bool:
#         """Run prerequisite tests to ensure proper environment setup"""
#         try:

#             # Set the radar to SURVEILLANCE mode
#             surveillance_mode = weather_radarMode.SURVEILLANCE
#             logger.info("Setting weather radar to SURVEILLANCE mode")
#             mode_request_id = await self.radar_handler.send_request(
#                 radar_name="weather_radar",
#                 request_type="mode_change",
#                 data=surveillance_mode
#             )
#             time.sleep(5.0) 
#             if not mode_request_id:
#                 raise AssertionError(f"Failed to get mode change request ID")
                
#             logger.info(f"Prerequisites successfully set up; mode change request ID: {mode_request_id}")
#             return True
            
#         except Exception as e:
#             logger.error(f"Error setting up prerequisites: {str(e)}")
#             traceback.print_exc()
#             return False

#     async def test_precipitation_data_flow(self) -> bool:
#         """Test precipitation data flow from weather radar to display"""
#         try:
#             logger.info("Testing precipitation data flow...")
            
#             # Clear logs
#             self.log_capture.seek(0)
#             self.log_capture.truncate()
            
#             # Create a precipitation data request for unified router compatibility
#             logger.info("[TEST POINT] Creating precipitation data request")
#             test_uuid = str(uuid.uuid4())
#             # Create request with standard parameters only
#             precip_request = weather_radarPrecipitationRequest(
#                 message_header="data_request",
#                 sending_system="TestSystem",
#                 destination="weather_radar",
#                 request_uuid=test_uuid,
#                 scan_parameters={"mode": "SURVEILLANCE"}
#             )
            
#             # Add command_type after creation - this is needed by the unified router
#             # but not part of the original message constructor
#             precip_request.command_type = "precipitation_data"
            
#             # Add enhanced metadata to help with routing
#             try:
#                 precip_request.metadata = {
#                     "source": "precipitation_test",
#                     "data_type": "precipitation",
#                     "test_identifier": f"precip_test_{test_uuid[-8:]}",
#                     "unified_router_test": True
#                 }
#                 logger.info(f"Added metadata for unified router routing: {precip_request.metadata}")
#             except Exception as metadata_error:
#                 logger.warning(f"Could not add metadata to precipitation request: {metadata_error}")
            
#             # Send precipitation data request to weather radar
#             logger.info("Sending precipitation data request to weather radar")
#             request_id = await self.radar_handler.send_request(
#                "weather_radar",  # Target system
#                "data",          # Command type
#                precip_request      # Send request object
#             )
            
#             logger.info(f"[TEST] Precipitation data request sent with ID: {request_id}")
            
#             # Wait for precipitation request
#             time.sleep(3.0)
            
#             if not request_id:
#                raise AssertionError("Failed to get request ID")
            
#             # Wait for processing and verify
#             max_retries = 3
#             retry_delay = 1.0
#             success = False
            
#             # Initial wait for processing - increased for unified router path
#             for attempt in range(max_retries):
#                 logger.info(f"[TEST] Verification attempt {attempt + 1}/{max_retries}")
#                 await asyncio.sleep(3.0)  # Increased wait between retries
#                 # Get logs
#                 log_output = self.log_capture.getvalue()
#                 logger.info(f"[TEST] Log capture size: {len(log_output)} bytes")
                
#                 # Verify precipitation data flow
#                 success, missing_patterns = self._verify_precipitation_flow(log_output)
#                 if success:
#                     logger.info(f"[TEST] Verification succeeded on attempt {attempt + 1}")
#                     break
#                 else:
#                     logger.info(f"[TEST] Verification failed on attempt {attempt + 1}")
#                     if attempt < max_retries - 1:
#                         logger.info(f"[TEST] Retrying in {retry_delay} seconds...")
#                         time.sleep(retry_delay)
            
#             if not success:
#                 missing = "\n".join(f"- {p}" for p in missing_patterns)
#                 raise AssertionError(
#                     f"Precipitation data flow verification failed:\n{missing}"
#                 )
            
#             logger.info("Precipitation data flow test completed successfully")
#             return True
            
#         except Exception as e:
#             logger.error(f"Error in precipitation data flow test: {str(e)}")
#             traceback.print_exc()
#             return False
            
#     async def test_vil_data_flow(self) -> bool:
#         """Test VIL data flow from weather radar to display"""
#         try:
#             logger.info("Testing VIL data flow...")
            
#             # Clear logs
#             self.log_capture.seek(0)
#             self.log_capture.truncate()
            
#             # Create a VIL data request for unified router compatibility
#             logger.info("[TEST POINT] Creating VIL data request")
#             test_uuid = str(uuid.uuid4())
#             # Create request with standard parameters
#             vil_request = weather_radarVILRequest(
#                 message_header="data_request",
#                 sending_system="TestSystem",
#                 destination="weather_radar",
#                 request_uuid=test_uuid,
#                 scan_parameters={"mode": "SURVEILLANCE"}
#             )
            
#             # Add command_type after creation - this is needed by the unified router
#             # but not part of the original message constructor
#             vil_request.command_type = "vil_data"
            
#             # Add enhanced metadata to help with routing
#             try:
#                 vil_request.metadata = {
#                     "source": "vil_test",
#                     "data_type": "vil",
#                     "message_type": "weather_radarVILRequest",
#                     "test_identifier": f"vil_test_{test_uuid[-8:]}",
#                     "unified_router_test": True
#                 }
#                 logger.info(f"Added metadata for unified router routing: {vil_request.metadata}")
#             except Exception as metadata_error:
#                 logger.warning(f"Could not add metadata to VIL request: {metadata_error}")
            
#             # Send VIL data request to weather radar
#             logger.info("Sending VIL data request to weather radar")
#             request_id = await self.radar_handler.send_request(
#                "weather_radar",  # Target system
#                "data",          # Command type
#                vil_request      # Send request object
#             )
            
#             logger.info(f"VIL data request sent with ID: {request_id}")
            
#             # Wait for VIL request processing
#             time.sleep(3.0)
            
#             if not request_id:
#                raise AssertionError("Failed to get request ID")
            
#             # Wait for processing and verify
#             max_retries = 3
#             retry_delay = 2.0
#             success = False
            
#             # Initial wait for processing - increased for unified router path
#             for attempt in range(max_retries):
#                 logger.info(f"[TEST] Verification attempt {attempt + 1}/{max_retries}")
#                 await asyncio.sleep(3.0)  # Increased wait between retries
#                 # Get logs
#                 log_output = self.log_capture.getvalue()
#                 logger.info(f"[TEST] Log capture size: {len(log_output)} bytes")
                
#                 # Verify VIL data flow
#                 success, missing_patterns = self._verify_vil_flow(log_output)
#                 if success:
#                     logger.info(f"[TEST] Verification succeeded on attempt {attempt + 1}")
#                     break
#                 else:
#                     logger.info(f"[TEST] Verification failed on attempt {attempt + 1}")
#                     if attempt < max_retries - 1:
#                         logger.info(f"[TEST] Retrying in {retry_delay} seconds...")
#                         time.sleep(retry_delay)
            
#             if not success:
#                 missing = "\n".join(f"- {p}" for p in missing_patterns)
#                 raise AssertionError(
#                     f"VIL data flow verification failed:\n{missing}"
#                 )
            
#             logger.info("VIL data flow test completed successfully")
#             return True
            
#         except Exception as e:
#             logger.error(f"Error in VIL data flow test: {str(e)}")
#             traceback.print_exc()
#             return False

#     async def run_tests(self):
#         """Run the combined precipitation and VIL flow test"""
#         try:
#             # Initialize system
#             await self.initialize()
            
#             # Run prerequisite tests first - set radar to SURVEILLANCE mode
#             logger.info("=== Step 1: Setting radar to SURVEILLANCE mode ===")
#             prereq_success = await self.setup_prerequisites()
#             if not prereq_success:
#                 logger.error("Prerequisites failed - cannot run combined flow test")
#                 return False
            
#             # Wait 5 seconds between steps
#             logger.info("Waiting 5 seconds...")
#             time.sleep(5.0)
            
#             # Run precipitation data flow test
#             logger.info("=== Step 2: Testing precipitation data flow ===")
#             precip_flow_test = await self.test_precipitation_data_flow()
#             if not precip_flow_test:
#                 logger.error("Precipitation data flow test failed - stopping tests")
#                 return False
                
#             # Wait 5 seconds between tests
#             logger.info("Waiting 5 seconds...")
#             time.sleep(5.0)
            
#             # Run VIL data flow test
#             logger.info("=== Step 3: Testing VIL data flow ===")
#             vil_flow_test = await self.test_vil_data_flow()
            
#             # Report results
#             logger.info("\nTest Results:")
#             logger.info(f"Prerequisites: {'PASSED' if prereq_success else 'FAILED'}")
#             logger.info(f"Precipitation Data Flow Test: {'PASSED' if precip_flow_test else 'FAILED'}")
#             logger.info(f"VIL Data Flow Test: {'PASSED' if vil_flow_test else 'FAILED'}")
            
#             # Display expectations
#             logger.info("\nExpected Combined Flow:")
#             logger.info("1. Weather radar set to SURVEILLANCE mode")
#             logger.info("2. Precipitation data flow from radar to display")
#             logger.info("3. VIL data flow from radar to display")
            
#             return prereq_success and precip_flow_test and vil_flow_test
            
#         except Exception as e:
#             logger.error(f"Error running tests: {e}")
#             traceback.print_exc()
#             return False
#         finally:
#             # Clean up logging
#             root_logger = logging.getLogger()
#             root_logger.removeHandler(self.log_handler)
#             logger.logger.removeHandler(self.log_handler)
#             self.log_capture.close()

# def test():
#     """Function to be called from test runner"""
#     test_instance = TestCombinedPrecipitationVILFlow()
#     result = asyncio.run(test_instance.run_tests())
#     return result

# if __name__ == '__main__':
#     # This test is designed to be run from the user CLI
#     # It should not be run directly as it requires the system to be initialized
#     logger.warning("This test should be run via the user CLI 'test' command")
#     sys.exit(1)
