import sys
import FMOFP.Utils.common.fetching as fetching
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class MissionData:
    def __init__(self):
        self.mission_objectives = []
        self.rules_of_engagement = []
        self.intelligence_data = {}

    def set_mission_objectives(self, objectives):
        self.mission_objectives = objectives
        logger.info(f"[MissionData] Mission objectives updated: {objectives}")

    def set_rules_of_engagement(self, rules):
        self.rules_of_engagement = rules
        logger.info(f"[MissionData] Rules of engagement updated: {rules}")

    def add_intelligence_data(self, data):
        self.intelligence_data.update(data)
        logger.info(f"[MissionData] Intelligence data updated: {data}")

    def get_mission_data(self):
        return {
            "mission_objectives": self.mission_objectives,
            "rules_of_engagement": self.rules_of_engagement,
            "intelligence_data": self.intelligence_data
        }

    def handle_message(self, message):
        if message.get("type") == "set_mission_objectives":
            self.set_mission_objectives(message.get("objectives"))
        elif message.get("type") == "set_rules_of_engagement":
            self.set_rules_of_engagement(message.get("rules"))
        elif message.get("type") == "add_intelligence_data":
            self.add_intelligence_data(message.get("data"))
        elif message.get("type") == "get_mission_data":
            return self.get_mission_data()

    def _dict_to_xml(self, tag, d):
        elem = ET.Element(tag)
        for key, val in d.items():
            child = ET.Element(key)
            child.text = str(val)
            elem.append(child)
        return ET.tostring(elem, encoding='unicode')

    def _xml_to_dict(self, xml_string):
        root = ET.fromstring(xml_string)
        return {child.tag: child.text for child in root}

# Example usage
if __name__ == "__main__":
    mission_data = MissionData()
    mission_data.set_mission_objectives(["Destroy Enemy SAM Site", "Provide Close Air Support"])
    mission_data.set_rules_of_engagement(["Weapon Free Zone", "Identify Targets Visually"])
    mission_data.add_intelligence_data({
        "enemy_positions": [(34.0522, -118.2437, 0)],
        "weather": "Clear Skies"
    })
    logger.info(mission_data.get_mission_data())
