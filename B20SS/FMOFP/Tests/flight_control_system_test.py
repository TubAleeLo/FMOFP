"""
System-level test for Flight Control System (FCS)

This test implements comprehensive testing of the Flight Control System
with complete MIL-STD-1553B message flow tracing to identify where
messages might be lost or mishandled between system boundaries.

Tests:
1. FCS mode changes
2. Control input handling
3. Orientation data requests/responses
4. FCS status requests/responses
5. Message routing through FMS messenger
"""

import asyncio
import sys
import logging
import io
import traceback
import time
import re
import uuid
from typing import List, Optional, Dict, Tuple, Any, Union

# Import setup environment
from FMOFP.Tests.setup_env import setup_environment
setup_environment()

from FMOFP.core.system_manager import get_system_manager
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.flightManagementSys.flightControlSys.flight_control_system import (
    get_flight_control_system,
    FlightControlModes
)
from FMOFP.Systems.flightManagementSys.fms_messaging.message_types import (
    FCS_CONTROL_INPUT_REQUEST,
    FCS_CONTROL_INPUT_RESPONSE,
    FCS_ORIENTATION_DATA_REQUEST,
    FCS_ORIENTATION_DATA_RESPONSE,
    FCS_STATUS_REQUEST,
    FCS_STATUS_RESPONSE,
    FCS_MODE_CHANGE_REQUEST,
    FCS_MODE_CHANGE_RESPONSE
)
from FMOFP.local_messaging.command_word_map_fcs import FCS_COMMAND_WORDS

logger = get_logger()

