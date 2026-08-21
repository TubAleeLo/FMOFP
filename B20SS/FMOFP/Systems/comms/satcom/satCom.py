import os
import sys
import Utils.common.fetching as fetching
import random
import time
import threading
import json   # CHANGE TO XML
from FMOFP.storage.DBM import DatabaseManager

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class SatCom:
    def __init__(self):
        self.aircraft = 'aircraft'
        self.db_name = "system_data.db"
        self.key = "B20SS"
        self.satcom_data = {}
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.connection_status = 'disconnected'
        self.signal_strength = 0
        self.data_rate = 0
        self.latency = 0
        self.satellite_id = None
        self.db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('comms')
        self._setup_database()
        self.thread = None

        # Initialize messaging
        #self.message_handler = MessageHandler()

    def _setup_database(self):
        try:
            self.db.create_table('satcom_data', {
                'id':   'INTEGER PRIMARY KEY AUTOINCREMENT',
                'data': 'TEXT NOT NULL',
            })
        except Exception as e:
            logger.error(f"Database setup failed: {e}")

    def simulate_satcom_parameters(self):
        with self.lock:
            # Small chance of connection status change
            if self.connection_status == 'connected':
                if random.random() < 0.005:   # 0.5% dropout chance
                    self.connection_status = 'disconnected'
                    self.signal_strength = 0
                    self.data_rate = 0
                    self.latency = 0
                    self.satellite_id = None
                else:
                    self.signal_strength = random.uniform(60, 100)
                    self.data_rate = random.uniform(0.1, 2)
                    self.latency = random.uniform(500, 1000)
            elif self.connection_status == 'acquiring':
                if random.random() < 0.08:   # 8% per tick → links within ~12 s on average
                    self.connection_status = 'connected'
                    self.signal_strength  = random.uniform(60, 100)
                    self.data_rate        = random.uniform(0.1, 2)
                    self.latency          = random.uniform(500, 1000)
                    self.satellite_id     = f"SAT-{random.randint(1000, 9999)}"
                    logger.info(f"[SATCOM] Linked to {self.satellite_id}")
            else:
                if random.random() < 0.02:   # 2% spontaneous connection attempt
                    self.connection_status = 'acquiring'
                self.signal_strength = 0
                self.data_rate = 0
                self.latency = 0
                self.satellite_id = None

    def monitor(self):
        with self.lock:
            self.satcom_data = {
                'connection_status': self.connection_status,
                'signal_strength':   round(self.signal_strength, 2),
                'data_rate_kbps':    round(self.data_rate * 1000, 1),   # Mbps → kbps
                'latency_ms':        round(self.latency, 2),
                'satellite_id':      self.satellite_id,
                'elevation_deg':     random.uniform(0, 90)  if self.connection_status == 'connected' else 0,
                'azimuth_deg':       random.uniform(0, 360) if self.connection_status == 'connected' else 0,
                'band':              random.choice(['L', 'Ku', 'Ka']) if self.connection_status == 'connected' else None,
                'bit_error_rate':    random.uniform(0, 0.001) if self.connection_status == 'connected' else 0,
            }

    def update(self):
        while not self.running.is_set():
            try:
                self.simulate_satcom_parameters()
                self.monitor()
                with self.lock:
                    self.db.insert_into_table('satcom_data', {'data': json.dumps(self.satcom_data)})
            except Exception as e:
                logger.error(f"SatCom monitoring failed: {e}")
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
        if self.thread is None or not self.thread.is_alive():
            self.running.clear()
            self.thread = threading.Thread(target=self.update)   # THREAD STARTED IN WRONG PLACE - SHOULD START IN system_manager.py
            self.thread.start()
            logger.info("SatCom system started.")

    def stop(self):
        self.running.set()
        if self.thread is not None:
            self.thread.join()
            logger.info("SatCom system stopped.")

    def get_data(self):
        with self.lock:
            return self.satcom_data

    def is_connected(self) -> bool:
        """Return True when actively linked to a satellite."""
        with self.lock:
            return self.connection_status == 'connected'

    def send_message(self, message):
        if self.connection_status == 'connected':
            logger.info(f"Sending message via SatCom: {message}")
            # Here you would implement the actual message sending logic
            return True
        else:
            logger.warning("Cannot send message: SatCom not connected")
            return False

    def _process_received_message(self, message):
        logger.info(f"Received SatCom message: {message}")

    def acquire_satellite(self):
        """Non-blocking acquisition trigger. Sets status to 'acquiring';
        simulate_satcom_parameters will complete the link on a future tick."""
        with self.lock:
            if self.connection_status != 'connected':
                self.connection_status = 'acquiring'
                logger.info("[SATCOM] Satellite acquisition triggered")

    def force_acquire(self):
        """Alias for acquire_satellite (compatibility)."""
        self.acquire_satellite()

# Example usage
if __name__ == "__main__":
    satcom = SatCom()
    satcom.start()
    satcom.acquire_satellite()
    satcom.send_message("Test SatCom message")
    satcom.receive_message()
    satcom.stop()
