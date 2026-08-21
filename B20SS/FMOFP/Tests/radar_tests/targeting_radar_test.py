"""
Comprehensive test for all Targeting Radar modes in the FMOFP system.
Tests transitions between all modes defined in the targeting_radarMode enum.
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
from FMOFP.Interfaces.predefinedMessages.radar_enums import targeting_radarMode

logger = get_logger()

class TargetingRadarTest:
    """Comprehensive test for all Targeting Radar modes and data requests"""
    
    def __init__(self):
        """Initialize test using existing system infrastructure"""
        # Get system manager to access existing components
        self.system_manager = get_system_manager()
        
        # Get components from system manager
        self.radar_handler = self.system_manager.components.get('radar_message_handler')
        self.async_handler = self.system_manager.components.get('async_message_handler')
        self.display_handler = get_display_message_handler()
        
        # Get message routing service
        from FMOFP.local_messaging.routing.MessageRoutingService import get_message_routing_service
        self.routing_service = get_message_routing_service()
        
        # Initialize Messages class which contains all predefined messages
        self.messages = get_messages()
        
        # Set wait times between operations (in seconds)
        self.SHORT_WAIT = 0.5   # Wait between each message in a test group
        self.MEDIUM_WAIT = 1.0  # Wait after mode changes to ensure mode is active
        self.LONG_WAIT = 2.0    # Wait between test groups to ensure no message overlap
        
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
        
        # Unique test ID for this run
        self.test_id = str(uuid.uuid4())[:8]
        
        # Setup logging capture
        self.log_capture = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture)
        self.log_handler.setLevel(logging.DEBUG)
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add handlers
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        logger.logger.addHandler(self.log_handler)
        
        logger.info(f"[TEST::{self.test_id}] Targeting Radar test initialized")

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

    async def initialize(self):
        """Verify system initialization"""
        try:
            logger.info(f"[TEST::{self.test_id}] Verifying system initialization")
            
            # Verify required components
            if not all([self.radar_handler, self.async_handler, self.display_handler]):
                missing = [name for name, comp in {
                    'radar_message_handler': self.radar_handler,
                    'async_message_handler': self.async_handler,
                    'display_message_handler': self.display_handler
                }.items() if not comp]
                raise RuntimeError(f"Missing required components: {', '.join(missing)}")
            logger.info(f"[TEST::{self.test_id}] Message handlers verified")
            
            # Verify AsyncMessageHandler is running
            if not (self.radar_handler.async_handler and self.radar_handler.async_handler.started):
                raise RuntimeError("RadarMessageHandler's AsyncMessageHandler is not properly initialized")
            logger.info(f"[TEST::{self.test_id}] AsyncMessageHandler verified")
            
            # Verify routing service
            if not self.routing_service:
                raise RuntimeError("Message routing service not available")
            logger.info(f"[TEST::{self.test_id}] Message routing service verified")
            
            # Initialize the Messages object
            await self.messages.initialize()
            logger.info(f"[TEST::{self.test_id}] Message classes initialized")
            
            logger.info(f"[TEST::{self.test_id}] System initialization verification complete")
            
        except Exception as e:
            logger.error(f"[TEST::{self.test_id}] Error during test initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    async def test_all_targeting_radar_modes(self):
        """Test ALL Targeting Radar modes and transitions between them"""
        try:
            logger.info(f"[TEST::{self.test_id}] === Testing All Targeting Radar Modes ===")
            
            # Get all available modes from the enum
            all_modes = list(targeting_radarMode)
            logger.info(f"[TEST::{self.test_id}] Testing {len(all_modes)} Targeting Radar modes: {[mode.name for mode in all_modes]}")
            
            # First, ensure radar is in STANDBY mode to start with a known state
            logger.info(f"[TEST::{self.test_id}] Setting initial STANDBY mode")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            initial_mode = targeting_radarMode.STANDBY
            request_id = await self.messages.targeting_radar.set_targeting_radar_mode(initial_mode)
            
            # Wait for mode change to take effect
            await asyncio.sleep(self.MEDIUM_WAIT)
            
            # Now test each mode transition
            for mode in all_modes:
                if mode == targeting_radarMode.STANDBY:
                    # Skip STANDBY as we've already tested it in initialization
                    continue
                    
                logger.info(f"[TEST::{self.test_id}] Testing transition to {mode.name} mode")
                
                # Clear log capture for this test
                self.log_capture.seek(0)
                self.log_capture.truncate()
                
                # Send mode change request
                try:
                    request_id = await self.messages.targeting_radar.set_targeting_radar_mode(mode)
                    logger.info(f"[TEST::{self.test_id}] Mode change request sent with ID: {request_id}")
                    
                    if not request_id:
                        raise ValueError("Failed to get request ID")
                    
                    # Wait for mode change to take effect
                    await asyncio.sleep(self.MEDIUM_WAIT)
                    
                    # Verify mode change in logs - both radar and display
                    log_output = self.log_capture.getvalue()
                    
                    # Verify radar mode change
                    radar_patterns = [
                        (f"targeting_radar.*{mode.name}|setting mode to.*{mode.name}", "Radar mode change confirmation"),
                        (f"Handling mode change|Processed mode value.*{mode.name}", "Mode change processing")
                    ]
                    
                    # Verify display mode update
                    display_patterns = [
                        (f"Sending mode change completion notification|{mode.name}", "Display mode update"),
                        (f"Using request ID|request_id", "Display processing")
                    ]
                    
                    # Check both radar and display
                    radar_success, radar_missing = self._verify_log_patterns(
                        f"targeting_radar_{mode.name}_radar",
                        log_output,
                        radar_patterns
                    )
                    
                    display_success, display_missing = self._verify_log_patterns(
                        f"targeting_radar_{mode.name}_display",
                        log_output,
                        display_patterns
                    )
                    
                    # Record combined result
                    success = radar_success and display_success
                    error = None
                    if not success:
                        missing_details = []
                        if not radar_success:
                            missing_details.append(f"Radar missing: {', '.join(radar_missing)}")
                        if not display_success:
                            missing_details.append(f"Display missing: {', '.join(display_missing)}")
                        error = "; ".join(missing_details)
                    
                    self._record_test_result(
                        f"targeting_radar_to_{mode.name.lower()}_mode",
                        success=success,
                        request_id=request_id,
                        error=error
                    )
                    
                    # Wait before next mode test
                    await asyncio.sleep(self.SHORT_WAIT)
                    
                except Exception as e:
                    logger.error(f"[TEST::{self.test_id}] Error in {mode.name} mode test: {str(e)}")
                    self._record_test_result(
                        f"targeting_radar_to_{mode.name.lower()}_mode",
                        success=False,
                        error=str(e)
                    )
                    
                # Set back to STANDBY before testing next mode
                logger.info(f"[TEST::{self.test_id}] Resetting to STANDBY mode")
                reset_request_id = await self.messages.targeting_radar.set_targeting_radar_mode(targeting_radarMode.STANDBY)
                await asyncio.sleep(self.MEDIUM_WAIT)
            
            logger.info(f"[TEST::{self.test_id}] === Targeting Radar Mode Testing Complete ===")
            
        except Exception as e:
            logger.error(f"[TEST::{self.test_id}] Error in Targeting radar mode tests: {str(e)}")
            traceback.print_exc()

    async def test_targeting_radar_data_requests(self):
        """Test all Targeting Radar data requests"""
        try:
            logger.info(f"[TEST::{self.test_id}] === Testing Targeting Radar Data Requests ===")
            
            # Set radar to TRACKING mode for data requests (this is the most suitable mode for targeting)
            logger.info(f"[TEST::{self.test_id}] Setting to TRACKING mode for data tests")
            mode_request_id = await self.messages.targeting_radar.targeting_radar_to_tracking_mode()
            await asyncio.sleep(self.MEDIUM_WAIT)
            
            # Test track data request
            logger.info(f"[TEST::{self.test_id}] Testing track data request")
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            try:
                request_id = await self.messages.targeting_radar.request_track_data()
                logger.info(f"[TEST::{self.test_id}] Track data request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for track data processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"track data|targeting|target", "Track data processing"),
                    (r"stored|processing", "Data storage or processing")
                ]
                success, missing = self._verify_log_patterns("track_data", log_output, patterns)
                
                self._record_test_result(
                    "request_track_data",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
                # Wait before next test
                await asyncio.sleep(self.MEDIUM_WAIT)
                
            except Exception as e:
                logger.error(f"[TEST::{self.test_id}] Error in track data test: {str(e)}")
                self._record_test_result(
                    "request_track_data",
                    success=False,
                    error=str(e)
                )
            
            # Test radar lock request if available
            try:
                logger.info(f"[TEST::{self.test_id}] Testing target lock request")
                self.log_capture.seek(0)
                self.log_capture.truncate()
                
                # Create a mock track ID for testing
                mock_track_id = f"track_{self.test_id}"
                
                # Use a generic request method or a specific one if available
                if hasattr(self.messages.targeting_radar, "request_targeting_radar_lock"):
                    request_id = await self.messages.targeting_radar.request_targeting_radar_lock(
                        track_id=mock_track_id,
                        lock_parameters={"priority": "high"}
                    )
                else:
                    # Create a custom request if specific method is not available
                    request_id = await self.radar_handler.send_request(
                        radar_name="targeting_radar",
                        request_type="lock",
                        data={"track_id": mock_track_id, "priority": "high"}
                    )
                
                logger.info(f"[TEST::{self.test_id}] Target lock request sent with ID: {request_id}")
                
                if not request_id:
                    raise ValueError("Failed to get request ID")
                
                # Wait for data processing
                await asyncio.sleep(self.SHORT_WAIT)
                
                # Verify logs for lock processing
                log_output = self.log_capture.getvalue()
                patterns = [
                    (r"lock|track|targeting", "Lock request processing"),
                    (r"stored|processing", "Data storage or processing")
                ]
                success, missing = self._verify_log_patterns("target_lock", log_output, patterns)
                
                self._record_test_result(
                    "request_target_lock",
                    success=success,
                    request_id=request_id,
                    error=None if success else f"Missing log patterns: {', '.join(missing)}"
                )
                
            except Exception as e:
                logger.error(f"[TEST::{self.test_id}] Error in target lock test: {str(e)}")
                self._record_test_result(
                    "request_target_lock",
                    success=False,
                    error=str(e)
                )
            
            # Reset to STANDBY mode
            logger.info(f"[TEST::{self.test_id}] Resetting to STANDBY mode")
            reset_request_id = await self.messages.targeting_radar.set_targeting_radar_mode(targeting_radarMode.STANDBY)
            await asyncio.sleep(self.MEDIUM_WAIT)
            
            logger.info(f"[TEST::{self.test_id}] === Targeting Radar Data Testing Complete ===")
            
        except Exception as e:
            logger.error(f"[TEST::{self.test_id}] Error in Targeting radar data tests: {str(e)}")
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
            f"==== TARGETING RADAR TEST RESULTS ({self.test_id}) ====",
            f"Start Time: {self.results['start_time']}",
            f"End Time:   {self.results['end_time']}",
            f"Duration:   {duration:.2f} seconds",
            f"Total Tests: {self.results['summary']['total']}",
            f"Successful: {self.results['summary']['success']}",
            f"Failed: {self.results['summary']['failure']}",
            ""
        ]
        
        # Group tests by category
        categories = {
            "MODE CHANGES": [t for t in self.results["tests"] if "to_" in t["name"] and "_mode" in t["name"]],
            "DATA REQUESTS": [t for t in self.results["tests"] if "request_" in t["name"]]
        }
        
        # Add category sections to report
        for category_name, tests in categories.items():
            if tests:
                report.append(f"--- {category_name} ---")
                for test in tests:
                    status = "[PASS]" if test["success"] else "[FAIL]"
                    req_id = f" - Request ID: {test['request_id']}" if test["request_id"] else ""
                    error = f" - ERROR: {test['error']}" if test["error"] else ""
                    report.append(f"{status} {test['name']}{req_id}{error}")
                report.append("")
        
        report.append(f"==== END TEST RESULTS ({self.test_id}) ====")
        
        # Save report to files
        report_str = "\n".join(report)
        timestamp_report_file = f"targeting_radar_test_report_{start.strftime('%Y%m%d_%H%M%S')}.txt"
        json_report_file = f"targeting_radar_test_results_{self.test_id}.json"
        
        try:
            # Save timestamped report
            with open(timestamp_report_file, "w") as f:
                f.write(report_str)
                
            # Save to JSON format for programmatic access
            json_report = {
                "test_id": self.test_id,
                "start_time": self.results["start_time"],
                "end_time": self.results["end_time"],
                "duration_seconds": duration,
                "summary": self.results["summary"],
                "tests": self.results["tests"],
                "by_category": {
                    category_name: [
                        {
                            "name": test["name"],
                            "success": test["success"],
                            "request_id": test["request_id"],
                            "error": test["error"],
                            "timestamp": test["timestamp"]
                        } for test in tests
                    ] for category_name, tests in categories.items() if tests
                }
            }
            
            with open(json_report_file, "w") as f:
                json.dump(json_report, f, indent=2)
                
            logger.info(f"[TEST::{self.test_id}] Test reports saved to {timestamp_report_file} and {json_report_file}")
        except Exception as e:
            logger.error(f"[TEST::{self.test_id}] Error saving test report: {str(e)}")
        
        return report_str

    async def run_tests(self):
        """Run all Targeting Radar tests"""
        try:
            # Initialize system
            await self.initialize()
            
            # Run tests for all Targeting radar modes
            await self.test_all_targeting_radar_modes()
            await asyncio.sleep(self.LONG_WAIT)  # Long pause between test groups
            
            # Run tests for Targeting radar data requests
            await self.test_targeting_radar_data_requests()
            
            # Generate and display test report
            report = self.generate_test_report()
            logger.info("\n" + report)
            
            return self.results["summary"]["failure"] == 0
            
        except Exception as e:
            logger.error(f"[TEST::{self.test_id}] Error running tests: {str(e)}")
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
        test_instance = TargetingRadarTest()
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
