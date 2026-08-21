"""
Test script for the WeatherRadarHolographicDisplay class.

This script tests the initialization of the WeatherRadarHolographicDisplay class
to ensure that it properly initializes without any AttributeError exceptions.
"""
import sys
import os
import asyncio
from PyQt6.QtWidgets import QApplication

# Add parent directory to path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the class to test
from FMOFP.Interfaces.userInterface.displays.radar.weather_radar_holographic_display import WeatherRadarHolographicDisplay
from Utils.logger.sys_logger import get_logger

logger = get_logger()

async def test_initialization():
    """Test the initialization of the WeatherRadarHolographicDisplay class."""
    logger.info("Starting test_initialization")
    
    try:
        # Create the display
        display = WeatherRadarHolographicDisplay()
        logger.info("Successfully created WeatherRadarHolographicDisplay instance")
        
        # Test that the required attributes exist
        required_attributes = [
            'holo_rotation',
            'holo_rotation_speed',
            'holo_elevation',
            'holo_perspective',
            'holo_layer_separation',
            'holo_layers'
        ]
        
        for attr in required_attributes:
            if hasattr(display, attr):
                logger.info(f"Attribute '{attr}' exists with value: {getattr(display, attr)}")
            else:
                logger.error(f"Attribute '{attr}' does not exist")
                
        # Initialize the display
        await display.initialize_display()
        logger.info("Successfully initialized display")
        
        return True
    except Exception as e:
        logger.error(f"Error in test_initialization: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main function to run the test."""
    # Create QApplication instance
    app = QApplication(sys.argv)
    
    # Run the test
    success = await test_initialization()
    
    if success:
        logger.info("Test completed successfully")
        return 0
    else:
        logger.error("Test failed")
        return 1

if __name__ == "__main__":
    # Run the main function
    loop = asyncio.get_event_loop()
    exit_code = loop.run_until_complete(main())
    sys.exit(exit_code)
