import os
import sys
import Utils.common.fetching as fetching
import random
import time
import threading
import xml.etree.ElementTree as ET
from queue import Queue, PriorityQueue
from FMOFP.storage.DBM import DatabaseManager

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class DataLink:
    def __init__(self):
        self.aircraft = 'aircraft'
        self.db_name = "system_data.db"
        self.key = "B20SS"
        self.datalink_data = {}
        self.running = threading.Event()
        self.lock = threading.Lock()
        self.connection_status = 'disconnected'
        self.signal_strength = 0
        self.data_rate = 0
        self.latency = 0
        self.db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('comms')
        self._setup_database()
        self.thread = None
        self.message_queue = PriorityQueue()
        self.datalink_mode = 'LOS'  # Line of Sight by default

    def _setup_database(self):
        try:
            table_name = 'datalink_data'
            received_from = 'datalink_system'
            information_type = 'communication_data'
            field_data_dict = {'id': 'INTEGER PRIMARY KEY', 'data': 'TEXT'}

            if table_name is not None and received_from is not None and information_type is not None and field_data_dict is not None:
                self.db.create_table(table_name, received_from, information_type, field_data_dict)
            else:
                logger.warning("Skipping create_table call due to None values")
        except Exception as e:
            logger.error(f"Database setup failed: {e}")

    def simulate_datalink_parameters(self):
        with self.lock:
            if random.random() < 0.05:  # 5% chance of connection status change
                self.connection_status = random.choice(['connected', 'disconnected', 'connecting'])

            if self.connection_status == 'connected':
                if self.datalink_mode == 'LOS':
                    self.signal_strength = random.uniform(80, 100)
                    self.data_rate = random.uniform(5, 10)
                    self.latency = random.uniform(10, 100)
                elif self.datalink_mode == 'BLOS':
                    self.signal_strength = random.uniform(60, 90)
                    self.data_rate = random.uniform(1, 5)
                    self.latency = random.uniform(100, 500)
            else:
                self.signal_strength = 0
                self.data_rate = 0
                self.latency = 0

    def monitor(self):
        with self.lock:
            self.datalink_data = {
                'connection_status': self.connection_status,
                'signal_strength': round(self.signal_strength, 2),
                'data_rate': round(self.data_rate, 2),
                'latency': round(self.latency, 2),
                'packets_sent': random.randint(1000, 10000),
                'packets_received': random.randint(1000, 10000),
                'error_rate': random.uniform(0, 0.1),
                'encryption_status': random.choice(['enabled', 'disabled']),
                'channel': random.randint(1, 20),
                'datalink_mode': self.datalink_mode,
            }
            self.message_handler.send_datalink_data(self.datalink_data)

    def update(self):
        while not self.running.is_set():
            try:
                self.simulate_datalink_parameters()
                self.monitor()
                with self.lock:
                    self.db.insert_into_table('datalink_data', {'data': self._dict_to_xml(self.datalink_data)})
                self._process_message_queue()
            except Exception as e:
                logger.error(f"DataLink monitoring failed: {e}")
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
            logger.info("DataLink system started.")

    def stop(self):
        self.running.set()
        if self.thread is not None:
            self.thread.join()
            logger.info("DataLink system stopped.")

    def get_data(self):
        with self.lock:
            return self.datalink_data

    def send_message(self, message, priority=2):
        if self.connection_status == 'connected':
            logger.info(f"Sending message: {message}")
            # Here you would implement the actual message sending logic
            return True
        else:
            logger.warning("Cannot send message: DataLink not connected")
            self.message_queue.put((priority, message))
            return False

    def receive_message(self):
        message = self.message_handler.receive_message()
        if message:
            self._process_received_message(message)

    def _process_received_message(self, message):
        logger.info(f"Received message: {message}")
        # Parse the message and take appropriate action

    def _process_message_queue(self):
        if self.connection_status == 'connected':
            while not self.message_queue.empty():
                priority, message = self.message_queue.get()
                self.send_message(message, priority)

    def set_datalink_mode(self, mode):
        if mode in ['LOS', 'BLOS']:
            self.datalink_mode = mode
            logger.info(f"DataLink mode set to {mode}")
        else:
            logger.warning(f"Invalid DataLink mode: {mode}")

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
    datalink = DataLink()
    datalink.start()
    datalink.set_datalink_mode('BLOS')
    datalink.monitor()
    datalink.send_message("Test message", priority=1)
    datalink.receive_message()
    datalink.stop()
