import FMOFP.Utils.common.fetching as fetching
import os
import xml.etree.ElementTree as ET
import time
import threading
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

_fdm_instance = None

# fdmsConfig.xml lives alongside this file. The previous relative path,
# "Systems/flightDataMonitoring/fdmsConfig.xml", was missing the "FMOFP/" segment (only
# B20SS/FMOFP/Systems/... exists, not B20SS/Systems/...), so it raised
# FileNotFoundError on every construction -- and this class isn't
# currently instantiated anywhere in the codebase, so the bug was
# entirely latent (production readiness reanalysis, dead-subsystem
# audit). Resolving relative to this file's own directory, matching
# the pattern already used in bitControl.py / DBM.py / baseStartUp.py,
# fixes this regardless of working directory if this class is ever
# wired up.
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fdmsConfig.xml")

class FlightDataMonitoring:
    def __init__(self):

        
        tree = ET.parse(_CONFIG_PATH)
        config = tree.getroot()
        
        self.recorders = []
        for recorder in config.findall("recorders/recorder"):
            rec_id = int(recorder.find("id").text)
            desc = recorder.find("description").text
            rec_type = recorder.find("type").text
            parameters = [{"name": p.find("name").text, "units": p.find("units").text} for p in recorder.findall("parameters/parameter")]
            self.recorders.append({"id": rec_id, "description": desc, "type": rec_type, "parameters": parameters})
            
        self.storage = []
        for card in config.findall("storage/memoryCards/card"):
            slot = int(card.find("slot").text)
            desc = card.find("description").text
            capacity = int(card.find("capacity").text)
            contents = card.find("contents").text 
            self.storage.append({"slot": slot, "description": desc, "capacity": capacity, "contents": contents})

        self._running = threading.Event()
        self._thread = None
        self._start_lock = threading.Lock()

    def collect_data(self):
        for recorder in self.recorders:
            logger.info(f"Recording {recorder['description']} Data:")
            for param in recorder["parameters"]:
                value = 123 # Simulate parameter value
                logger.info(f"  {param['name']}: {value} {param['units']}")
                
    def eject_storage(self, slot):
        card = next((c for c in self.storage if c["slot"] == slot), None)
        if card:
            logger.info(f"Ejecting {card['description']}")
            # Simulate ejecting storage card
            logger.info(f"  Contents: {card['contents'].upper()} data")
            logger.info(f"  Capacity: {card['capacity']} GB") 
        else:
            logger.warning(f"No storage card in slot {slot}")
        
    def run(self):
        """
        Standalone demo entry point (python fdmControl.py): records one
        pass of flight parameters, then simulates ejecting both storage
        cards. Kept unchanged from its original form for that use.
        """
        self.collect_data()

        self.eject_storage(1)
        self.eject_storage(2)

    def _record_loop(self):
        """
        Continuous flight-data-recorder loop: repeatedly logs parameters
        via collect_data(), matching the real behavior of a flight data
        recorder (it records continuously in flight). Deliberately does
        NOT call eject_storage() on a timer -- ejecting a recorder's
        storage card is a ground-crew maintenance action, not something
        that should happen automatically and repeatedly every few seconds
        while the aircraft is running; eject_storage() remains available
        to be called on demand (e.g. from a maintenance CLI).
        """
        logger.info("[FDM] Recording loop started")
        while not self._running.is_set():
            try:
                self.collect_data()
            except Exception as e:
                logger.error(f"[FDM] Recording error: {e}")
                # NOTE (production readiness re-analysis, August 2026): this was
                # `time.sleep(5)`, which is NOT interruptible by stop() setting the
                # Event -- live-verified (via ThrustManagementSystem, same pattern)
                # that calling stop() while a thread is in this backoff sleep makes
                # stop()'s join(timeout=2) time out and return while the thread is
                # still alive, misleadingly logging "stopped" up to ~3s before the
                # thread actually exits. Event.wait(timeout) is interruptible by
                # .set(), so stop() now wakes this immediately instead of waiting
                # out the full backoff.
                self._running.wait(5)
                continue
            time.sleep(2.0)

    def start(self):
        # Guarded by a dedicated lock -- confirmed live (extended 25s+ boot
        # test) that without it, this was a genuine TOCTOU race producing a
        # real second _record_loop() thread: collect_data() log volume ran
        # at ~28 recordings in ~28s at a 2s cadence (roughly double the
        # ~14 a single correct thread produces), dropping back to ~14 once
        # locked. (The separately-observed "Flight Data Monitoring
        # started" line appearing twice is unrelated to this race -- see
        # PowerManagementSystem.start()'s comment for why.)
        with self._start_lock:
            if self._thread and self._thread.is_alive():
                return
            self._running.clear()
            self._thread = threading.Thread(target=self._record_loop, daemon=True, name="FDM_Record")
            self._thread.start()
            logger.info("[FDM] Flight Data Monitoring started")

    def stop(self):
        self._running.set()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Flight Data Monitoring stopped")

    def get_status(self):
        return {
            'running': self._thread is not None and self._thread.is_alive(),
            'recorder_count': len(self.recorders),
            'storage_slots': [s['slot'] for s in self.storage],
        }


def get_flight_data_monitoring() -> "FlightDataMonitoring":
    global _fdm_instance
    if _fdm_instance is None:
        _fdm_instance = FlightDataMonitoring()
    return _fdm_instance


if __name__ == "__main__":
    fdm = FlightDataMonitoring()
    fdm.run()