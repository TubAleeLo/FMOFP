"""
System-level test for setting the weather radar to SURVEILLANCE mode.
This test must be run before the VIL data flow test.

Enhanced with MIL-STD-1553B message flow tracing to identify where
messages might be lost or mishandled between system boundaries.
"""

import asyncio
import sys
import logging
import io
import traceback
import time
import re
import uuid
from typing import List, Optional, Dict, Tuple, Any

# Import setup environment
from FMOFP.Tests.setup_env import setup_environment
setup_environment()

from core.system_manager import get_system_manager
from Utils.logger.sys_logger import get_logger
from Systems.radarManagement.radar_enums import weather_radarMode

logger = get_logger()

class TestWeatherRadarSurveillanceMode:
    """System test for setting weather radar to SURVEILLANCE mode with detailed message tracing"""
    
    def __init__(self):
        """Initialize test using existing system infrastructure"""
        # Get system manager to access existing components
        self.system_manager = get_system_manager()
        
        # Get components from system manager
        self.radar_handler = self.system_manager.components.get('radar_message_handler')
        self.async_handler = self.system_manager.components.get('async_message_handler')
        
        # Setup logging capture
        self.log_capture = io.StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture)
        self.log_handler.setLevel(logging.DEBUG)  # Capture all log levels for detailed tracing
        self.log_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        
        # Add handlers
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        logger.logger.addHandler(self.log_handler)
        
        # Test metadata
        self.test_id = str(uuid.uuid4())[:8]  # Generate short unique ID for this test run
        self.verification_points = {}
        
        logger.info(f"[TRACE::{self.test_id}] Weather radar surveillance mode test initialized with tracing")

    async def initialize(self):
        """Verify system initialization"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Verifying system initialization")
            
            # Verify required components
            if not all([self.radar_handler, self.async_handler]):
                missing = [name for name, comp in {
                    'radar_message_handler': self.radar_handler,
                    'async_message_handler': self.async_handler
                }.items() if not comp]
                raise RuntimeError(f"Missing required components: {', '.join(missing)}")
            logger.info(f"[TRACE::{self.test_id}] Message handlers verified")
            
            # Verify AsyncMessageHandler is running
            if not (self.radar_handler.async_handler and self.radar_handler.async_handler.started):
                raise RuntimeError("RadarMessageHandler's AsyncMessageHandler is not properly initialized")
            logger.info(f"[TRACE::{self.test_id}] AsyncMessageHandler verified")
            
            # Setup verification points for message flow tracing
            self._setup_verification_points()
            
            logger.info(f"[TRACE::{self.test_id}] System initialization verification complete")
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error during test initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _setup_verification_points(self):
        """Setup verification points for the complete message flow"""
        # These will be checked against the log output - patterns based on actual log messages
        self.verification_points = {
            'local_request': {
                'description': "Local system generated mode change request",
                'pattern': r"Setting weather radar to SURVEILLANCE mode|mode change request.*weather_radar",
                'matched': False
            },
            'bc_received': {
                'description': "Bus Controller received mode change request",
                'pattern': r"\[BC\].*Structured message details|BC_sender sending.*message",
                'matched': False
            },
            'bc_transmit': {
                'description': "Bus Controller transmitted message on 1553B bus",
                'pattern': r"BC_sender sending.*message|BC_sender sending frame list",
                'matched': False
            },
            'rt_received': {
                'description': "Remote Terminal received message",
                'pattern': r"\[RT\].*Processing frames|Remote_Terminal.process_frames_loop: Processing frames",
                'matched': False
            },
            'rt_message_handled': {
                'description': "RT processed message and added to queue",
                'pattern': r"\[RT\].*Added message to processed_messages queue|Current processed_messages queue size",
                'matched': False
            },
            'radar_received': {
                'description': "Weather radar received mode change message",
                'pattern': r"\[WEATHER\].*Detected mode change message|\[WEATHER\].*Mode change command detected",
                'matched': False
            },
            'radar_mode_changed': {
                'description': "Weather radar mode changed to SURVEILLANCE",
                'pattern': r"\[WEATHER\].*Setting mode to: SURVEILLANCE|\[WEATHER\].*Weather radar mode changed from .* to SURVEILLANCE",
                'matched': False
            },
            'mode_change_completed': {
                'description': "Weather radar mode change completed",
                'pattern': r"\[WEATHER\].*Mode change completed",
                'matched': False
            },
            'completion_sent': {
                'description': "Mode change completion sent from radar",
                'pattern': r"\[WEATHER\].*Sending mode change completion notification",
                'matched': False
            },
            'completion_notification_sent': {
                'description': "Completion notification successfully sent",
                'pattern': r"\[WEATHER\].*Mode change completion notification sent successfully",
                'matched': False
            },
            'rt_sending_response': {
                'description': "RT sending response back",
                'pattern': r"RT sending frame|RT_send_message",
                'matched': False
            },
            'bc_receiving_response': {
                'description': "BC receiving response message",
                'pattern': r"\[BC\].*Detected mode change completion message|mode_change_complete",
                'matched': False
            },
            'display_notified': {
                'description': "Display notified of mode change",
                'pattern': r"Display mode change for weather radar: SURVEILLANCE",
                'matched': False
            }
        }

    def _verify_mode_change(self, log_output: str) -> Tuple[bool, Dict[str, Any]]:
        """Verify radar mode change in logs with detailed tracing"""
        # First, apply the original verification method
        basic_missing_patterns = []
        
        # Add debug logging
        logger.info(f"[TRACE::{self.test_id}] Checking radar mode change")
        logger.info(f"[TRACE::{self.test_id}] Log capture content length: {len(log_output)}")
        logger.info(f"[TRACE::{self.test_id}] Last 500 characters of log:")
        logger.info(log_output[-500:] if len(log_output) > 500 else log_output)
        
        # Define patterns to check for mode change - updated to match actual log format
        basic_patterns = [
            # Mode change request and processing
            # Alternative patterns for when radar is already in SURVEILLANCE mode
            (r"\[WEATHER\] Already in mode SURVEILLANCE, no change needed|"
             r"\[WEATHER\] Setting mode to: SURVEILLANCE",
                "Mode change in progress"),
            (r"\[WEATHER\] Mode changed to: SURVEILLANCE|"
             r"\[WEATHER\] Weather radar mode changed from .* to SURVEILLANCE",
                "Mode change completed"),
            
            # Display mode change routing patterns
            (r"metadata.*routed_to.*display",
                "Message routed to display"),
            (r"Display mode change for weather radar: SURVEILLANCE",
                "Display mode change confirmation")
        ]
        
        for pattern, desc in basic_patterns:
            if not re.search(pattern, log_output, re.IGNORECASE):
                logger.error(f"[TRACE::{self.test_id}] [VERIFY] Missing {desc}")
                basic_missing_patterns.append(desc)
            else:
                logger.info(f"[TRACE::{self.test_id}] [VERIFY] Found {desc}")
        
        basic_success = len(basic_missing_patterns) == 0
        
        # Now perform detailed tracing verification
        detailed_success, detailed_results = self._trace_message_flow(log_output)
        
        # Create combined result
        combined_success = basic_success and detailed_success
        
        combined_result = {
            'basic_success': basic_success,
            'basic_missing': basic_missing_patterns,
            'detailed_success': detailed_success,
            'detailed_results': detailed_results,
            'flow_breaks': self._analyze_message_flow_breaks(detailed_results) if not detailed_success else []
        }
        
        logger.info(f"[TRACE::{self.test_id}] Verification {'succeeded' if combined_success else 'failed'}")
        if not combined_success:
            if not basic_success:
                logger.error(f"[TRACE::{self.test_id}] Basic verification missing patterns: {basic_missing_patterns}")
            if not detailed_success:
                logger.error(f"[TRACE::{self.test_id}] Detailed flow verification failed")
        
        return combined_success, combined_result
        
    def _trace_message_flow(self, log_output: str) -> Tuple[bool, Dict[str, Any]]:
        """Perform detailed tracing of message flow through all verification points"""
        results = {}
        
        # Check each verification point
        for point_id, point_data in self.verification_points.items():
            pattern = point_data['pattern']
            description = point_data['description']
            
            # Try to find pattern in logs
            match = re.search(pattern, log_output, re.IGNORECASE)
            if match:
                point_data['matched'] = True
                match_line = match.group(0)
                
                # Find the full log line for better context
                lines = log_output.splitlines()
                full_line = next((line for line in lines if match_line in line), match_line)
                
                results[point_id] = {
                    'success': True,
                    'description': description,
                    'match': full_line
                }
                logger.info(f"[TRACE::{self.test_id}] ✓ {description}")
                logger.info(f"[TRACE::{self.test_id}] Match: {full_line}")
            else:
                results[point_id] = {
                    'success': False,
                    'description': description,
                    'error': f"No match found for pattern: {pattern}"
                }
                logger.error(f"[TRACE::{self.test_id}] ✗ {description}")
                logger.error(f"[TRACE::{self.test_id}] No match found for pattern: {pattern}")
        
        # Calculate overall success
        overall_success = all(result.get('success', False) for result in results.values())
        
        # Return overall success and detailed results
        return overall_success, results
    
    def _analyze_message_flow_breaks(self, results: Dict[str, Any]) -> List[str]:
        """Analyze where message flow breaks down based on verification results"""
        flow_breaks = []
        
        # Define the expected message flow order
        flow_order = [
            'local_request', 'bc_received', 'bc_transmit', 'rt_received', 
            'rt_message_handled', 'radar_received', 'radar_mode_changed', 
            'mode_change_completed', 'completion_sent', 'completion_notification_sent',
            'rt_sending_response', 'bc_receiving_response', 'display_notified'
        ]
        
        # Find breakpoints in the flow
        last_successful = None
        for point_id in flow_order:
            if results.get(point_id, {}).get('success', False):
                last_successful = point_id
            elif last_successful is not None:
                # This point failed but a previous one succeeded - found a break
                from_desc = self.verification_points[last_successful]['description']
                to_desc = self.verification_points[point_id]['description']
                flow_breaks.append(f"Message flow breaks between: {from_desc} → {to_desc}")
                last_successful = None
        
        return flow_breaks

    async def test_surveillance_mode(self) -> Dict[str, Any]:
        """Test setting weather radar to SURVEILLANCE mode with detailed message tracing"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Testing weather radar SURVEILLANCE mode change with MIL-STD-1553B message tracing...")
            
            # Clear logs before starting
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Generate unique request ID for tracing through the system
            request_id = f"trace-{self.test_id}-{str(uuid.uuid4())[:8]}"
            logger.info(f"[TRACE::{self.test_id}] Using request ID: {request_id}")
            
            # Set the radar to SURVEILLANCE mode with the traced request ID
            surveillance_mode = weather_radarMode.SURVEILLANCE
            logger.info(f"[TRACE::{self.test_id}] Setting weather radar to SURVEILLANCE mode")
            
            # Setup metadata for tracing
            metadata = {
                "request_id": request_id,
                "trace_id": self.test_id,
                "test_type": "mode_change_tracing"
            }
            
            # Send the request with metadata for tracing
            mode_request_id = await self.radar_handler.send_request(
                radar_name="weather_radar",
                request_type="mode_change",
                data=surveillance_mode,
                metadata=metadata
            )
            
            if not mode_request_id:
                raise AssertionError("Failed to get mode change request ID")
            
            logger.info(f"[TRACE::{self.test_id}] Mode change request sent with ID: {mode_request_id}")
            logger.info(f"[TRACE::{self.test_id}] Trace request ID: {request_id}")
            
            # Verify mode change with enhanced message flow tracing
            max_retries = 3
            retry_delay = 1.0
            success = False
            detailed_result = {}
            
            # Wait a bit longer for message propagation
            logger.info(f"[TRACE::{self.test_id}] Waiting for message propagation...")
            time.sleep(5.0)  # Increased from 3.0 to ensure full propagation
            
            for attempt in range(max_retries):
                logger.info(f"[TRACE::{self.test_id}] Verification attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1.0)
                
                # Get logs
                log_output = self.log_capture.getvalue()
                
                # Verify mode change with detailed tracing
                success, detailed_result = self._verify_mode_change(log_output)
                
                if success:
                    logger.info(f"[TRACE::{self.test_id}] Verification succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.info(f"[TRACE::{self.test_id}] Verification failed on attempt {attempt + 1}")
                    
                    # Provide information about where the message flow breaks
                    if 'flow_breaks' in detailed_result and detailed_result['flow_breaks']:
                        logger.error(f"[TRACE::{self.test_id}] Message flow breaks:")
                        for break_msg in detailed_result['flow_breaks']:
                            logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[TRACE::{self.test_id}] Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            
            if not success:
                # Prepare detailed error information
                error_details = []
                
                if detailed_result.get('basic_missing'):
                    missing = "\n".join(f"- {p}" for p in detailed_result['basic_missing'])
                    error_details.append(f"Basic verification failed:\n{missing}")
                
                if detailed_result.get('flow_breaks'):
                    breaks = "\n".join(f"- {b}" for b in detailed_result['flow_breaks'])
                    error_details.append(f"Message flow breaks:\n{breaks}")
                
                raise AssertionError(
                    f"Weather radar mode change verification failed:\n{' '.join(error_details)}"
                )
            
            # Calculate verification statistics
            total_points = len(self.verification_points)
            matched_points = sum(1 for point in self.verification_points.values() if point['matched'])
            success_rate = (matched_points / total_points) * 100
            
            logger.info(f"[TRACE::{self.test_id}] Message flow verification: {matched_points}/{total_points} points ({success_rate:.1f}%)")
            logger.info(f"[TRACE::{self.test_id}] Weather radar SURVEILLANCE mode test completed successfully")
            
            # Prepare test result
            test_result = {
                'success': True,
                'request_id': request_id,
                'trace_id': self.test_id,
                'verification_points': detailed_result,
                'success_rate': success_rate,
                'timestamp': time.time()
            }
            
            return test_result
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error in weather radar mode test: {str(e)}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'trace_id': self.test_id,
                'timestamp': time.time()
            }

    async def run_tests(self):
        """Run all weather radar mode tests with enhanced tracing"""
        try:
            # Initialize system
            await self.initialize()
            
            # Run test with message flow tracing
            mode_test_result = await self.test_surveillance_mode()
            
            # Report results
            logger.info(f"\n[TRACE::{self.test_id}] Test Results:")
            
            if mode_test_result.get('success', False):
                success_rate = mode_test_result.get('success_rate', 0)
                logger.info(f"[TRACE::{self.test_id}] Weather Radar SURVEILLANCE Mode Test: PASSED ({success_rate:.1f}% of verification points)")
            else:
                logger.error(f"[TRACE::{self.test_id}] Weather Radar SURVEILLANCE Mode Test: FAILED")
                
                # Report error details
                if 'error' in mode_test_result:
                    logger.error(f"[TRACE::{self.test_id}] Error: {mode_test_result['error']}")
                
                # Check for flow breaks
                verification_points = mode_test_result.get('verification_points', {})
                if verification_points and 'flow_breaks' in verification_points:
                    logger.error(f"[TRACE::{self.test_id}] Message Flow Breaks:")
                    for break_msg in verification_points['flow_breaks']:
                        logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
            
            return mode_test_result.get('success', False)
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error running tests: {e}")
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
    test_instance = TestWeatherRadarSurveillanceMode()
    result = asyncio.run(test_instance.run_tests())
    return result

if __name__ == '__main__':
    # This test is designed to be run from the user CLI
    # It should not be run directly as it requires the system to be initialized
    logger.warning("This test should be run via the user CLI 'test' command")
    sys.exit(1)
