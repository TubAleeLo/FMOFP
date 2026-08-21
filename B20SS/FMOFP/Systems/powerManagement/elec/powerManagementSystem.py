import os
import sys
import FMOFP.Utils.common.fetching as fetching
import random
import time
import threading
import json    # CHANGE TO XML
from FMOFP.storage.DBM import DatabaseManager
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.powerManagement.batts.mainBatt import MainBattery
from FMOFP.Systems.powerManagement.batts.emergencyBatt import EmergencyBattery
from FMOFP.Systems.powerManagement.batts.apuBatt import APUBattery
from FMOFP.Systems.powerManagement.batts.missionEquipmentBatt import MissionEquipmentBatteryBank
from FMOFP.Systems.powerManagement.thermalManagement.coolingSystems.cooling import CoolingSystem
from FMOFP.Systems.powerManagement.thermalManagement.coolingSystems.HVAC import HVACSystem

logger = get_logger()

_pms_instance = None


class PowerManagementSystem:
    def __init__(self):
        self.aircraft = 'aircraft'
        self.db_name = "system_data.db"
        self.key = "B20SS"
        self.pms_data = {}
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.generator_output = 0  # Generator output in kW
        self.total_power_consumption = 0  # Total power consumption in kW

        # Real component-level electrical/thermal model (previously this
        # class only tracked main_battery_charge/aux_battery_charge as two
        # bare floats with no discharge/charge physics and no consumers of
        # the battery/thermal classes built out this session). Wiring this
        # class into the live boot sequence is the reason those classes
        # exist, so use them here instead of the old placeholder floats.
        self.main_battery = MainBattery()
        self.emergency_battery = EmergencyBattery()
        self.apu_battery = APUBattery()
        self.mission_equipment = MissionEquipmentBatteryBank()
        for equip_name in ("Radar", "Comms", "Mission Computer"):
            self.mission_equipment.add_equipment(equip_name)

        self.cooling = CoolingSystem()
        self.hvac = HVACSystem()

        # dbConfig.xml registers this system as "power_management_system",
        # not "power" -- get_system_db('power') always raised ValueError once
        # this class became reachable (production readiness reanalysis,
        # dead-subsystem audit; this was unreachable before the import fix
        # above, since `import Utils.common.fetching` always failed first).
        self.db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('power_management_system')
        self._setup_database()
        self.thread = None
        self._start_lock = threading.Lock()

        # Initialize messaging
        #self.message_handler = MessageHandler()

    def _setup_database(self):
        try:
            table_name = 'pms_data'
            field_data_dict = {'id': 'INTEGER PRIMARY KEY', 'data': 'TEXT'}

            if table_name is not None and field_data_dict is not None:
                # SystemDatabase.create_table(table_name, fields) only takes
                # those two arguments -- this used to also pass
                # received_from/information_type positionally, which always
                # raised "TypeError: create_table() takes 3 positional
                # arguments but 5 were given", caught by this method's own
                # except block and logged, so the 'pms_data' table was never
                # actually created (confirmed live: table_exists('pms_data')
                # returned False after construction). Every later
                # insert_into_table() call in update() would then silently
                # fail in the background too, since insert_into_table() uses
                # the fire-and-forget execute_query_async() path. Fixed
                # earlier this session; now load-bearing since this class is
                # wired into the live boot sequence.
                self.db.create_table(table_name, field_data_dict)
            else:
                logger.warning("Skipping create_table call due to None values")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")

    def adjust_power_parameters(self, dt_hours: float = 1.0 / 3600.0):
        with self.lock:
            # Simulate power generation and consumption
            self.generator_output = random.uniform(200, 250)  # Generator output between 200-250 kW
            self.total_power_consumption = random.uniform(180, 220)  # Total consumption between 180-220 kW

            power_balance_kw = self.generator_output - self.total_power_consumption

            # Route the electrical surplus/deficit through the main battery
            # (24V bus) as charge/discharge current -- P = IV, so
            # amps = kW * 1000 / V. A deficit discharges the main battery;
            # a surplus tops it back up. This replaces the old
            # main_battery_charge/aux_battery_charge float arithmetic with
            # the real Battery amp-hour model.
            amps = abs(power_balance_kw) * 1000.0 / self.main_battery.nominal_voltage
            if power_balance_kw >= 0:
                self.main_battery.charge(amps, dt_hours)
                self.apu_battery.charge(amps / 4.0, dt_hours)
            else:
                self.main_battery.discharge(amps, dt_hours)

            # Emergency battery only supplies load while in emergency mode
            # (activated externally, e.g. by BIT/fault-detection logic);
            # otherwise it just sits ready.
            self.emergency_battery.sustain_critical_systems(dt_hours)

            # Avionics heat load scales with total electrical consumption.
            # NOTE: this is *not* 35% of total_power_consumption converted
            # straight to Watts -- that was tried first and immediately
            # overwhelmed the ActiveDissipationUnit's rejection capacity
            # (max ~100% fan * 0.6 W/%/C * ~35C achievable delta-T =~
            # 2100W ceiling; 35% of a ~200kW total_power_consumption is
            # ~70000W, 33x the unit's max rejection), so coolant_temp_c
            # would climb unbounded past CRITICAL_TEMP_C within about two
            # minutes of continuous running and then log an ERROR every
            # second forever. Confirmed live before choosing this constant:
            # a 6 W-per-kW-of-total-consumption scaling keeps the avionics
            # heat load in the ~1000-1500W range (a plausible fraction of
            # total generator output actually spent on avionics/mission
            # electronics, as opposed to actuators/environmental bleed air/
            # etc.), which the dissipation unit can hold in equilibrium
            # comfortably under WARNING_TEMP_C at full fan speed.
            self.cooling.set_heat_load('avionics_bus', self.total_power_consumption * 6.0)
            self.cooling.update(dt_hours)
            self.hvac.update(dt_hours)

    def monitor(self):
        with self.lock:
            self.pms_data = {
                'main_battery_charge': self.main_battery.charge_pct,
                'emergency_battery_charge': self.emergency_battery.charge_pct,
                'apu_battery_charge': self.apu_battery.charge_pct,
                'generator_output': round(self.generator_output, 2),
                'total_power_consumption': round(self.total_power_consumption, 2),
                'power_balance': round(self.generator_output - self.total_power_consumption, 2),
                'main_bus_voltage': random.uniform(110, 120),  # Main bus voltage (assuming 115V system)
                'aux_bus_voltage': random.uniform(25, 28),  # Auxiliary bus voltage (assuming 28V system)
                'generator_frequency': random.uniform(398, 402),  # Generator frequency (assuming 400Hz system)
                'power_factor': random.uniform(0.95, 1),  # Power factor
                'coolant_temp_c': self.cooling.coolant_temp_c,
                'cabin_temp_c': self.hvac.cabin_temp_c,
            }

    def get_status(self):
        with self.lock:
            return {
                'running': self.thread is not None and self.thread.is_alive(),
                'pms_data': dict(self.pms_data),
                'main_battery': self.main_battery.get_status(),
                'emergency_battery': self.emergency_battery.get_status(),
                'apu_battery': self.apu_battery.get_status(),
                'mission_equipment': self.mission_equipment.get_all_status(),
                'cooling': self.cooling.get_status(),
                'hvac': self.hvac.get_status(),
            }

    def update(self):
        while not self.running.is_set():
            try:
                self.adjust_power_parameters()
                self.monitor()
                with self.lock:
                    self.db.insert_into_table('pms_data', {'data': json.dumps(self.pms_data)})
            except Exception as e:
                logger.error(f"PMS monitoring failed: {e}")
                # NOTE (production readiness re-analysis, August 2026): this was
                # `time.sleep(5)`, which is NOT interruptible by stop() setting the
                # Event -- live-verified (via ThrustManagementSystem, same pattern)
                # that calling stop() while a thread is in this backoff sleep makes
                # stop()'s join(timeout=2) time out and return while the thread is
                # still alive, misleadingly logging "stopped" up to ~3s before the
                # thread actually exits. Event.wait(timeout) is interruptible by
                # .set(), so stop() now wakes this immediately instead of waiting
                # out the full backoff.
                self.running.wait(5)
            else:
                time.sleep(1)  # Update every second

    def start(self):
        # Guarded by a dedicated lock: system_manager.py's start_FM_system()
        # calls x.start() directly during its Phase 3 block, and separately,
        # start_async_components()'s generic "start remaining components"
        # pass also calls component.start() for anything in self.components
        # with a start attribute. Confirmed live (extended 25s+ boot test)
        # that this class's own unguarded check-then-create was a real
        # TOCTOU race: two calls to start() close enough together can both
        # pass "self.thread is None or not self.thread.is_alive()" before
        # either assigns self.thread, spinning up two independent update()
        # threads for the same instance. Proven concretely on
        # FlightDataMonitoring (flightDataMonitoring/fdmControl.py), where
        # the un-locked version's collect_data() log volume was ~2x the
        # single-thread expectation and dropped back to the expected rate
        # once locked. This lock makes start() safe to call redundantly
        # from any number of threads.
        #
        # Separate, since-resolved question: several of these subsystems'
        # "X started" INFO line appeared TWICE in the log even with this
        # lock in place. Dug into it with a logging-internals diagnostic
        # (callHandlers/Handler.handle/emit/stream.write all traced) which
        # proved the *second* start() call is correctly short-circuited by
        # this guard -- no second thread, no second call reaching the
        # logger.info() line below. The real explanation, found by grepping
        # the source tree for the literal duplicated string: there are two
        # separate, intentional logger.info() call sites -- this one here,
        # and a second one in system_manager.py's Phase 3 block, logged
        # right after x.start() returns (e.g. `logger.info("Power
        # Management System started")`). This two-tier "subsystem confirms
        # its own thread started" + "boot sequence confirms the phase step
        # completed" pattern is pre-existing and universal across every
        # Phase 2/3 component (EngineControlUnit/NavService/CommsService/
        # etc. all do the same thing) -- it just wasn't obviously visible
        # for those because their internal messages use a distinguishing
        # [TAG] prefix and slightly different capitalization
        # (e.g. NavService logs "[NAV] Navigation service started"
        # internally vs. system_manager.py's "Navigation Service started"),
        # which happens to dodge a naive substring grep. This class's own
        # internal message is likewise now prefixed "[PMS] " for the same
        # reason (readability/consistency), but the double log line itself
        # is expected, not a bug, and was never actually caused by the
        # TOCTOU race above (that race only ever risked a second *thread*,
        # never a second real log call from a genuinely re-entered start()).
        with self._start_lock:
            if self.thread is None or not self.thread.is_alive():
                self.running.clear()
                self.thread = threading.Thread(target=self.update, daemon=True, name="PMS_Update")
                self.thread.start()
                logger.info("[PMS] Power Management System started.")

    def stop(self):
        self.running.set()
        if self.thread is not None:
            self.thread.join(timeout=2)
            logger.info("Power Management System stopped.")

    def get_data(self):
        with self.lock:
            return self.pms_data

    def set_generator_output(self, output):
        with self.lock:
            self.generator_output = max(0, output)
            logger.info(f"Generator output set to {self.generator_output} kW.")

    def receive_message(self):
        message = self.message_handler.receive_message()
        if message:
            self._process_received_message(message)

    def _process_received_message(self, message):
        # Process the received message
        logger.info(f"Received message: {message}")
        # Here you would typically parse the message and take appropriate action
        # For example, adjusting power distribution based on commands


def get_power_management_system() -> PowerManagementSystem:
    global _pms_instance
    if _pms_instance is None:
        _pms_instance = PowerManagementSystem()
    return _pms_instance


# Example usage
if __name__ == "__main__":
    pms = PowerManagementSystem()
    pms.start()
    pms.monitor()
    pms.receive_message()
    pms.stop()
