"""
Test script to verify the fix for precipitation data being properly transferred 
between BC and RT using the new RT_transfer_aggregator.
"""

import sys
import os
import uuid
import time
import logging
import traceback

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.MIL_STD_1553B.Bus_Controller.BC import get_Bus_Controller
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT import get_Remote_Terminal
from FMOFP.MIL_STD_1553B.Remote_Terminal.RT_messaging.RT_transfer_aggregator import get_rt_transfer_aggregator

logger = get_logger()

def setup_logging():
    """Set up logging with enhanced detail for data transfer debugging"""
    # get_logger() returns the SysLogger singleton, a thin wrapper around a
    # stdlib logging.Logger (stored as .root_logger) -- it doesn't expose
    # setLevel()/addHandler() itself, only debug()/info()/warning()/etc.
    # Calling logger.setLevel() directly raised AttributeError immediately
    # at import time, before any of this file's actual test logic ever ran
    # (confirmed live: 'AttributeError: SysLogger object has no attribute
    # setLevel'). Go through .root_logger, matching how the rest of the
    # codebase configures this same singleton.
    logger.root_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.root_logger.addHandler(handler)
    logger.info("Detailed logging configured")

def create_test_precipitation_data():
    """Create sample precipitation data for testing"""
    # Create a list of precipitation data objects with realistic values
    precip_objects = []
    
    for i in range(5):  # Create 5 test objects
        x_coord = (i - 2) * 5  # Range from -10 to 10
        y_coord = (i - 2) * 4  # Range from -8 to 8
        
        # Alternate between rain and snow
        precip_type = "rain" if i % 2 == 0 else "snow"
        
        # Create realistic rate and intensity values
        rate = (i + 1) * 2.5  # Range from 2.5 to 12.5
        intensity = min(1.0, (i + 1) * 0.2)  # Range from 0.2 to 1.0
        
        # Create precipitation data object
        precip_obj = {
            "position": (x_coord, y_coord),
            "type": precip_type,
            "rate": rate,
            "intensity": intensity,
            "show_values": intensity > 0.5
        }
        
        precip_objects.append(precip_obj)
    
    return precip_objects

def create_test_frames(precip_obj):
    """Build (frames, metadata, request_id) for one precipitation reading.

    NOTE: this replaces an earlier create_binary_data_message() that hand-
    rolled a fake binary payload and wrapped it in a MIL_STD_1553B_Message
    object, then passed that whole object to Bus_Controller.send_message().
    That method's real signature is send_message(frames, request_id,
    metadata) where frames[0] is a 16-bit binary command word string and
    frames[1:] are 16-bit binary data word strings -- it feeds into
    Messaging.py's send1553Msg.send_message() -> _sendCommandComms(), which
    parses the command word's RT address/T-R/subaddress/word-count bits and
    encodes real sync+parity frames onto the wire. Passing a whole message
    object there never worked; there is no shortcut that accepts one.
    RT.py reconstructs a fresh MIL_STD_1553B_Message from what actually
    arrives over the socket (rt_address, sub_address, decoded data,
    message_type, command_type -- see RT.py's process_frames_loop), so the
    round-trip has to go through the real wire encoding on both ends.
    This builds a properly-encoded frame list using the same command-word
    map and PrecipitationData wire encoding production code uses, instead
    of an ad hoc integer packing scheme that was never actually decoded by
    anything on the receiving side.
    """
    from FMOFP.local_messaging.command_word_map import WEATHER_RADAR_PRECIPITATION_DATA_RESPONSE
    from FMOFP.Systems.radarManagement.radar_messaging.message_definitions.weather_data import PrecipitationData

    request_id = str(uuid.uuid4())

    precip_data = PrecipitationData(
        position=precip_obj["position"],
        type=precip_obj["type"],
        rate=precip_obj["rate"],
        intensity=precip_obj["intensity"],
        show_values=precip_obj["show_values"],
        request_id=request_id,
    )
    data_words = precip_data.to_data_words()  # 2 x 16-bit binary strings

    frames = [WEATHER_RADAR_PRECIPITATION_DATA_RESPONSE] + data_words
    metadata = {
        'command_type': 'precipitation_data',
        'message_type': 'weather_radarPrecipitationResponse',
        'precipitation_message': True,
        'data_type': 'precipitation',
    }

    return frames, metadata, request_id

