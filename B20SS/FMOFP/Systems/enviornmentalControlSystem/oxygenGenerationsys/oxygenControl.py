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

class OxygenControl:
    def __init__(self):
        self.oxygen_level = 21.0  # Normal atmospheric oxygen level
        self.oxygen_generation_rate = 1.0  # L/min

    def generate_oxygen(self):
        logger.info(f"Generating oxygen at {self.oxygen_generation_rate} L/min")
        # Simulating oxygen generation
        self.oxygen_level += 0.1  # Increase oxygen level slightly
        if self.oxygen_level > 23.0:
            self.oxygen_level = 23.0  # Cap at 23% to prevent hyperoxia
        
    def adjust_generation_rate(self, new_rate):
        logger.info(f"Adjusting oxygen generation rate from {self.oxygen_generation_rate} to {new_rate} L/min")
        self.oxygen_generation_rate = new_rate

    def get_oxygen_status(self):
        return {
            "oxygen_level": self.oxygen_level,
            "generation_rate": self.oxygen_generation_rate
        }

    def handle_message(self, message):
        if message.get("type") == "generate_oxygen":
            self.generate_oxygen()
        elif message.get("type") == "adjust_generation_rate":
            self.adjust_generation_rate(message["new_rate"])
        elif message.get("type") == "get_status":
            return self.get_oxygen_status()