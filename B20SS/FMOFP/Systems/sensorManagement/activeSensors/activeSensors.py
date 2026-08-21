import sys
import FMOFP.Utils.common.fetching as fetching
#from FMOFP.local_messaging.Messaging import Messaging
import random
import math
import xml.etree.ElementTree as ET
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class ActiveSensor:
    def __init__(self, name, range, accuracy):
        self.name = name
        self.range = range
        self.accuracy = accuracy
        self.is_active = False

    def activate(self):
        self.is_active = True

    def deactivate(self):
        self.is_active = False

    def get_status(self):
        return {
            "name": self.name,
            "is_active": self.is_active,
            "range": self.range,
            "accuracy": self.accuracy
        }

class Radar(ActiveSensor):
    def __init__(self, name, range, accuracy, frequency):
        super().__init__(name, range, accuracy)
        self.frequency = frequency

    def scan(self):
        if not self.is_active:
            return None
        # Simulate radar scan
        detected_objects = []
        for _ in range(random.randint(0, 5)):
            distance = random.uniform(0, self.range)
            angle = random.uniform(0, 360)
            speed = random.uniform(0, 1000)
            detected_objects.append({
                "distance": distance,
                "angle": angle,
                "speed": speed
            })
        return detected_objects

class Lidar(ActiveSensor):
    def __init__(self, name, range, accuracy, pulse_rate):
        super().__init__(name, range, accuracy)
        self.pulse_rate = pulse_rate

    # Real LIDAR units emit on the order of pulse_rate pulses/second, but
    # scan() simulates discrete processed detections returned per poll, not
    # raw pulses. Looping range(self.pulse_rate) here used to generate up to
    # 1,000,000 point-cloud entries per call (pulse_rate == 1_000_000 for the
    # bundled LIDAR spec), which made SensorDataFusion._merge_or_add()'s
    # O(n) per-contact gate check blow up to O(n^2) over up to a million
    # entries -- in practice an indefinite hang of the sensor poll thread the
    # first time the LIDAR sensor was activated and scanned (production
    # readiness punch list, item 3 audit). Bounded to a small number of
    # simulated detections per scan, matching Radar.scan()'s density.
    MAX_DETECTIONS_PER_SCAN = 5

    def scan(self):
        if not self.is_active:
            return None
        # Simulate lidar scan
        point_cloud = []
        for _ in range(random.randint(0, self.MAX_DETECTIONS_PER_SCAN)):
            distance = random.uniform(0, self.range)
            azimuth = random.uniform(0, 360)
            elevation = random.uniform(-15, 15)
            point_cloud.append({
                "distance": distance,
                "azimuth": azimuth,
                "elevation": elevation
            })
        return point_cloud

class ActiveSensorManager:
    def __init__(self):
        self.sensors = {
            "main_radar": Radar("Main Radar", 300000, 0.95, 10e9),  # 300km range, 95% accuracy, 10 GHz
            "terrain_following_radar": Radar("Terrain Following Radar", 50000, 0.99, 15e9),  # 50km range, 99% accuracy, 15 GHz
            "lidar": Lidar("LIDAR", 1000, 0.99, 1000000)  # 1km range, 99% accuracy, 1M pulses/second
        }

    def activate_sensor(self, sensor_name):
        if sensor_name in self.sensors:
            self.sensors[sensor_name].activate()
            logger.info(f"[ActiveSensors] Activated {sensor_name}")
        else:
            logger.warning(f"[ActiveSensors] Sensor {sensor_name} not found")

    def deactivate_sensor(self, sensor_name):
        if sensor_name in self.sensors:
            self.sensors[sensor_name].deactivate()
            logger.info(f"[ActiveSensors] Deactivated {sensor_name}")
        else:
            logger.warning(f"[ActiveSensors] Sensor {sensor_name} not found")

    def get_sensor_data(self, sensor_name):
        if sensor_name in self.sensors:
            sensor = self.sensors[sensor_name]
            if isinstance(sensor, Radar) or isinstance(sensor, Lidar):
                return sensor.scan()
            else:
                logger.warning(f"[ActiveSensors] Sensor {sensor_name} does not support scanning")
        else:
            logger.warning(f"[ActiveSensors] Sensor {sensor_name} not found")
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
    asm = ActiveSensorManager()
    asm.activate_sensor("main_radar")
    logger.info(asm.get_sensor_data("main_radar"))
    logger.info(asm.get_all_sensor_statuses())
    asm.deactivate_sensor("main_radar")
