import FMOFP.Utils.common.fetching as fetching
import time
import threading
from FMOFP.Utils.logger.sys_logger import get_logger
from FMOFP.Systems.enviornmentalControlSystem.climate.climateControl import ClimateControl
from FMOFP.Systems.enviornmentalControlSystem.oxygenGenerationsys.oxygenControl import OxygenControl

logger = get_logger()

_ecs_instance = None

class ECSControl:
    def __init__(self):
        if not hasattr(self, 'running'):
            self.running = False
        self._thread = None
        self._start_lock = threading.Lock()

        # ClimateControl and OxygenControl (climate/climateControl.py,
        # oxygenGenerationsys/oxygenControl.py) were fixed earlier this
        # session (both imported a nonexistent FMOFP.local_messaging
        # .Messaging.Messaging class and called sys_logger(name) as a
        # constructor, raising ModuleNotFoundError on every import) but
        # were never actually wired into anything -- confirmed via a
        # repo-wide dead-code sweep (production readiness re-analysis,
        # August 2026) that neither class was instantiated anywhere
        # outside its own file. They're complementary to, not duplicates
        # of, this class's existing get_temperature()/get_pressure()/
        # get_air_quality() readings: those three remain a documented
        # stub (no real sensor data source exists), while ClimateControl
        # tracks temperature/humidity as genuinely mutable, adjustable
        # state and OxygenControl models cabin oxygen generation -- a
        # concern ECSControl didn't cover at all before. Owned here the
        # same way PowerManagementSystem owns its battery/cooling/HVAC
        # sub-components.
        self.climate = ClimateControl()
        self.oxygen = OxygenControl()

    def initialize(self):
        logger.info("Initializing Environmental Control System")

    def run(self):
        # NOTE: previously just set self.running = True and returned
        # immediately -- not an actual monitoring loop, so calling run()
        # (e.g. as a thread target) would do nothing beyond that one flag
        # flip. This class isn't currently instantiated anywhere in the
        # codebase (dead code today), so the gap was entirely latent.
        # Turned into a real periodic monitor loop, matching the pattern
        # used by every other subsystem singleton wired into
        # system_manager.py this round.
        self.initialize()
        self.running = True
        while self.running:
            # try/except added round 20: this loop previously had no
            # exception handling at all -- live-reproduced (via the
            # identical pattern in hydrControl.py's run(), same fix
            # applied there) that an uncaught exception here would kill
            # this daemon thread permanently and silently, with no
            # restart and no entry in this app's own log file. Matches
            # the self-healing try/except-per-iteration pattern already
            # established in ThrustManagementSystem/MissionService/
            # NavService's own update loops.
            try:
                self.monitor_ecs()
            except Exception as e:
                logger.error(f"[ECS] Monitor error: {e}")
            time.sleep(2.0)

    def start(self):
        # Guarded by a dedicated lock against a TOCTOU race in the
        # check-then-create sequence below -- see PowerManagementSystem
        # .start()'s comment (powerManagement/elec/powerManagementSystem.py)
        # for the full writeup.
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self.run, daemon=True, name="ECS_Update")
            self._thread.start()
            logger.info("[ECS] Environmental Control System started")

    def stop(self):
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Environmental Control System stopped")

    def get_status(self):
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'temperature_c': self.get_temperature(),
            'pressure_kpa': self.get_pressure(),
            'air_quality_pct': self.get_air_quality(),
            'climate': self.climate.get_climate_status(),
            'oxygen': self.oxygen.get_oxygen_status(),
        }

    def monitor_ecs(self):
        # Monitor temperature, pressure, and air quality
        temperature = self.get_temperature()
        pressure = self.get_pressure()
        air_quality = self.get_air_quality()

        logger.info(f"ECS Status - Temp: {temperature}°C, Pressure: {pressure} kPa, Air Quality: {air_quality}%")

        # Adjust system based on readings
        self.adjust_temperature(temperature)
        self.adjust_pressure(pressure)
        self.adjust_air_quality(air_quality)

        # Drive the two previously-unwired sub-components each tick:
        # oxygen generation runs continuously in a real ECS, and climate
        # is nudged toward this cycle's temperature reading so
        # get_status()['climate'] reflects genuinely live (if still
        # simulated) state rather than sitting frozen at its 22.0C/50%
        # construction-time defaults forever.
        self.oxygen.generate_oxygen()
        self.climate.adjust_temperature(temperature)

    def get_temperature(self):
        # Simulate temperature reading
        return 22.5  # 22.5°C

    def get_pressure(self):
        # Simulate pressure reading
        return 101.3  # 101.3 kPa (standard atmospheric pressure)

    def get_air_quality(self):
        # Simulate air quality reading (percentage of clean air)
        return 98.5  # 98.5% clean air

    def adjust_temperature(self, current_temp):
        target_temp = 22.0  # Target temperature in °C
        if abs(current_temp - target_temp) > 0.5:
            logger.info(f"Adjusting temperature from {current_temp}°C to {target_temp}°C")
            # Code to adjust temperature

    def adjust_pressure(self, current_pressure):
        target_pressure = 101.3  # Target pressure in kPa
        if abs(current_pressure - target_pressure) > 0.5:
            logger.info(f"Adjusting pressure from {current_pressure} kPa to {target_pressure} kPa")
            # Code to adjust pressure

    def adjust_air_quality(self, current_quality):
        if current_quality < 95:
            logger.info(f"Air quality below threshold. Current: {current_quality}%. Activating air purification.")
            # Code to activate air purification systems

def get_ecs_control() -> "ECSControl":
    global _ecs_instance
    if _ecs_instance is None:
        _ecs_instance = ECSControl()
    return _ecs_instance


if __name__ == "__main__":
    ecs = ECSControl()
    ecs.initialize()
