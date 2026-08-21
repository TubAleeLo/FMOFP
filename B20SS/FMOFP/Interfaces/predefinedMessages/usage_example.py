"""
Usage Example for the Predefined Messages System

This module demonstrates how to use the predefined messages system 
to send messages to various systems in the FMOFP system.
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Optional

# Import the Messages class and singleton
from FMOFP.Interfaces.predefinedMessages.Messages import Messages, get_messages

# Import radar enums for mode settings
from FMOFP.Interfaces.predefinedMessages.radar_enums import (
    weather_radarMode,
    tfr_radarMode,
    sar_radarMode,
    targeting_radarMode,
    aewc_radarMode
)

# Import logging utilities
from FMOFP.Utils.logger.sys_logger import get_logger

# Create logger
logger = get_logger()

async def example_weather_radar_messages():
    """Example of using Weather Radar predefined messages"""
    logger.info("=== Weather Radar Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Change radar mode
    logger.info("Example 1: Changing Weather Radar to SURVEILLANCE mode")
    request_id = await messages.set_weather_radar_mode(weather_radarMode.SURVEILLANCE)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change to take effect
    await asyncio.sleep(1.0)
    
    # Example 2: Request precipitation data
    logger.info("Example 2: Requesting precipitation data")
    scan_parameters = {
        "azimuth_start": 0,
        "azimuth_end": 90,
        "elevation": 0,
        "range": 100
    }
    request_id = await messages.request_precipitation_data(scan_parameters)
    logger.info(f"Precipitation data request sent with ID: {request_id}")
    
    # Wait for data processing
    await asyncio.sleep(1.0)
    
    # Example 3: Request VIL data
    logger.info("Example 3: Requesting VIL data")
    request_id = await messages.request_vil_data(scan_parameters)
    logger.info(f"VIL data request sent with ID: {request_id}")
    
    logger.info("Weather Radar message examples completed")

async def example_tfr_radar_messages():
    """Example of using TFR Radar predefined messages"""
    logger.info("=== TFR Radar Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Change radar mode
    logger.info("Example 1: Changing TFR Radar to ACTIVE mode")
    request_id = await messages.set_tfr_radar_mode(tfr_radarMode.ACTIVE)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change to take effect
    await asyncio.sleep(1.0)
    
    # Example 2: Request elevation data
    logger.info("Example 2: Requesting elevation data")
    scan_parameters = {
        "azimuth": 45,
        "range": 50,
        "resolution": "high"
    }
    request_id = await messages.request_elevation_data(scan_parameters)
    logger.info(f"Elevation data request sent with ID: {request_id}")
    
    logger.info("TFR Radar message examples completed")

async def example_sar_radar_messages():
    """Example of using SAR Radar predefined messages"""
    logger.info("=== SAR Radar Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Change radar mode
    logger.info("Example 1: Changing SAR Radar to STRIPMAP mode")
    request_id = await messages.set_sar_radar_mode(sar_radarMode.STRIPMAP)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change to take effect
    await asyncio.sleep(1.0)
    
    # Example 2: Request imagery data
    logger.info("Example 2: Requesting imagery data")
    scan_parameters = {
        "area": {
            "lat_start": 35.0,
            "lon_start": -120.0,
            "lat_end": 36.0,
            "lon_end": -119.0
        },
        "resolution": "medium"
    }
    request_id = await messages.request_imagery_data(scan_parameters)
    logger.info(f"Imagery data request sent with ID: {request_id}")
    
    logger.info("SAR Radar message examples completed")

async def example_targeting_radar_messages():
    """Example of using Targeting Radar predefined messages"""
    logger.info("=== Targeting Radar Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Change radar mode
    logger.info("Example 1: Changing Targeting Radar to TRACKING mode")
    request_id = await messages.set_targeting_radar_mode(targeting_radarMode.TRACKING)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change to take effect
    await asyncio.sleep(1.0)
    
    # Example 2: Request track data
    logger.info("Example 2: Requesting track data")
    track_parameters = {
        "sector": {
            "azimuth_start": 0,
            "azimuth_end": 45,
            "elevation": 10
        },
        "filters": {
            "min_rcs": 0.5,
            "max_range": 100
        }
    }
    request_id = await messages.request_track_data(track_parameters)
    logger.info(f"Track data request sent with ID: {request_id}")
    
    # Wait for data processing
    await asyncio.sleep(1.0)
    
    # Example 3: Request lock on target
    logger.info("Example 3: Requesting lock on target")
    track_id = "TGT-12345"  # This would be a real track ID from a track response
    lock_parameters = {
        "lock_type": "hard",
        "priority": "high"
    }
    request_id = await messages.request_targeting_radar_lock(track_id, lock_parameters)
    logger.info(f"Lock request sent with ID: {request_id}")
    
    logger.info("Targeting Radar message examples completed")

async def example_aewc_radar_messages():
    """Example of using AEWC Radar predefined messages"""
    logger.info("=== AEWC Radar Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Change radar mode
    logger.info("Example 1: Changing AEWC Radar to SURVEILLANCE mode")
    request_id = await messages.set_aewc_radar_mode(aewc_radarMode.SURVEILLANCE)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change to take effect
    await asyncio.sleep(1.0)
    
    # Example 2: Request sector scan
    logger.info("Example 2: Requesting sector scan")
    request_id = await messages.request_sector_scan(
        azimuth_start=270,
        azimuth_end=360,
        elevation=5
    )
    logger.info(f"Sector scan request sent with ID: {request_id}")
    
    logger.info("AEWC Radar message examples completed")

async def example_fcs_messages():
    """Example of using FCS predefined messages"""
    logger.info("=== FCS Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Control surface change
    logger.info("Example 1: Requesting control surface change")
    request_id = await messages.request_control_surface_change(
        surface_name="aileron",
        position=15.0,
        rate=5.0
    )
    logger.info(f"Control surface change request sent with ID: {request_id}")
    
    # Wait for command processing
    await asyncio.sleep(1.0)
    
    # Example 2: Flight mode change
    logger.info("Example 2: Requesting flight mode change")
    mode_params = {
        "flaps": 30,
        "gear": "down"
    }
    request_id = await messages.request_flight_mode_change(
        mode_name="approach",
        mode_params=mode_params
    )
    logger.info(f"Flight mode change request sent with ID: {request_id}")
    
    # Wait for command processing
    await asyncio.sleep(1.0)
    
    # Example 3: Autopilot command
    logger.info("Example 3: Requesting autopilot command")
    request_id = await messages.request_autopilot_command(
        command_type="altitude_hold",
        target_value=35000
    )
    logger.info(f"Autopilot command sent with ID: {request_id}")
    
    logger.info("FCS message examples completed")

async def example_fms_messages():
    """Example of using FMS predefined messages"""
    logger.info("=== FMS Message Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example 1: Navigation update
    logger.info("Example 1: Sending navigation update")
    request_id = await messages.request_navigation_update(
        latitude=35.12345,
        longitude=-120.98765,
        altitude=30000,
        heading=270.0,
        airspeed=450.0
    )
    logger.info(f"Navigation update request sent with ID: {request_id}")
    
    # Wait for update processing
    await asyncio.sleep(1.0)
    
    # Example 2: Attitude update
    logger.info("Example 2: Sending attitude update")
    request_id = await messages.request_attitude_update(
        pitch=2.5,
        roll=5.0,
        yaw=180.0
    )
    logger.info(f"Attitude update request sent with ID: {request_id}")
    
    # Wait for update processing
    await asyncio.sleep(1.0)
    
    # Example 3: Maneuver request
    logger.info("Example 3: Requesting maneuver")
    maneuver_params = {
        "heading": 310.0,
        "altitude": 35000,
        "speed": 400.0,
        "turn_rate": 2.0
    }
    request_id = await messages.request_maneuver(
        maneuver_type="heading_change",
        maneuver_params=maneuver_params
    )
    logger.info(f"Maneuver request sent with ID: {request_id}")
    
    logger.info("FMS message examples completed")

async def example_combined_operations():
    """Example of combined operations using multiple systems"""
    logger.info("=== Combined Operations Examples ===")
    
    # Get the global Messages instance
    messages = get_messages()
    
    # Initialize the Messages system (if not already initialized)
    await messages.initialize()
    
    # Example: Weather data acquisition and flight path adjustment
    logger.info("Example: Weather data acquisition and flight path adjustment")
    
    # 1. Set weather radar to surveillance mode
    logger.info("1. Setting weather radar to surveillance mode")
    request_id = await messages.set_weather_radar_mode(weather_radarMode.SURVEILLANCE)
    logger.info(f"Mode change request sent with ID: {request_id}")
    
    # Wait for mode change
    await asyncio.sleep(1.0)
    
    # 2. Request precipitation data
    logger.info("2. Requesting precipitation data")
    scan_parameters = {
        "azimuth_start": 0,
        "azimuth_end": 90,
        "elevation": 0,
        "range": 100
    }
    request_id = await messages.request_precipitation_data(scan_parameters)
    logger.info(f"Precipitation data request sent with ID: {request_id}")
    
    # Wait for data processing
    await asyncio.sleep(1.0)
    
    # 3. Modify flight path based on weather data (simulated)
    logger.info("3. Adjusting flight path to avoid weather")
    
    # 4. Send new navigation parameters to FMS
    logger.info("4. Sending updated navigation parameters to FMS")
    request_id = await messages.request_navigation_update(
        latitude=34.98765,
        longitude=-121.12345,
        altitude=32000,
        heading=285.0,
        airspeed=430.0
    )
    logger.info(f"Navigation update request sent with ID: {request_id}")
    
    # 5. Request autopilot engagement to follow new path
    logger.info("5. Engaging autopilot to follow new path")
    request_id = await messages.request_autopilot_command(
        command_type="nav_follow",
        target_value="active_route"
    )
    logger.info(f"Autopilot command sent with ID: {request_id}")
    
    logger.info("Combined operations example completed")

async def run_examples():
    """Run all examples"""
    try:
        # Get the global Messages instance
        messages = get_messages()
        
        # Initialize the Messages system
        await messages.initialize()
        logger.info("Messages system initialized successfully")
        
        # Run examples for each system
        await example_weather_radar_messages()
        await asyncio.sleep(1.0)  # Pause between examples
        
        await example_tfr_radar_messages()
        await asyncio.sleep(1.0)
        
        await example_sar_radar_messages()
        await asyncio.sleep(1.0)
        
        await example_targeting_radar_messages()
        await asyncio.sleep(1.0)
        
        await example_aewc_radar_messages()
        await asyncio.sleep(1.0)
        
        await example_fcs_messages()
        await asyncio.sleep(1.0)
        
        await example_fms_messages()
        await asyncio.sleep(1.0)
        
        await example_combined_operations()
        
        logger.info("All examples completed successfully")
        
    except Exception as e:
        logger.error(f"Error running examples: {e}")
        import traceback
        logger.error(traceback.format_exc())

def main():
    """Main entry point for running examples"""
    try:
        asyncio.run(run_examples())
    except KeyboardInterrupt:
        logger.info("Examples stopped by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    # This example is designed to be run when the system is already initialized
    # from another part of the FMOFP system, as it requires message handlers
    # to be set up correctly.
    logger.warning("This example requires a running FMOFP system to function correctly.")
    logger.warning("Run this example through the system's CLI or test harness.")
    sys.exit(0)