def test_rt_transfer_aggregator_integration():
    """Test the integration of RT_transfer_aggregator with RT message flow"""
    logger.info("Starting RT transfer aggregator integration test")
    
    try:
        # Create test data -- use the first generated reading as the single
        # precipitation data point sent over the wire (each 1553B
        # precipitation response frame carries one reading's worth of data:
        # 2 data words, per WEATHER_DATA_TYPES word_count in
        # command_word_map.py, matching PrecipitationData.to_data_words()).
        precip_objects = create_test_precipitation_data()
        logger.info(f"Created {len(precip_objects)} test precipitation objects")
        test_obj = precip_objects[0]

        # Build the real command word + data words + metadata for this reading
        frames, metadata, request_id = create_test_frames(test_obj)
        logger.info(f"Created test frames: command={frames[0]}, {len(frames) - 1} data word(s)")
        
        # Initialize RT and BC
        bc = get_Bus_Controller()
        rt = get_Remote_Terminal()
        
        # Start RT listener
        rt.start_listener()
        logger.info("Started RT listener")
        
        # Get RT transfer aggregator
        rt_aggregator = get_rt_transfer_aggregator()
        logger.info("Got RT transfer aggregator instance")
        
        # Send test message from BC to RT
        #
        # Bus_Controller.send_message() is `async def` -- calling it bare
        # like this creates a coroutine object and immediately discards it
        # without ever running its body, so the message was never actually
        # sent (confirmed live: 'RuntimeWarning: coroutine
        # Bus_Controller.send_message was never awaited', and RT then
        # reports "No message was processed by RT" every time, since BC
        # never sent anything for it to receive). This function
        # (test_rt_transfer_aggregator_integration) is synchronous and is
        # invoked directly (not from inside a running event loop), so
        # asyncio.run() is the correct way to actually execute the
        # coroutine here.
        logger.info("Sending test message from BC to RT")
        import asyncio as _asyncio
        _asyncio.run(bc.send_message(frames, request_id=request_id, metadata=metadata))
        
        # Wait a bit for processing
        time.sleep(1)
        
        # VERIFICATION: Check if RT received and processed the message
        logger.info("Checking if RT processed the message")
        
        # Wait for up to 5 seconds for a message to appear
        max_wait = 5
        processed_message = None
        
        for i in range(max_wait):
            # Check for processed messages
            logger.info(f"Checking for processed messages (attempt {i+1}/{max_wait})")
            
            with rt.rt_listener.message_lock:
                if rt.rt_listener.processed_messages:
                    processed_message = rt.rt_listener.processed_messages.pop(0)
                    logger.info(f"Found processed message: {processed_message}")
                    break
            
            # Wait before checking again
            time.sleep(1)
        
        # Verify the processed message
        if processed_message:
            logger.info("✅ Message received and processed by RT")
            
            # Check data preservation. MIL_STD_1553B_Message.data is always
            # a binary string (not a list -- __init__ concatenates data
            # words into one string: "Convert list of integers to binary
            # string"), so the correct check is string length, not list
            # length. Each data word is DATA_WORD_SIZE (16) bits, and we
            # sent 2 data words (a precipitation reading is always encoded
            # as exactly 2 words -- see PrecipitationData.to_data_words()).
            data_word_count = len(frames) - 1
            expected_data_bits = data_word_count * 16
            if hasattr(processed_message, 'data') and isinstance(processed_message.data, str) and processed_message.data:
                data_len = len(processed_message.data)
                logger.info(f"Received data length (bits): {data_len}")
                logger.info(f"Expected data length (bits): {expected_data_bits}")
                
                if data_len == expected_data_bits:
                    logger.info("✅ Data length preserved correctly")
                    logger.info(f"Received data: {processed_message.data}")
                else:
                    logger.error(f"❌ Data length mismatch: received {data_len} bits, expected {expected_data_bits} bits")
            else:
                logger.error("❌ No data found in processed message")
            
            # Check metadata preservation. RT.py's message-reconstruction
            # code (process_frames_loop / process_complete_block_transfer)
            # never builds a nested `.metadata` dict on the reconstructed
            # message -- it does `for key, value in metadata.items():
            # setattr(message, key, value)`, splatting each metadata key
            # onto the message object directly as its own attribute. So
            # 'precipitation_message' and 'data_type' show up as
            # processed_message.precipitation_message /
            # processed_message.data_type, not inside processed_message.metadata
            # (processed_message.metadata is a separate dict that
            # MIL_STD_1553B_Message.__init__ always creates, populated only
            # with rt_address/sub_address/command_type/etc. -- confirmed
            # live it comes back empty of these two keys).
            for key in ['precipitation_message', 'data_type']:
                if hasattr(processed_message, key):
                    logger.info(f"✅ Metadata '{key}' preserved: {getattr(processed_message, key)}")
                else:
                    logger.error(f"❌ Metadata '{key}' missing")
            
            # Check command type preservation
            if hasattr(processed_message, 'command_type') and processed_message.command_type == metadata['command_type']:
                logger.info(f"✅ Command type preserved: {processed_message.command_type}")
            else:
                logger.error(f"❌ Command type mismatch: {getattr(processed_message, 'command_type', None)} vs expected {metadata['command_type']}")
        else:
            logger.error("❌ No message was processed by RT")
        
        # Stop RT listener
        rt.stop_listener()
        logger.info("Stopped RT listener")
        
        return processed_message is not None
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    setup_logging()
    logger.info("Starting precipitation data transfer test")
    
    success = test_rt_transfer_aggregator_integration()
    
    if success:
        logger.info("TEST PASSED: RT transfer aggregator integration test successful!")
        sys.exit(0)
    else:
        logger.error("TEST FAILED: RT transfer aggregator integration test failed")
        sys.exit(1)
