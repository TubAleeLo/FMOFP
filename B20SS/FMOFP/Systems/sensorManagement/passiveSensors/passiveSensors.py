import sys
import FMOFP.Utils.common.fetching as fetching
import random
import math
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class PassiveSensor:
    def __init__(self, name, sensitivity, field_of_view):
        self.name = name
        self.sensitivity = sensitivity
        self.field_of_view = field_of_view
        self.is_active = False

    def activate(self):
        self.is_active = True

    def deactivate(self):
        self.is_active = False

    def get_status(self):
        return {
            "name": self.name,
            "is_active": self.is_active,
            "sensitivity": self.sensitivity,
            "field_of_view": self.field_of_view
        }

class InfraredSensor(PassiveSensor):
    def __init__(self, name, sensitivity, field_of_view, wavelength_range):
        super().__init__(name, sensitivity, field_of_view)
        self.wavelength_range = wavelength_range

    def detect(self):
        if not self.is_active:
            return None
        # Simulate infrared detection
        detected_objects = []
        for _ in range(random.randint(0, 3)):
            temperature = random.uniform(0, 1000)
            angle = random.uniform(-self.field_of_view/2, self.field_of_view/2)
            distance = random.uniform(100, 10000)
            detected_objects.append({
                "temperature": temperature,
                "angle": angle,
                "distance": distance
            })
        return detected_objects

class ESMSensor(PassiveSensor):
    def __init__(self, name, sensitivity, field_of_view, frequency_range):
        super().__init__(name, sensitivity, field_of_view)
        self.frequency_range = frequency_range

    def detect(self):
        if not self.is_active:
            return None
        # Simulate ESM detection
        detected_signals = []
        for _ in range(random.randint(0, 5)):
            frequency = random.uniform(self.frequency_range[0], self.frequency_range[1])
            signal_strength = random.uniform(-120, -20)  # dBm
            bearing = random.uniform(0, 360)
            detected_signals.append({
                "frequency": frequency,
                "signal_strength": signal_strength,
                "bearing": bearing
            })
        return detected_signals

class PassiveSensorManager:
    def __init__(self):
        self.sensors = {
            "forward_looking_infrared": InfraredSensor("Forward Looking Infrared", 0.1, 60, (8e-6, 14e-6)),  # 60° FOV, 8-14 µm
            "missile_approach_warning": InfraredSensor("Missile Approach Warning", 0.05, 360, (3e-6, 5e-6)),  # 360° FOV, 3-5 µm
            "electronic_support_measures": ESMSensor("Electronic Support Measures", 0.01, 360, (0.5e9, 40e9))  # 360° FOV, 0.5-40 GHz
        }

    def activate_sensor(self, sensor_name):
        if sensor_name in self.sensors:
            self.sensors[sensor_name].activate()
            logger.info(f"[PassiveSensors] Activated {sensor_name}")
        else:
            logger.warning(f"[PassiveSensors] Sensor {sensor_name} not found")

    def deactivate_sensor(self, sensor_name):
        if sensor_name in self.sensors:
            self.sensors[sensor_name].deactivate()
            logger.info(f"[PassiveSensors] Deactivated {sensor_name}")
        else:
            logger.warning(f"[PassiveSensors] Sensor {sensor_name} not found")

    def get_sensor_data(self, sensor_name):
        if sensor_name in self.sensors:
            sensor = self.sensors[sensor_name]
            if isinstance(sensor, InfraredSensor) or isinstance(sensor, ESMSensor):
                return sensor.detect()
            else:
                logger.warning(f"[PassiveSensors] Sensor {sensor_name} does not support detection")
        else:
            logger.warning(f"[PassiveSensors] Sensor {sensor_name} not found")
        return None

    def get_all_sensor_statuses(self):
        return {name: sensor.get_status() for name, sensor in self.sensors.items()}

    def handle_message(self, message):
        if message.get("type") == "activate_sensor":
            self.activate_sensor(message.get("sensor_name"))
        elif message.get("type") == "deactivate_sensor":
            self.deactivate_sensor(message.get("sensor_name"))
        elif message.get("type") == "get_sensor_data":
            return self.get_sensor_data(message.get("sensor_name"))
        elif message.get("type") == "get_all_sensor_statuses":
            return self.get_all_sensor_statuses()

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
    psm = PassiveSensorManager()
    psm.activate_sensor("forward_looking_infrared")
    logger.info(psm.get_sensor_data("forward_looking_infrared"))
    logger.info(psm.get_all_sensor_statuses())
    psm.deactivate_sensor("forward_looking_infrared")
