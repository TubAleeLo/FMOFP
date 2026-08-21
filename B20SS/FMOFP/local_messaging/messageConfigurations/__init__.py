"""
Message Configurations Package

Initializes and registers all message types.
"""
import FMOFP.Utils.common.fetching as fetching
from FMOFP.local_messaging.messageConfigurations.base_message import register_message_type
from FMOFP.local_messaging.messageConfigurations.WeatherRadarEchoTopData import WeatherRadarEchoTopData
from FMOFP.local_messaging.messageConfigurations.WeatherRadarShearData import WeatherRadarShearData
from FMOFP.local_messaging.messageConfigurations.WeatherRadarTurbulenceData import WeatherRadarTurbulenceData
from FMOFP.local_messaging.messageConfigurations.WeatherRadarVILData import WeatherRadarVILData

# Register weather radar data message types
register_message_type("echo_top_data", WeatherRadarEchoTopData)
register_message_type("shear_data", WeatherRadarShearData)
register_message_type("turbulence_data", WeatherRadarTurbulenceData)
register_message_type("vil_data", WeatherRadarVILData)