class TestFlightControlSystem:
    """System test for Flight Control System with detailed message tracing"""
    
    def __init__(self):
        """Initialize test using existing system infrastructure"""
        # Get system manager to access existing components
        self.system_manager = get_system_manager()
        
        # Get components from system manager
        self.fms_handler = self.system_manager.components.get('fms_message_handler')
        self.async_handler = self.system_manager.components.get('async_message_handler')
        
        # Get FCS system through the FMS
        self.fcs = get_flight_control_system()
        
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
        
        logger.info(f"[TRACE::{self.test_id}] FCS system test initialized with tracing")

    async def initialize(self):
        """Verify system initialization"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Verifying system initialization")
            
            # Verify required components
            if not all([self.fms_handler, self.async_handler]):
                missing = [name for name, comp in {
                    'fms_message_handler': self.fms_handler,
                    'async_message_handler': self.async_handler
                }.items() if not comp]
                raise RuntimeError(f"Missing required components: {', '.join(missing)}")
            logger.info(f"[TRACE::{self.test_id}] Message handlers verified")
            
            # Verify AsyncMessageHandler is running
            if not (self.fms_handler.async_handler and self.fms_handler.async_handler.started):
                raise RuntimeError("FMSMessageHandler's AsyncMessageHandler is not properly initialized")
            logger.info(f"[TRACE::{self.test_id}] AsyncMessageHandler verified")
            
            # Verify FCS system is available
            if not self.fcs:
                raise RuntimeError("Flight Control System not found")
            logger.info(f"[TRACE::{self.test_id}] FCS system verified")
            
            # Setup verification points for message flow tracing
            self._setup_verification_points()
            
            logger.info(f"[TRACE::{self.test_id}] System initialization verification complete")
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error during test initialization: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def _setup_verification_points(self):
        """Setup verification points for the complete message flow"""
        # Mode change verification points
        self.mode_verification_points = {
            'local_request': {
                'description': "Local system generated mode change request",
                'pattern': r"Setting FCS mode to|mode change request.*flightControlSystem",
                'matched': False
            },
            'request_processing': {
                'description': "FMS handler processing mode change request",
                'pattern': r"Processing mode change to|_handle_mode_change.*request_id",
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
            'fcs_received': {
                'description': "FCS received mode change message",
                'pattern': r"\[FCS\].*Handling mode change message|\[FCS\].*mode change",
                'matched': False
            },
            'fcs_mode_changed': {
                'description': "FCS mode changed to specified mode",
                'pattern': r"\[FCS\].*Mode changed from|\[FCS\].*set to",
                'matched': False
            },
            'mode_change_completed': {
                'description': "FCS mode change completed",
                'pattern': r"\[FCS\].*Mode changed from|command.*successful",
                'matched': False
            },
            'completion_sent': {
                'description': "Mode change completion sent from FCS",
                'pattern': r"\[FCS_COMP\].*Preparing mode change completion|\[FCS_COMP\].*Sending completion message",
                'matched': False
            },
            'completion_notification_sent': {
                'description': "Completion notification successfully sent",
                'pattern': r"\[FCS\].*Mode change completion notification sent successfully",
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
            'fms_response_received': {
                'description': "FMS handler received mode change response",
                'pattern': r"\[FMS_MSGR\].*Sending response for request_id|mode_change_response",
                'matched': False
            }
        }
        
        # Control input verification points
        self.control_verification_points = {
            'control_request': {
                'description': "Local system generated control input request",
                'pattern': r"Control input request|control input.*request",
                'matched': False
            },
            'control_processing': {
                'description': "FMS handler processing control input request",
                'pattern': r"Processing control input|_handle_control_input",
                'matched': False
            },
            'bc_control_received': {
                'description': "Bus Controller received control input request",
                'pattern': r"\[BC\].*Structured message details|BC_sender sending.*message",
                'matched': False
            },
            'bc_control_transmit': {
                'description': "Bus Controller transmitted control message on 1553B bus",
                'pattern': r"BC_sender sending.*message|BC_sender sending frame list",
                'matched': False
            },
            'rt_control_received': {
                'description': "Remote Terminal received control message",
                'pattern': r"\[RT\].*Processing frames|Remote_Terminal.process_frames_loop: Processing frames",
                'matched': False
            },
            'fcs_control_received': {
                'description': "FCS received control input message",
                'pattern': r"\[FCS\].*Handling control input message|control input",
                'matched': False
            },
            'control_input_set': {
                'description': "FCS control input set to new value",
                'pattern': r"\[FCS\].*changed from .* to|\[FCS\].*control input",
                'matched': False
            },
            'control_completion_sent': {
                'description': "Control input completion sent from FCS",
                'pattern': r"\[FCS\].*Control input completion notification sent",
                'matched': False
            },
            'control_response_received': {
                'description': "FMS handler received control input response",
                'pattern': r"\[FMS_MSGR\].*Sending response for request_id|control.*response",
                'matched': False
            }
        }
        
        # Orientation data verification points
        self.orientation_verification_points = {
            'orientation_request': {
                'description': "Local system generated orientation data request",
                'pattern': r"Orientation data request|ORIENTATION_DATA.*request",
                'matched': False
            },
            'orientation_processing': {
                'description': "FMS handler processing orientation data request",
                'pattern': r"Processing orientation data|_handle_orientation",
                'matched': False
            },
            'fcs_orientation_received': {
                'description': "FCS received orientation data request",
                'pattern': r"\[FCS\].*Handling orientation data|orientation data request",
                'matched': False
            },
            'orientation_data_sent': {
                'description': "FCS sending orientation data",
                'pattern': r"\[FCS\].*Sending orientation data|orientation data.*sent",
                'matched': False
            },
            'orientation_response_received': {
                'description': "FMS handler received orientation data response",
                'pattern': r"\[FMS_MSGR\].*orientation data|response.*orientation",
                'matched': False
            }
        }
        
        # Status request verification points
        self.status_verification_points = {
            'status_request': {
                'description': "Local system generated status request",
                'pattern': r"Status request|status.*request",
                'matched': False
            },
            'status_processing': {
                'description': "FMS handler processing status request",
                'pattern': r"Processing status request|_handle_status_request",
                'matched': False
            },
            'fcs_status_received': {
                'description': "FCS received status request",
                'pattern': r"\[FCS\].*status request|get status",
                'matched': False
            },
            'status_response_sent': {
                'description': "Status response sent",
                'pattern': r"\[FCS\].*status.*response|status.*sent",
                'matched': False
            },
            'status_response_received': {
                'description': "FMS handler received status response",
                'pattern': r"status.*response|fms_message_handler.*status",
                'matched': False
            }
        }

    def _verify_message_flow(self, log_output: str, verification_points: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify message flow against verification points in logs with detailed tracing
        
        Args:
            log_output: The log output to analyze
            verification_points: Dictionary of verification points to check
            
        Returns:
            Tuple of (success, results)
        """
        results = {}
        
        # Add debug logging
        logger.info(f"[TRACE::{self.test_id}] Checking message flow")
        logger.info(f"[TRACE::{self.test_id}] Log capture content length: {len(log_output)}")
        logger.info(f"[TRACE::{self.test_id}] Last 500 characters of log:")
        logger.info(log_output[-500:] if len(log_output) > 500 else log_output)
        
        # Check each verification point
        for point_id, point_data in verification_points.items():
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
    
    def _analyze_message_flow_breaks(self, results: Dict[str, Any], verification_points_order: List[str]) -> List[str]:
        """
        Analyze where message flow breaks down based on verification results
        
        Args:
            results: Dictionary of verification results
            verification_points_order: List of verification point IDs in expected order
            
        Returns:
            List of error messages describing flow breaks
        """
        flow_breaks = []
        
        # Find breakpoints in the flow
        last_successful = None
        for point_id in verification_points_order:
            if point_id in results and results[point_id].get('success', False):
                last_successful = point_id
            elif last_successful is not None and point_id in results:
                # This point failed but a previous one succeeded - found a break
                from_desc = results[last_successful]['description']
                to_desc = results[point_id]['description']
                flow_breaks.append(f"Message flow breaks between: {from_desc} → {to_desc}")
                last_successful = None
        
        return flow_breaks

    async def test_fcs_mode_change(self) -> Dict[str, Any]:
        """Test FCS mode change functionality with detailed message tracing"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Testing FCS mode change with MIL-STD-1553B message tracing...")
            
            # Clear logs before starting
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Generate unique request ID for tracing through the system
            request_id = f"trace-{self.test_id}-{str(uuid.uuid4())[:8]}"
            logger.info(f"[TRACE::{self.test_id}] Using request ID: {request_id}")
            
            # Set the FCS to COMBAT mode with the traced request ID
            target_mode = FlightControlModes.COMBAT
            logger.info(f"[TRACE::{self.test_id}] Setting FCS mode to {target_mode}")
            
            # Setup metadata for tracing
            metadata = {
                "request_id": request_id,
                "trace_id": self.test_id,
                "test_type": "mode_change_tracing"
            }
            
            # Send the request with metadata for tracing
            logger.info(f"[TRACE::{self.test_id}] Sending mode change request to FCS")
            
            # Send request using the proper send_request API with mode_name parameter
            mode_request_id = await self.fms_handler.send_request(
                system_name="flight_control_system",
                request_type="mode_change",
                data={"mode_name": target_mode},  # Use mode_name parameter in a dictionary (same format as FMS)
                metadata=metadata
            )
            
            if not mode_request_id:
                raise AssertionError("Failed to get mode change request ID")
            
            logger.info(f"[TRACE::{self.test_id}] Mode change request sent with ID: {mode_request_id}")
            
            # No immediate result since we're using the async API
            # We'll verify success through message flow tracing instead
            logger.info(f"[TRACE::{self.test_id}] Mode change request submitted, waiting for message flow...")
            logger.info(f"[TRACE::{self.test_id}] Trace request ID: {request_id}")
            
            # Verify mode change with enhanced message flow tracing
            max_retries = 3
            retry_delay = 1.0
            success = False
            detailed_result = {}
            
            # Wait for message propagation
            logger.info(f"[TRACE::{self.test_id}] Waiting for message propagation...")
            time.sleep(3.0)
            
            for attempt in range(max_retries):
                logger.info(f"[TRACE::{self.test_id}] Verification attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1.0)
                
                # Get logs
                log_output = self.log_capture.getvalue()
                
                # Verify mode change with detailed tracing
                success, detailed_result = self._verify_message_flow(log_output, self.mode_verification_points)
                
                if success:
                    logger.info(f"[TRACE::{self.test_id}] Verification succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.info(f"[TRACE::{self.test_id}] Verification failed on attempt {attempt + 1}")
                    
                    # Analyze where message flow breaks occur
                    flow_points_order = [
                        'local_request', 'request_processing', 'bc_received', 'bc_transmit', 
                        'rt_received', 'rt_message_handled', 'fcs_received', 'fcs_mode_changed',
                        'mode_change_completed', 'completion_sent', 'completion_notification_sent',
                        'rt_sending_response', 'bc_receiving_response', 'fms_response_received'
                    ]
                    
                    flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                    if flow_breaks:
                        logger.error(f"[TRACE::{self.test_id}] Message flow breaks:")
                        for break_msg in flow_breaks:
                            logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[TRACE::{self.test_id}] Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            
            # Verify mode was actually changed in the FCS
            actual_mode = self.fcs.mode
            
            if actual_mode != target_mode:
                logger.error(f"[TRACE::{self.test_id}] FCS mode verification failed: expected {target_mode}, got {actual_mode}")
                success = False
            else:
                logger.info(f"[TRACE::{self.test_id}] FCS mode verification succeeded: {actual_mode}")
            
            if not success:
                # Prepare detailed error information
                error_details = []
                
                # Add mode verification failure if applicable
                if actual_mode != target_mode:
                    error_details.append(f"FCS mode verification failed: expected {target_mode}, got {actual_mode}")
                
                # Add information about flow breaks
                flow_points_order = [
                    'local_request', 'request_processing', 'bc_received', 'bc_transmit', 
                    'rt_received', 'rt_message_handled', 'fcs_received', 'fcs_mode_changed',
                    'mode_change_completed', 'completion_sent', 'completion_notification_sent',
                    'rt_sending_response', 'bc_receiving_response', 'fms_response_received'
                ]
                
                flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                if flow_breaks:
                    breaks = "\n".join(f"- {b}" for b in flow_breaks)
                    error_details.append(f"Message flow breaks:\n{breaks}")
                
                raise AssertionError(
                    f"FCS mode change verification failed:\n{' '.join(error_details)}"
                )
            
            # Calculate verification statistics
            total_points = len(self.mode_verification_points)
            matched_points = sum(1 for point in self.mode_verification_points.values() if point['matched'])
            success_rate = (matched_points / total_points) * 100
            
            logger.info(f"[TRACE::{self.test_id}] Message flow verification: {matched_points}/{total_points} points ({success_rate:.1f}%)")
            logger.info(f"[TRACE::{self.test_id}] FCS mode change test completed successfully")
            
            # Prepare test result
            test_result = {
                'success': True,
                'request_id': request_id,
                'trace_id': self.test_id,
                'verification_points': detailed_result,
                'success_rate': success_rate,
                'new_mode': actual_mode,
                'timestamp': time.time()
            }
            
            return test_result
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error in FCS mode test: {str(e)}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'trace_id': self.test_id,
                'timestamp': time.time()
            }

    async def test_control_input(self) -> Dict[str, Any]:
        """Test FCS control input functionality with detailed message tracing"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Testing FCS control input with message tracing...")
            
            # Clear logs before starting
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Generate unique request ID for tracing through the system
            request_id = f"trace-{self.test_id}-{str(uuid.uuid4())[:8]}"
            logger.info(f"[TRACE::{self.test_id}] Using request ID: {request_id}")
            
            # Save original control values for verification
            original_control_inputs = self.fcs.control_inputs.copy()
            logger.info(f"[TRACE::{self.test_id}] Original control inputs: {original_control_inputs}")
            
            # Setup control input parameters - change aileron input
            control_type = 'aileron'
            control_value = 0.5  # 50% right roll
            
            # Setup metadata for tracing
            metadata = {
                "request_id": request_id,
                "trace_id": self.test_id,
                "test_type": "control_input_tracing",
                "control_type": control_type
            }
            
            # Create control input request parameters
            control_data = {
                "control_type": control_type,
                "value": control_value
            }
            
            logger.info(f"[TRACE::{self.test_id}] Sending control input request: {control_type}={control_value}")
            
            # Send request using the proper send_request API
            control_request_id = await self.fms_handler.send_request(
                system_name="flight_control_system",
                request_type="control_input",
                data=control_data,
                metadata=metadata
            )
            
            if not control_request_id:
                raise AssertionError("Failed to get control input request ID")
            
            logger.info(f"[TRACE::{self.test_id}] Control input request sent with ID: {control_request_id}")
            logger.info(f"[TRACE::{self.test_id}] Trace request ID: {request_id}")
            
            # Verify control input with message flow tracing
            max_retries = 3
            retry_delay = 1.0
            success = False
            detailed_result = {}
            
            # Wait for message propagation
            logger.info(f"[TRACE::{self.test_id}] Waiting for message propagation...")
            time.sleep(2.0)
            
            for attempt in range(max_retries):
                logger.info(f"[TRACE::{self.test_id}] Verification attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1.0)
                
                # Get logs
                log_output = self.log_capture.getvalue()
                
                # Verify control input with detailed tracing
                success, detailed_result = self._verify_message_flow(log_output, self.control_verification_points)
                
                if success:
                    logger.info(f"[TRACE::{self.test_id}] Verification succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.info(f"[TRACE::{self.test_id}] Verification failed on attempt {attempt + 1}")
                    
                    # Analyze where message flow breaks occur
                    flow_points_order = [
                        'control_request', 'control_processing', 'bc_control_received', 
                        'bc_control_transmit', 'rt_control_received', 'fcs_control_received',
                        'control_input_set', 'control_completion_sent', 'control_response_received'
                    ]
                    
                    flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                    if flow_breaks:
                        logger.error(f"[TRACE::{self.test_id}] Message flow breaks:")
                        for break_msg in flow_breaks:
                            logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[TRACE::{self.test_id}] Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            
            # Verify control was actually updated in the FCS
            actual_value = self.fcs.control_inputs.get(control_type)
            
            # Check if control value is within acceptable tolerance
            control_updated = abs(actual_value - control_value) < 0.01
            
            if not control_updated:
                logger.error(f"[TRACE::{self.test_id}] Control input verification failed:")
                logger.error(f"[TRACE::{self.test_id}] Expected: {control_value}")
                logger.error(f"[TRACE::{self.test_id}] Actual: {actual_value}")
                success = False
            else:
                logger.info(f"[TRACE::{self.test_id}] Control input verification succeeded: {control_type}={actual_value}")
            
            if not success:
                # Prepare detailed error information
                error_details = []
                
                # Add control verification failure if applicable
                if not control_updated:
                    error_details.append(f"Control input verification failed: Expected {control_value}, got {actual_value}")
                
                # Add information about flow breaks
                flow_points_order = [
                    'control_request', 'control_processing', 'bc_control_received', 
                    'bc_control_transmit', 'rt_control_received', 'fcs_control_received',
                    'control_input_set', 'control_completion_sent', 'control_response_received'
                ]
                
                flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                if flow_breaks:
                    breaks = "\n".join(f"- {b}" for b in flow_breaks)
                    error_details.append(f"Message flow breaks:\n{breaks}")
                
                raise AssertionError(
                    f"FCS control input verification failed:\n{' '.join(error_details)}"
                )
            
            # Calculate verification statistics
            total_points = len(self.control_verification_points)
            matched_points = sum(1 for point in self.control_verification_points.values() if point['matched'])
            success_rate = (matched_points / total_points) * 100
            
            logger.info(f"[TRACE::{self.test_id}] Message flow verification: {matched_points}/{total_points} points ({success_rate:.1f}%)")
            logger.info(f"[TRACE::{self.test_id}] FCS control input test completed successfully")
            
            # Reset control to original value
            self.fcs.set_control_input(control_type, original_control_inputs[control_type], send_completion=False)
            logger.info(f"[TRACE::{self.test_id}] Reset {control_type} to original value: {original_control_inputs[control_type]}")
            
            # Prepare test result
            test_result = {
                'success': True,
                'request_id': request_id,
                'trace_id': self.test_id,
                'verification_points': detailed_result,
                'success_rate': success_rate,
                'control_type': control_type,
                'control_value': actual_value,
                'timestamp': time.time()
            }
            
            return test_result
            
        except Exception as e:
            logger.error(f"[TRACE::{self.test_id}] Error in FCS control input test: {str(e)}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'trace_id': self.test_id,
                'timestamp': time.time()
            }
    
    async def test_orientation_data(self) -> Dict[str, Any]:
        """Test FCS orientation data functionality with detailed message tracing"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Testing FCS orientation data with message tracing...")
            
            # Clear logs before starting
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Generate unique request ID for tracing through the system
            request_id = f"trace-{self.test_id}-{str(uuid.uuid4())[:8]}"
            logger.info(f"[TRACE::{self.test_id}] Using request ID: {request_id}")
            
            # Setup metadata for tracing
            metadata = {
                "request_id": request_id,
                "trace_id": self.test_id,
                "test_type": "orientation_data_tracing"
            }
            
            # Create orientation data request
            logger.info(f"[TRACE::{self.test_id}] Sending orientation data request")
            
            # Send request using the proper send_request API
            orientation_request_id = await self.fms_handler.send_request(
                system_name="flight_control_system",
                request_type="orientation_data",
                data={},  # No additional data needed for orientation request
                metadata=metadata
            )
            
            if not orientation_request_id:
                raise AssertionError("Failed to get orientation data request ID")
            
            logger.info(f"[TRACE::{self.test_id}] Orientation data request sent with ID: {orientation_request_id}")
            logger.info(f"[TRACE::{self.test_id}] Trace request ID: {request_id}")
            
            # Verify orientation data request with message flow tracing
            max_retries = 3
            retry_delay = 1.0
            success = False
            detailed_result = {}
            
            # Wait for message propagation
            logger.info(f"[TRACE::{self.test_id}] Waiting for message propagation...")
            time.sleep(2.0)
            
            for attempt in range(max_retries):
                logger.info(f"[TRACE::{self.test_id}] Verification attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1.0)
                
                # Get logs
                log_output = self.log_capture.getvalue()
                
                # Verify orientation data with detailed tracing
                success, detailed_result = self._verify_message_flow(log_output, self.orientation_verification_points)
                
                if success:
                    logger.info(f"[TRACE::{self.test_id}] Verification succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.info(f"[TRACE::{self.test_id}] Verification failed on attempt {attempt + 1}")
                    
                    # Analyze where message flow breaks occur
                    flow_points_order = [
                        'orientation_request', 'orientation_processing', 'fcs_orientation_received',
                        'orientation_data_sent', 'orientation_response_received'
                    ]
                    
                    flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                    if flow_breaks:
                        logger.error(f"[TRACE::{self.test_id}] Message flow breaks:")
                        for break_msg in flow_breaks:
                            logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[TRACE::{self.test_id}] Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            
            if not success:
                # Prepare detailed error information
                error_details = []
                
                # Add information about flow breaks
                flow_points_order = [
                    'orientation_request', 'orientation_processing', 'fcs_orientation_received',
                    'orientation_data_sent', 'orientation_response_received'
                ]
                
                flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                if flow_breaks:
                    breaks = "\n".join(f"- {b}" for b in flow_breaks)
                    error_details.append(f"Message flow breaks:\n{breaks}")
                
                raise AssertionError(
                    f"FCS orientation data verification failed:\n{' '.join(error_details)}"
                )
            
            # Calculate verification statistics
            total_points = len(self.orientation_verification_points)
            matched_points = sum(1 for point in self.orientation_verification_points.values() if point['matched'])
            success_rate = (matched_points / total_points) * 100
            
            logger.info(f"[TRACE::{self.test_id}] Message flow verification: {matched_points}/{total_points} points ({success_rate:.1f}%)")
            logger.info(f"[TRACE::{self.test_id}] FCS orientation data test completed successfully")
            
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
            logger.error(f"[TRACE::{self.test_id}] Error in FCS orientation data test: {str(e)}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'trace_id': self.test_id,
                'timestamp': time.time()
            }

    async def test_status_request(self) -> Dict[str, Any]:
        """Test FCS status request functionality with detailed message tracing"""
        try:
            logger.info(f"[TRACE::{self.test_id}] Testing FCS status request with message tracing...")
            
            # Clear logs before starting
            self.log_capture.seek(0)
            self.log_capture.truncate()
            
            # Generate unique request ID for tracing through the system
            request_id = f"trace-{self.test_id}-{str(uuid.uuid4())[:8]}"
            logger.info(f"[TRACE::{self.test_id}] Using request ID: {request_id}")
            
            # Setup metadata for tracing
            metadata = {
                "request_id": request_id,
                "trace_id": self.test_id,
                "test_type": "status_request_tracing"
            }
            
            # Send status request
            logger.info(f"[TRACE::{self.test_id}] Sending status request")
            
            # Send request using the proper send_request API
            status_request_id = await self.fms_handler.send_request(
                system_name="flight_control_system",
                request_type="status",
                data={},  # No additional data needed for status request
                metadata=metadata
            )
            
            if not status_request_id:
                raise AssertionError("Failed to get status request ID")
            
            logger.info(f"[TRACE::{self.test_id}] Status request sent with ID: {status_request_id}")
            logger.info(f"[TRACE::{self.test_id}] Trace request ID: {request_id}")
            
            # Verify status request with message flow tracing
            max_retries = 3
            retry_delay = 1.0
            success = False
            detailed_result = {}
            
            # Wait for message propagation
            logger.info(f"[TRACE::{self.test_id}] Waiting for message propagation...")
            time.sleep(2.0)
            
            for attempt in range(max_retries):
                logger.info(f"[TRACE::{self.test_id}] Verification attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1.0)
                
                # Get logs
                log_output = self.log_capture.getvalue()
                
                # Verify status request with detailed tracing
                success, detailed_result = self._verify_message_flow(log_output, self.status_verification_points)
                
                if success:
                    logger.info(f"[TRACE::{self.test_id}] Verification succeeded on attempt {attempt + 1}")
                    break
                else:
                    logger.info(f"[TRACE::{self.test_id}] Verification failed on attempt {attempt + 1}")
                    
                    # Analyze where message flow breaks occur
                    flow_points_order = [
                        'status_request', 'status_processing', 'fcs_status_received',
                        'status_response_sent', 'status_response_received'
                    ]
                    
                    flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                    if flow_breaks:
                        logger.error(f"[TRACE::{self.test_id}] Message flow breaks:")
                        for break_msg in flow_breaks:
                            logger.error(f"[TRACE::{self.test_id}]   - {break_msg}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"[TRACE::{self.test_id}] Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
            
            if not success:
                # Prepare detailed error information
                error_details = []
                
                # Add information about flow breaks
                flow_points_order = [
                    'status_request', 'status_processing', 'fcs_status_received',
                    'status_response_sent', 'status_response_received'
                ]
                
                flow_breaks = self._analyze_message_flow_breaks(detailed_result, flow_points_order)
                if flow_breaks:
                    breaks = "\n".join(f"- {b}" for b in flow_breaks)
                    error_details.append(f"Message flow breaks:\n{breaks}")
                
                raise AssertionError(
                    f"FCS status request verification failed:\n{' '.join(error_details)}"
                )
            
            # Calculate verification statistics
            total_points = len(self.status_verification_points)
            matched_points = sum(1 for point in self.status_verification_points.values() if point['matched'])
            success_rate = (matched_points / total_points) * 100
            
            logger.info(f"[TRACE::{self.test_id}] Message flow verification: {matched_points}/{total_points} points ({success_rate:.1f}%)")
            logger.info(f"[TRACE::{self.test_id}] FCS status request test completed successfully")
            
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
            logger.error(f"[TRACE::{self.test_id}] Error in FCS status request test: {str(e)}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e),
                'trace_id': self.test_id,
                'timestamp': time.time()
            }

    async def run_tests(self):
        """Run all FCS system tests with enhanced tracing"""
        try:
            # Initialize system
            await self.initialize()
            
            # Run tests with message flow tracing
            mode_test_result = await self.test_fcs_mode_change()
            control_test_result = await self.test_control_input()
            orientation_test_result = await self.test_orientation_data()
            status_test_result = await self.test_status_request()
            
            # Report results
            logger.info(f"\n[TRACE::{self.test_id}] Test Results:")
            
            # Mode change test results
            if mode_test_result.get('success', False):
                success_rate = mode_test_result.get('success_rate', 0)
                logger.info(f"[TRACE::{self.test_id}] FCS Mode Change Test: PASSED ({success_rate:.1f}% of verification points)")
            else:
                logger.error(f"[TRACE::{self.test_id}] FCS Mode Change Test: FAILED")
                if 'error' in mode_test_result:
                    logger.error(f"[TRACE::{self.test_id}] Error: {mode_test_result['error']}")
            
            # Control input test results
            if control_test_result.get('success', False):
                success_rate = control_test_result.get('success_rate', 0)
                logger.info(f"[TRACE::{self.test_id}] FCS Control Input Test: PASSED ({success_rate:.1f}% of verification points)")
            else:
                logger.error(f"[TRACE::{self.test_id}] FCS Control Input Test: FAILED")
                if 'error' in control_test_result:
                    logger.error(f"[TRACE::{self.test_id}] Error: {control_test_result['error']}")
            
            # Orientation data test results
            if orientation_test_result.get('success', False):
                success_rate = orientation_test_result.get('success_rate', 0)
                logger.info(f"[TRACE::{self.test_id}] FCS Orientation Data Test: PASSED ({success_rate:.1f}% of verification points)")
            else:
                logger.error(f"[TRACE::{self.test_id}] FCS Orientation Data Test: FAILED")
                if 'error' in orientation_test_result:
                    logger.error(f"[TRACE::{self.test_id}] Error: {orientation_test_result['error']}")
            
            # Status request test results
            if status_test_result.get('success', False):
                success_rate = status_test_result.get('success_rate', 0)
                logger.info(f"[TRACE::{self.test_id}] FCS Status Request Test: PASSED ({success_rate:.1f}% of verification points)")
            else:
                logger.error(f"[TRACE::{self.test_id}] FCS Status Request Test: FAILED")
                if 'error' in status_test_result:
                    logger.error(f"[TRACE::{self.test_id}] Error: {status_test_result['error']}")
            
            # Calculate overall success
            overall_success = all([
                mode_test_result.get('success', False),
                control_test_result.get('success', False),
                orientation_test_result.get('success', False),
                status_test_result.get('success', False)
            ])
            
            # Overall test result
            logger.info(f"[TRACE::{self.test_id}] Overall FCS System Test: {'PASSED' if overall_success else 'FAILED'}")
            
            return overall_success
            
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
    test_instance = TestFlightControlSystem()
    result = asyncio.run(test_instance.run_tests())
    return result

if __name__ == '__main__':
    # This test is designed to be run from the user CLI
    # It should not be run directly as it requires the system to be initialized
    logger.warning("This test should be run via the user CLI 'test' command")
    sys.exit(1)
