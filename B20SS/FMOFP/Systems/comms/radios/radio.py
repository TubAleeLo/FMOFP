import os
import sys
import Utils.common.fetching as fetching
import random
import time
import threading
import json       # CHANGE TO XML
from FMOFP.storage.DBM import DatabaseManager

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class Radio:
    def __init__(self):
        self.aircraft = 'aircraft'
        self.db_name = "system_data.db"
        self.key = "B20SS"
        self.radio_data = {}
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.frequency = 118.0  # Default frequency in MHz
        self.mode = 'AM'  # Default mode (AM/FM)
        self.volume = 50  # Default volume (0-100)
        self.squelch = 3  # Default squelch level (0-9)
        self.signal_strength = 0
        self.db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('comms')
        self._setup_database()
        self.thread = None

        # Initialize messaging
        #self.message_handler = MessageHandler()

    def _setup_database(self):
        try:
            table_name = 'radio_data'
            received_from = 'radio_system'
            information_type = 'communication_data'
            field_data_dict = {'id': 'INTEGER PRIMARY KEY', 'data': 'TEXT'}

            if table_name is not None and received_from is not None and information_type is not None and field_data_dict is not None:
                self.db.create_table(table_name, received_from, information_type, field_data_dict)
            else:
                logger.warning("Skipping create_table call due to None values")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")

    def simulate_radio_parameters(self):
        with self.lock:
            # Simulate signal strength changes
            self.signal_strength = random.uniform(0, 100)  # Signal strength in percentage

    def monitor(self):
        with self.lock:
            self.radio_data = {
                'frequency': self.frequency,
                'mode': self.mode,
                'volume': self.volume,
                'squelch': self.squelch,
                'signal_strength': round(self.signal_strength, 2),
                'noise_level': random.uniform(0, 20),  # Noise level in dB
                'clarity': random.uniform(0, 100),  # Voice clarity in percentage
                'interference': random.choice(['none', 'low', 'medium', 'high']),
                'battery_level': random.uniform(0, 100),  # Battery level for portable radios
            }
            self.message_handler.send_radio_data(self.radio_data)

    def update(self):
        while not self.running.is_set():
            try:
                self.simulate_radio_parameters()
                self.monitor()
                with self.lock:
                    self.db.insert_into_table('radio_data', {'data': json.dumps(self.radio_data)})
            except Exception as e:
                logger.error(f"Radio monitoring failed: {e}")
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
            logger.info("Radio system started.")

    def stop(self):
        self.running.set()
        if self.thread is not None:
            self.thread.join()
            logger.info("Radio system stopped.")

    def get_data(self):
        with self.lock:
            return self.radio_data

    def set_frequency(self, frequency):
        with self.lock:
            self.frequency = frequency
            logger.info(f"Radio frequency set to {self.frequency} MHz.")

    def set_mode(self, mode):
        with self.lock:
            if mode in ['AM', 'FM']:
                self.mode = mode
                logger.info(f"Radio mode set to {self.mode}.")
            else:
                logger.warning(f"Invalid radio mode: {mode}")

    def set_volume(self, volume):
        with self.lock:
            self.volume = max(0, min(100, volume))
            logger.info(f"Radio volume set to {self.volume}.")

    def set_squelch(self, squelch):
        with self.lock:
            self.squelch = max(0, min(9, squelch))
            logger.info(f"Radio squelch set to {self.squelch}.")

    def transmit(self, message):
        if self.signal_strength > 20:  # Arbitrary threshold for transmission
            logger.info(f"Transmitting message: {message}")
            # Here you would implement the actual message transmission logic
            return True
        else:
            logger.warning("Cannot transmit: Signal too weak")
            return False

    def receive_message(self):
        message = self.message_handler.receive_message()
        if message:
            self._process_received_message(message)

    def _process_received_message(self, message):
        # Process the received message
        logger.info(f"Received radio message: {message}")
        # Here you would typically parse the message and take appropriate action
        # For example, updating radio parameters or forwarding to other systems

# Example usage
if __name__ == "__main__":
    radio = Radio()
    radio.start()
    radio.set_frequency(120.5)
    radio.set_mode('AM')
    radio.transmit("Test transmission")
    radio.receive_message()
    radio.stop()
