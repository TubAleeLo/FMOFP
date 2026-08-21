import FMOFP.Utils.common.fetching as fetching
import os
import xml.etree.ElementTree as ET
import time
import threading
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_fitness_instance = None

# fmfConfig.xml lives alongside this file. The previous relative path,
# "Systems/fmFitness/fmfConfig.xml", was missing the "FMOFP/" segment (only
# B20SS/FMOFP/Systems/... exists, not B20SS/Systems/...), so it raised
# FileNotFoundError on every construction -- and this class isn't
# currently instantiated anywhere in the codebase, so the bug was
# entirely latent (production readiness reanalysis, dead-subsystem
# audit). Resolving relative to this file's own directory, matching
# the pattern already used in bitControl.py / DBM.py / baseStartUp.py,
# fixes this regardless of working directory if this class is ever
# wired up.
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fmfConfig.xml")


class FlightManagementFitness:
    def __init__(self):
        pass
        
        tree = ET.parse(_CONFIG_PATH)
        config = tree.getroot()
        
        self.components = []
        for comp in config.find("components"):
            name = comp.find("name").text
            desc = comp.find("description").text
            self.components.append({"name": name, "description": desc})
            
        self.thresholds = {
            "warning": {
                "cpu": int(config.find("thresholds/warning/cpu").text),
                "memory": int(config.find("thresholds/warning/memory").text)
            },
            "critical": {
                "cpu": int(config.find("thresholds/critical/cpu").text),
                "memory": int(config.find("thresholds/critical/memory").text)
            }
        }
        
        self.redundancy = {
            "component": config.find("redundancy/component").text,
            "backup": config.find("redundancy/backup").text
        }

        self._running = threading.Event()
        self._thread = None
        self._start_lock = threading.Lock()

    def monitor_components(self):
        # Simulate monitoring components
        # Get actual component data from other systems
        logger.info("Monitoring flight management components")
        
    def check_thresholds(self, component, metrics):
        # Check CPU and memory usage against thresholds
        cpu_usage = metrics.get("cpu", 0)
        mem_usage = metrics.get("memory", 0)
        
        status = "OK"
        if cpu_usage == self.thresholds["critical"]["cpu"] or \
           mem_usage == self.thresholds["critical"]["memory"]:
            status = "CRITICAL"
        elif cpu_usage == self.thresholds["warning"]["cpu"] or \
             mem_usage == self.thresholds["warning"]["memory"]:
            status = "WARNING"
            
        logger.info(f"{component} status: {status}") 
        
        # Take appropriate actions based on status
        
    def handle_redundancy(self, component):
        if component == self.redundancy["component"]:
            logger.info(f"Activating backup {self.redundancy['backup']} for {component}")
            # Failover logic
            
    def run(self):
        while not self._running.is_set():
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
                self.monitor_components()

                # Simulate getting metrics from components
                for component in self.components:
                    metrics = {
                        "cpu": 75, # Replace with actual CPU usage
                        "memory": 80 # Replace with actual memory usage  
                    }
                    self.check_thresholds(component["name"], metrics)
            except Exception as e:
                logger.error(f"[FMFITNESS] Monitor error: {e}")

            # Sleep for configured interval before checking again.
            # NOTE: this comment previously had no actual time.sleep() call
            # backing it -- the loop was a 100%-CPU busy loop with no way to
            # exit, if this class were ever wired up and its run() called
            # (it currently isn't instantiated anywhere in the codebase). No
            # documented polling interval exists in fmfConfig.xml, so using
            # 1s as a reasonable generic monitoring cadence, matching the
            # interval other subsystem singletons default to (e.g.
            # CommsService, MissionService) absent a more specific
            # requirement.
            time.sleep(1.0)

    def start(self):
        # Guarded by a dedicated lock -- see PowerManagementSystem.start()'s
        # comment for the full TOCTOU race explanation confirmed live via
        # an extended boot test; same fix applied here.
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self.run, daemon=True, name="FMFitness_Update")
            self._thread.start()
            logger.info("[FMFITNESS] Flight Management Fitness started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Flight Management Fitness stopped")

    def get_status(self):
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'components': [c['name'] for c in self.components],
            'redundancy': dict(self.redundancy),
        }


def get_flight_management_fitness() -> "FlightManagementFitness":
    global _fitness_instance
    if _fitness_instance is None:
        _fitness_instance = FlightManagementFitness()
    return _fitness_instance


if __name__ == "__main__":
    fmf = FlightManagementFitness()
    fmf.run()