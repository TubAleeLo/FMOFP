import FMOFP.Utils.common.fetching as fetching
import os
import xml.etree.ElementTree as ET
import time
import threading
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_hydraulic_instance = None

# hydrConfig.xml lives alongside this file. The previous relative path,
# "Systems/hydraulics/hydrConfig.xml", was missing the "FMOFP/" segment (only
# B20SS/FMOFP/Systems/... exists, not B20SS/Systems/...), so it raised
# FileNotFoundError on every construction -- and this class isn't
# currently instantiated anywhere in the codebase, so the bug was
# entirely latent (production readiness reanalysis, dead-subsystem
# audit). Resolving relative to this file's own directory, matching
# the pattern already used in bitControl.py / DBM.py / baseStartUp.py,
# fixes this regardless of working directory if this class is ever
# wired up.
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hydrConfig.xml")

class HydraulicSystemController:
    def __init__(self):


        
        tree = ET.parse(_CONFIG_PATH)
        config = tree.getroot()
        
        self.primary_system = {
            "id": int(config.find("primarySystem/id").text),
            "description": config.find("primarySystem/description").text,
            "components": []
        }
        for comp in config.findall("primarySystem/components/component"):
            name = comp.find("name").text
            desc = comp.find("description").text
            self.primary_system["components"].append({"name": name, "description": desc})
            
        self.backup_system = {
            "id": int(config.find("backupSystem/id").text),
            "description": config.find("backupSystem/description").text,
            "components": []
        }
        for comp in config.findall("backupSystem/components/component"):
            name = comp.find("name").text
            desc = comp.find("description").text  
            self.backup_system["components"].append({"name": name, "description": desc})
            
        self.pressure_thresholds = {
            "nominal": int(config.find("nominalPressure").text),
            "warning": int(config.find("warningThreshold").text),
            "critical": int(config.find("criticalThreshold").text)
        }
        
        self.active_system = self.primary_system
        self._running = threading.Event()
        self._thread = None
        self._start_lock = threading.Lock()

    def monitor_pressure(self):
        # Simulate getting pressure data
        current_pressure = 2800
        
        status = "OK"
        if current_pressure == self.pressure_thresholds["critical"]:
            status = "CRITICAL"
            self.activate_backup()
        elif current_pressure == self.pressure_thresholds["warning"]:
            status = "WARNING"
            
        logger.info(f"Hydraulic pressure: {current_pressure} psi, Status: {status}")
        
    def activate_backup(self):
        logger.info("Activating backup hydraulic system")
        self.active_system = self.backup_system
        
    def run(self):
        # NOTE: previously `while True:` with no sleep at all -- a 100%-CPU
        # busy loop with no way to exit, if this class were ever wired up
        # and its run() called (it currently isn't instantiated anywhere in
        # the codebase). No documented polling interval exists in
        # hydrConfig.xml, so using 1s as a reasonable generic monitoring
        # cadence, matching the interval other subsystem singletons default
        # to (e.g. CommsService, MissionService) absent a more specific
        # requirement.
        while not self._running.is_set():
            # try/except added round 20: this loop previously had no
            # exception handling at all. Live-reproduced that an uncaught
            # exception inside monitor_pressure() (e.g. a KeyError from a
            # malformed pressure_thresholds dict) kills this daemon thread
            # permanently and silently -- Python's threading.excepthook
            # prints a raw traceback to stderr (not this app's own logger),
            # thread.is_alive() goes False forever, and nothing anywhere in
            # this codebase watches for or restarts a dead subsystem
            # thread. Matches the self-healing try/except-per-iteration
            # pattern already established in ThrustManagementSystem,
            # MissionService, and NavService's own update loops.
            try:
                self.monitor_pressure()
            except Exception as e:
                logger.error(f"[HYDRAULICS] Monitor error: {e}")
            time.sleep(1.0)

    def start(self):
        # Guarded by a dedicated lock against a TOCTOU race in the
        # check-then-create sequence below -- see PowerManagementSystem
        # .start()'s comment (powerManagement/elec/powerManagementSystem.py)
        # for the full writeup, including why this is a real (not
        # cosmetic) fix.
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self.run, daemon=True, name="Hydraulics_Update")
            self._thread.start()
            logger.info("[HYDRAULICS] Hydraulic System Controller started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Hydraulic System Controller stopped")

    def get_status(self):
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'active_system': self.active_system.get('description'),
            'pressure_thresholds': dict(self.pressure_thresholds),
        }


def get_hydraulic_system_controller() -> "HydraulicSystemController":
    global _hydraulic_instance
    if _hydraulic_instance is None:
        _hydraulic_instance = HydraulicSystemController()
    return _hydraulic_instance


if __name__ == "__main__":
    controller = HydraulicSystemController() 
    controller.run()