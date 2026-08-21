"""
Comprehensive test for all predefined message types in the FMOFP system.
Tests all message systems: Weather Radar, TFR, SAR, Targeting, AEWC, FMS, and FCS.
"""

import asyncio
import sys
import logging
import io
import traceback
import time
import re
import uuid
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Import setup environment
from FMOFP.Tests.setup_env import setup_environment
setup_environment()

from FMOFP.core.system_manager import get_system_manager
from FMOFP.local_messaging.routing.handlers.system_message_handlers.DisplayMessageHandler import get_display_message_handler
from FMOFP.local_messaging.radar_display_modes import RadarDisplayMode
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Interfaces.predefinedMessages.Messages import Messages, get_messages
from FMOFP.Interfaces.predefinedMessages.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode
)

logger = get_logger()

class PredefinedMessagesTest:
    """Comprehensive test for all predefined message types"""
    
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
        
        # Initialize Messages class which contains all predefined messages
        self.messages = Messages()
        
        # Initialize the message objects immediately
        asyncio.create_task(self.initialize_message_classes())
        
        # Test results collection
        self.results = {
            "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": None,
            "tests": [],
            "summary": {
                "total": 0,
                "success": 0,
                "failure": 0
            }
        }
        
        # Setup logging capture
        self.log_capture = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture)
        self.log_handler.setLevel(logging.DEBUG)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add handlers
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        logger.logger.addHandler(self.log_handler)
        
        logger.info("Predefined messages test initialized")
        
        # Set wait times between operations (in seconds)
        self.SHORT_WAIT = 0.5   # Wait between each message in a test group
        self.MEDIUM_WAIT = 1.0  # Wait after mode changes to ensure mode is active
        self.LONG_WAIT = 2.0    # Wait between test groups to ensure no message overlap

    async def initialize_message_classes(self):
        """Initialize message class instances"""
        try:
            # Initialize the Messages object
            await self.messages.initialize()
            logger.info("Message classes initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize message classes: {str(e)}")
            logger.error(traceback.format_exc())
            raise
            
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

    def _record_test_result(self, test_name: str, success: bool, request_id: str = None, error: str = None):
        """Record a test result"""
        self.results["tests"].append({
            "name": test_name,
            "success": success,
            "request_id": request_id,
            "error": error,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Update summary
        self.results["summary"]["total"] += 1
        if success:
            self.results["summary"]["success"] += 1
        else:
            self.results["summary"]["failure"] += 1

    def _verify_log_patterns(self, test_name: str, log_output: str, patterns: List[Tuple[str, str]]) -> Tuple[bool, List[str]]:
        """Verify log patterns for a test"""
        missing_patterns = []
        
        logger.info(f"[VERIFY] Checking {test_name} test patterns")
        
        for pattern, desc in patterns:
            if not re.search(pattern, log_output, re.IGNORECASE):
                logger.error(f"[VERIFY] Missing {desc}")
                missing_patterns.append(desc)
            else:
                logger.info(f"[VERIFY] Found {desc}")
        
        success = len(missing_patterns) == 0
        logger.info(f"[VERIFY] {test_name} verification {'succeeded' if success else 'failed'}")
        
        return success, missing_patterns

    async def test_weather_radar_messages(self):
        """Test all Weather Radar predefined messages"""
        try:
            logger.info("=== Testing Weather Radar Messages ===")
            
            # 1. Test Weather Radar mode change to SURVEILLANCE
            logger.info("[TEST] Weather Radar to SURVEILLANCE mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.weather_radar.weather_radar_to_surveillance_mode()
                logger.info(f"[TEST] Mode change request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                success = True
                self._record_test_result(
                    "weather_radar_to_surveillance_mode",
                    success=success,
                    request_id=request_id
                )
                
                # Wait for mode change to take effect - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in mode change test: {str(e)}")
                self._record_test_result(
                    "weather_radar_to_surveillance_mode",
                    success=False,
                    error=str(e)
                )
            
            # # 2. Test Weather Radar precipitation data request
            # logger.info("[TEST] Weather Radar precipitation data request")
            # self.log_capture.seek(0)
            # self.log_capture.truncate()
            
            # try:
            #     request_id = await self.messages.weather_radar.request_precipitation_data()
            #     logger.info(f"[TEST] Precipitation data request sent with ID: {request_id}")
                
            #     if not request_id:
            #         raise ValueError("Failed to get request ID")
                
            #     # Wait for data processing - use SHORT_WAIT
            #     await asyncio.sleep(self.SHORT_WAIT)
                
            #     # Verify logs for precipitation data processing
            #     log_output = self.log_capture.getvalue()
            #     patterns = [
            #         (r"Precipitation data|PRECIP", "Precipitation data processing"),
            #         (r"stored|processing", "Data storage or processing")
            #     ]
            #     success, missing = self._verify_log_patterns("precipitation_data", log_output, patterns)
                
            #     self._record_test_result(
            #         "request_precipitation_data",
            #         success=success,
            #         request_id=request_id,
            #         error=None if success else f"Missing log patterns: {', '.join(missing)}"
            #     )
                
            #     # Wait before next test - use MEDIUM_WAIT
            #     await asyncio.sleep(self.MEDIUM_WAIT)
                
            # except Exception as e:
            #     logger.error(f"[TEST] Error in precipitation data test: {str(e)}")
            #     self._record_test_result(
            #         "request_precipitation_data",
            #         success=False,
            #         error=str(e)
            #     )
            
            # # 3. Test Weather Radar VIL data request
            # logger.info("[TEST] Weather Radar VIL data request")
            # self.log_capture.seek(0)
            # self.log_capture.truncate()
            
            # try:
            #     request_id = await self.messages.weather_radar.request_vil_data()
            #     logger.info(f"[TEST] VIL data request sent with ID: {request_id}")
                
            #     if not request_id:
            #         raise ValueError("Failed to get request ID")
                
            #     # Wait for data processing - use SHORT_WAIT
            #     await asyncio.sleep(self.SHORT_WAIT)
                
            #     # Verify logs for VIL data processing
            #     log_output = self.log_capture.getvalue()
            #     patterns = [
            #         (r"VIL data|vil|vertex", "VIL data processing"),
            #         (r"stored|processing", "Data storage or processing")
            #     ]
            #     success, missing = self._verify_log_patterns("vil_data", log_output, patterns)
                
            #     self._record_test_result(
            #         "request_vil_data",
            #         success=success,
            #         request_id=request_id,
            #         error=None if success else f"Missing log patterns: {', '.join(missing)}"
            #     )
                
            #     # Wait before next test section - use LONG_WAIT
            #     await asyncio.sleep(self.LONG_WAIT)
                
            # except Exception as e:
            #     logger.error(f"[TEST] Error in VIL data test: {str(e)}")
            #     self._record_test_result(
            #         "request_vil_data",
            #         success=False,
            #         error=str(e)
            #     )
            
            logger.info("=== Weather Radar Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in weather radar message tests: {str(e)}")
            traceback.print_exc()
            
    async def test_tfr_radar_messages(self):
        """Test all TFR Radar predefined messages"""
        try:
            logger.info("=== Testing TFR Radar Messages ===")
            
            # 1. Test TFR Radar mode change to ACTIVE
            logger.info("[TEST] TFR Radar to ACTIVE mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.tfr_radar.tfr_radar_to_active_mode()
                logger.info(f"[TEST] Mode change request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                success = True
                self._record_test_result(
                    "tfr_radar_to_active_mode",
                    success=success,
                    request_id=request_id
                )
                
                # Wait for mode change to take effect - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in mode change test: {str(e)}")
                self._record_test_result(
                    "tfr_radar_to_active_mode",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test TFR Radar elevation data request
            logger.info("[TEST] TFR Radar elevation data request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.tfr_radar.request_elevation_data()
                logger.info(f"[TEST] Elevation data request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for elevation data processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"Elevation|tfr_radar|terrain", "TFR elevation data processing"),
                    (r"profile|data", "Profile data handling")
                ]
                success, missing = self._verify_log_patterns("elevation_data", log_output, patterns)
                
                self._record_test_result(
                    "request_elevation_data",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test section - use LONG_WAIT
                await asyncio.sleep(self.LONG_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in elevation data test: {str(e)}")
                self._record_test_result(
                    "request_elevation_data",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== TFR Radar Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in TFR radar message tests: {str(e)}")
            traceback.print_exc()

    async def test_sar_radar_messages(self):
        """Test all SAR Radar predefined messages"""
        try:
            logger.info("=== Testing SAR Radar Messages ===")
            
            # 1. Test SAR Radar mode change to STRIPMAP
            logger.info("[TEST] SAR Radar to STRIPMAP mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.sar_radar.sar_radar_to_stripmap_mode()
                logger.info(f"[TEST] Mode change request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                success = True
                self._record_test_result(
                    "sar_radar_to_stripmap_mode",
                    success=success,
                    request_id=request_id
                )
                
                # Wait for mode change to take effect - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in mode change test: {str(e)}")
                self._record_test_result(
                    "sar_radar_to_stripmap_mode",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test SAR Radar imagery data request
            logger.info("[TEST] SAR Radar imagery data request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.sar_radar.request_imagery_data()
                logger.info(f"[TEST] Imagery data request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for imagery data processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"Imagery|sar_radar|image", "SAR imagery data processing"),
                    (r"SAR|sar", "SAR radar handling")
                ]
                success, missing = self._verify_log_patterns("imagery_data", log_output, patterns)
                
                self._record_test_result(
                    "request_imagery_data",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test section - use LONG_WAIT
                await asyncio.sleep(self.LONG_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in imagery data test: {str(e)}")
                self._record_test_result(
                    "request_imagery_data",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== SAR Radar Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in SAR radar message tests: {str(e)}")
            traceback.print_exc()

    async def test_targeting_radar_messages(self):
        """Test all Targeting Radar predefined messages"""
        try:
            logger.info("=== Testing Targeting Radar Messages ===")
            
            # 1. Test Targeting Radar mode change to TRACKING
            logger.info("[TEST] Targeting Radar to TRACKING mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.targeting_radar.targeting_radar_to_tracking_mode()
                logger.info(f"[TEST] Mode change request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                success = True
                self._record_test_result(
                    "targeting_radar_to_tracking_mode",
                    success=success,
                    request_id=request_id
                )
                
                # Wait for mode change to take effect - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in mode change test: {str(e)}")
                self._record_test_result(
                    "targeting_radar_to_tracking_mode",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test Targeting Radar track data request
            logger.info("[TEST] Targeting Radar track data request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.targeting_radar.request_track_data()
                logger.info(f"[TEST] Track data request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for track data processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"Track|targeting_radar|target", "Targeting track data processing"),
                    (r"position|velocity", "Track position/velocity handling")
                ]
                success, missing = self._verify_log_patterns("track_data", log_output, patterns)
                
                self._record_test_result(
                    "request_track_data",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test section - use LONG_WAIT
                await asyncio.sleep(self.LONG_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in track data test: {str(e)}")
                self._record_test_result(
                    "request_track_data",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== Targeting Radar Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in targeting radar message tests: {str(e)}")
            traceback.print_exc()

    async def test_aewc_radar_messages(self):
        """Test all AEWC Radar predefined messages"""
        try:
            logger.info("=== Testing AEWC Radar Messages ===")
            
            # 1. Test AEWC Radar mode change to SURVEILLANCE
            logger.info("[TEST] AEWC Radar to SURVEILLANCE mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.aewc_radar.aewc_radar_to_surveillance_mode()
                logger.info(f"[TEST] Mode change request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                success = True
                self._record_test_result(
                    "aewc_radar_to_surveillance_mode",
                    success=success,
                    request_id=request_id
                )
                
                # Wait for mode change to take effect - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in mode change test: {str(e)}")
                self._record_test_result(
                    "aewc_radar_to_surveillance_mode",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test AEWC Radar sector scan request
            logger.info("[TEST] AEWC Radar sector scan request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.aewc_radar.request_sector_scan()
                logger.info(f"[TEST] Sector scan request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for sector scan processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"Sector|aewc_radar|scan", "AEWC sector scan processing"),
                    (r"surveillance|tracking", "Surveillance/tracking handling")
                ]
                success, missing = self._verify_log_patterns("sector_scan", log_output, patterns)
                
                self._record_test_result(
                    "request_sector_scan",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test section - use LONG_WAIT
                await asyncio.sleep(self.LONG_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in sector scan test: {str(e)}")
                self._record_test_result(
                    "request_sector_scan",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== AEWC Radar Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in AEWC radar message tests: {str(e)}")
            traceback.print_exc()

    async def test_fms_messages(self):
        """Test all FMS predefined messages"""
        try:
            logger.info("=== Testing FMS Messages ===")
            
            # 1. Test FMS status request
            logger.info("[TEST] FMS status request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.fms.request_status()
                logger.info(f"[TEST] Status request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for status processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for status processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"FMS|fms|flight", "FMS status processing"),
                    (r"status|state", "Status data handling")
                ]
                success, missing = self._verify_log_patterns("fms_status", log_output, patterns)
                
                self._record_test_result(
                    "fms_request_status",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait between FMS tests - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in FMS status test: {str(e)}")
                self._record_test_result(
                    "fms_request_status",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test FMS attitude update
            logger.info("[TEST] FMS attitude update")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                # Sample attitude data
                attitude_data = {
                    "roll": 5.0,
                    "pitch": 2.5,
                    "yaw": 180.0
                }
                
                request_id = await self.messages.fms.update_attitude(attitude_data)
                logger.info(f"[TEST] Attitude update request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for update processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for attitude update processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"attitude|orientation", "Attitude data processing"),
                    (r"roll|pitch|yaw", "Attitude parameters")
                ]
                success, missing = self._verify_log_patterns("fms_attitude", log_output, patterns)
                
                self._record_test_result(
                    "fms_update_attitude",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait between FMS tests - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in FMS attitude test: {str(e)}")
                self._record_test_result(
                    "fms_update_attitude",
                    success=False,
                    error=str(e)
                )
            
            # 3. Test FMS navigation update
            logger.info("[TEST] FMS navigation update")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                # Sample navigation data
                nav_data = {
                    "latitude": 35.12345,
                    "longitude": -120.98765,
                    "altitude": 30000,
                    "heading": 270.0
                }
                
                request_id = await self.messages.fms.update_navigation(nav_data)
                logger.info(f"[TEST] Navigation update request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for update processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for navigation update processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"navigation|position", "Navigation data processing"),
                    (r"latitude|longitude|altitude", "Navigation parameters")
                ]
                success, missing = self._verify_log_patterns("fms_navigation", log_output, patterns)
                
                self._record_test_result(
                    "fms_update_navigation",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test section - use LONG_WAIT
                await asyncio.sleep(self.LONG_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in FMS navigation test: {str(e)}")
                self._record_test_result(
                    "fms_update_navigation",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== FMS Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in FMS message tests: {str(e)}")
            traceback.print_exc()

    async def test_fcs_messages(self):
        """Test all FCS predefined messages"""
        try:
            logger.info("=== Testing FCS Messages ===")
            
            # 1. Test FCS control surface request
            logger.info("[TEST] FCS control surface request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                # Aileron control command
                request_id = await self.messages.fcs.request_control_surface_change(
                    surface_name="aileron",
                    position=15.0,
                    rate=5.0
                )
                logger.info(f"[TEST] Control surface request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for command processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for control surface command processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"control|surface|aileron", "Control surface command processing"),
                    (r"position|rate", "Control parameters")
                ]
                success, missing = self._verify_log_patterns("fcs_control", log_output, patterns)
                
                self._record_test_result(
                    "fcs_control_surface_change",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait between FCS tests - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in FCS control surface test: {str(e)}")
                self._record_test_result(
                    "fcs_control_surface_change",
                    success=False,
                    error=str(e)
                )
            
            # 2. Test FCS flight mode request
            logger.info("[TEST] FCS flight mode request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                # Flight mode change to approach
                mode_params = {
                    "flaps": 30,
                    "gear": "down"
                }
                
                request_id = await self.messages.fcs.request_flight_mode_change(
                    mode_name="approach",
                    mode_params=mode_params
                )
                logger.info(f"[TEST] Flight mode request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for command processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for flight mode command processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"mode|approach", "Flight mode command processing"),
                    (r"flaps|gear", "Mode parameters")
                ]
                success, missing = self._verify_log_patterns("fcs_mode", log_output, patterns)
                
                self._record_test_result(
                    "fcs_flight_mode_change",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait between FCS tests - use MEDIUM_WAIT
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST] Error in FCS flight mode test: {str(e)}")
                self._record_test_result(
                    "fcs_flight_mode_change",
                    success=False,
                    error=str(e)
                )
            
            # 3. Test FCS autopilot request
            logger.info("[TEST] FCS autopilot request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                # Autopilot altitude hold command
                request_id = await self.messages.fcs.request_autopilot_command(
                    command="altitude_hold",
                    target=35000
                )
                logger.info(f"[TEST] Autopilot request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for command processing - use SHORT_WAIT
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for autopilot command processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"autopilot|altitude", "Autopilot command processing"),
                    (r"target|hold", "Autopilot parameters")
                ]
                success, missing = self._verify_log_patterns("fcs_autopilot", log_output, patterns)
                
                self._record_test_result(
                    "fcs_autopilot_command",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
            except Exception as e:
                logger.error(f"[TEST] Error in FCS autopilot test: {str(e)}")
                self._record_test_result(
                    "fcs_autopilot_command",
                    success=False,
                    error=str(e)
                )
            
            logger.info("=== FCS Messages Testing Complete ===")
            
        except Exception as e:
            logger.error(f"Error in FCS message tests: {str(e)}")
            traceback.print_exc()

    def generate_test_report(self) -> str:
        """Generate a formatted test report"""
        # Update end time
        self.results["end_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate duration
        start = datetime.strptime(self.results["start_time"], "%Y-%m-%d %H:%M:%S")
        end = datetime.strptime(self.results["end_time"], "%Y-%m-%d %H:%M:%S")
        duration = (end - start).total_seconds()
        
        # Create the report
        report = [
            "==== PREDEFINED MESSAGES TEST RESULTS ====",
            f"Start Time: {self.results['start_time']}",
            f"End Time:   {self.results['end_time']}",
            f"Duration:   {duration:.2f} seconds",
            f"Total Tests: {self.results['summary']['total']}",
            f"Successful: {self.results['summary']['success']}",
            f"Failed: {self.results['summary']['failure']}",
            ""
        ]
        
        # Group tests by system
        systems = {
            "WEATHER RADAR": [t for t in self.results["tests"] if "weather_radar" in t["name"]],
            "TFR RADAR": [t for t in self.results["tests"] if "tfr_radar" in t["name"]],
            "SAR RADAR": [t for t in self.results["tests"] if "sar_radar" in t["name"]],
            "TARGETING RADAR": [t for t in self.results["tests"] if "targeting_radar" in t["name"]],
            "AEWC RADAR": [t for t in self.results["tests"] if "aewc_radar" in t["name"]],
            "FMS": [t for t in self.results["tests"] if "fms_" in t["name"]],
            "FCS": [t for t in self.results["tests"] if "fcs_" in t["name"]]
        }
        
        # Add system sections to report
        for system_name, tests in systems.items():
            if tests:
                report.append(f"--- {system_name} MESSAGES ---")
                for test in tests:
                    status = "[PASS]" if test["success"] else "[FAIL]"
                    req_id = f" - Request ID: {test['request_id']}" if test["request_id"] else ""
                    error = f" - ERROR: {test['error']}" if test["error"] else ""
                    report.append(f"{status} {test['name']}{req_id}{error}")
                report.append("")
        
        report.append("==== END TEST RESULTS ====")
        
        # Save report to files - both timestamped and central fixed files
        report_str = "\n".join(report)
        timestamp_report_file = f"predefined_messages_test_report_{start.strftime('%Y%m%d_%H%M%S')}.txt"
        central_report_file = "predefined_messages_latest_results.txt"
        json_report_file = "predefined_messages_latest_results.json"
        
        try:
            # Save timestamped report
            with open(timestamp_report_file, "w") as f:
                f.write(report_str)
                
            # Save to central results file (text format)
            with open(central_report_file, "w") as f:
                f.write(report_str)
            
            # Save to JSON format for programmatic access
            json_report = {
                "start_time": self.results["start_time"],
                "end_time": self.results["end_time"],
                "duration_seconds": duration,
                "summary": self.results["summary"],
                "tests": self.results["tests"],
                "by_system": {
                    system_name: [
                        {
                            "name": test["name"],
                            "success": test["success"],
                            "request_id": test["request_id"],
                            "error": test["error"],
                            "timestamp": test["timestamp"]
                        } for test in tests
                    ] for system_name, tests in systems.items() if tests
                }
            }
            
            with open(json_report_file, "w") as f:
                json.dump(json_report, f, indent=2)
                
            logger.info(f"Test reports saved to {timestamp_report_file}, {central_report_file}, and {json_report_file}")
        except Exception as e:
            logger.error(f"Error saving test report: {str(e)}")
        
        return report_str

    async def run_tests(self):
        """Run all predefined message tests"""
        try:
            # Initialize system
            await self.initialize()
            
            # Ensure message classes are fully initialized
            await self.messages.initialize()
            logger.info("Message classes initialized")
            
            # Wait a moment to ensure all sub-objects are available
            await asyncio.sleep(1)
            
            # Run tests for each message system
            await self.test_weather_radar_messages()
            await asyncio.sleep(self.LONG_WAIT)  # Long pause between test groups
            
            await self.test_tfr_radar_messages()
            await asyncio.sleep(self.LONG_WAIT)
            
            await self.test_sar_radar_messages()
            await asyncio.sleep(self.LONG_WAIT)
            
            await self.test_targeting_radar_messages()
            await asyncio.sleep(self.LONG_WAIT)
            
            await self.test_aewc_radar_messages()
            await asyncio.sleep(self.LONG_WAIT)
            
            await self.test_fms_messages()
            await asyncio.sleep(self.LONG_WAIT)
            
            await self.test_fcs_messages()
            
            # Generate and display test report
            report = self.generate_test_report()
            logger.info("\n" + report)

            # NOTE (production readiness re-analysis, August 2026): this used to
            # unconditionally `return True` here regardless of how many individual
            # message checks recorded failure=False via _record_test_result() above
            # -- each of the test_*_messages() methods catches its own exceptions
            # internally and records the failure rather than re-raising, so a
            # top-level failure was the ONLY way this method could ever return
            # False. That means Utils/debug/userCLI.py's `test` CLI command, which
            # branches on this return value to report "completed successfully!" vs
            # "failed!", would report success even when every single predefined
            # message assertion had failed -- a false-positive result that could
            # only be caught by a human reading the full report text. Now derived
            # from the actual recorded summary counts instead.
            failure_count = self.results["summary"]["failure"]
            if failure_count > 0:
                logger.error(f"\n{failure_count} predefined message check(s) failed -- see report above")
            return failure_count == 0
            
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
    try:
        import re  # Import here to avoid circular imports
        
        test_instance = PredefinedMessagesTest()
        result = asyncio.run(test_instance.run_tests())
        return result
    except Exception as e:
        logger.error(f"Error in test runner: {str(e)}")
        traceback.print_exc()
        return False

if __name__ == '__main__':
    # This test is designed to be run from the user CLI
    # It should not be run directly as it requires the system to be initialized
    logger.warning("This test should be run via the user CLI 'test' command")
    sys.exit(1)
