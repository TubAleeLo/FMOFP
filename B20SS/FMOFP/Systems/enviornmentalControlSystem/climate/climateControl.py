import sys
import FMOFP.Utils.common.fetching as fetching
from FMOFP.Utils.logger.sys_logger import get_logger

# NOTE: previously imported FMOFP.local_messaging.Messaging.Messaging and
# called sys_logger(name) as a constructor -- neither exists anywhere in
# the codebase (Messaging was superseded by the local_messaging routing/
# handler system entirely; sys_logger only exposes get_logger()). This
# raised ModuleNotFoundError on every import, making this class entirely
# unreachable. Confirmed live. This class isn't currently instantiated
# anywhere else in the codebase (dead code today), so the bug had no live
# impact, but it's fixed here so the class actually works if/when wired up.
logger = get_logger()

class ClimateControl:
    def __init__(self):
        self.current_temperature = 22.0
        self.current_humidity = 50.0

    def adjust_temperature(self, target_temperature):
        logger.info(f"Adjusting temperature from {self.current_temperature}°C to {target_temperature}°C")
        # Simulating temperature adjustment
        self.current_temperature = target_temperature
        
    def adjust_humidity(self, target_humidity):
        logger.info(f"Adjusting humidity from {self.current_humidity}% to {target_humidity}%")
        # Simulating humidity adjustment
        self.current_humidity = target_humidity
        
    def get_climate_status(self):
        return {
            "temperature": self.current_temperature,
            "humidity": self.current_humidity
        }

    def handle_message(self, message):
        if message.get("type") == "adjust_temperature":
            self.adjust_temperature(message["target_temperature"])
        elif message.get("type") == "adjust_humidity":
            self.adjust_humidity(message["target_humidity"])
        elif message.get("type") == "get_status":
            return self.get_climate_status()