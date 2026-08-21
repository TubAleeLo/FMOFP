# Mission Equipment Batteries: These batteries might be used to power
# specific equipment related to the aircraft's  missions,
# such as sensors, radar, and communications systems that
# require independent power sources to enhance redundancy and security.

from typing import Dict
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.powerManagement.batts.mainBatt import Battery

logger = get_logger()


class MissionEquipmentBattery(Battery):
    """
    Mission Equipment Battery: an independent power source for a single
    piece of mission equipment (sensor, radar, comms system, etc.),
    isolated from the main aircraft electrical bus for redundancy/security.
    Tracks which piece of equipment it's currently powering.
    """

    def __init__(self, equipment_name: str, capacity_ah: float = 6.0,
                 nominal_voltage: float = 28.0, charge_pct: float = 100.0):
        super().__init__(f"Mission Equipment Battery ({equipment_name})",
                          capacity_ah, nominal_voltage, charge_pct)
        self.equipment_name = equipment_name
        self.powering_equipment = False

    def power_equipment(self, draw_amps: float, dt_hours: float) -> bool:
        """
        Supply power to the associated equipment for one tick. Returns
        True if the full requested load was supplied.
        """
        supplied = self.discharge(draw_amps, dt_hours)
        required = draw_amps * dt_hours
        self.powering_equipment = supplied >= required * 0.999 and draw_amps > 0
        if draw_amps > 0 and not self.powering_equipment:
            logger.warning(f"[BATT] {self.equipment_name} battery cannot sustain "
                            f"full load - {self.charge_pct:.1f}% charge remaining")
        return self.powering_equipment

    def get_status(self) -> Dict:
        status = super().get_status()
        status['equipment_name'] = self.equipment_name
        status['powering_equipment'] = self.powering_equipment
        return status


class MissionEquipmentBatteryBank:
    """
    Manages the independent battery for each mission-equipment item
    (sensors, radar, comms, etc.) as a named collection.
    """

    def __init__(self):
        self._batteries: Dict[str, MissionEquipmentBattery] = {}

    def add_equipment(self, equipment_name: str, capacity_ah: float = 6.0,
                       nominal_voltage: float = 28.0) -> MissionEquipmentBattery:
        batt = MissionEquipmentBattery(equipment_name, capacity_ah, nominal_voltage)
        self._batteries[equipment_name] = batt
        logger.info(f"[BATT] Added mission equipment battery for {equipment_name}")
        return batt

    def get(self, equipment_name: str) -> "MissionEquipmentBattery | None":
        return self._batteries.get(equipment_name)

    def get_all_status(self) -> Dict[str, Dict]:
        return {name: batt.get_status() for name, batt in self._batteries.items()}
