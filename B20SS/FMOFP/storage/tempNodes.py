# tempNodes.py
#    THIS is to be renamed - flags.py
#    class rename -    class flags


import threading
from typing import Optional
from FMOFP.Systems.comms.messaging_service import get_comms_service

from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

class BaseNode:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.children = {}
        self.lock = threading.Lock()
        self.messaging_service = get_comms_service()

    def add_child(self, child_node):
        with self.lock:
            self.children[child_node.name] = child_node
            logger.info(f"Added child {child_node.name} to {self.name}")

    def get_child(self, name):
        with self.lock:
            return self.children.get(name)

    def remove_child(self, name):
        with self.lock:
            if name in self.children:
                del self.children[name]
                logger.info(f"Removed child {name} from {self.name}")

    async def save_to_db(self):
        """Persist this node to the state database via DBM."""
        with self.lock:
            logger.debug(f"[NODE] save_to_db: {self.name} value={self.value}")
            try:
                from FMOFP.storage.DBM import DatabaseManager
                db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('configuration_management')
                db.create_table('state_nodes', {
                    'name': 'TEXT PRIMARY KEY',
                    'value': 'TEXT',
                    'updated_at': 'REAL',
                })
                import time, json
                db.insert_into_table('state_nodes', {
                    'name': self.name,
                    'value': json.dumps(str(self.value)),
                    'updated_at': time.time(),
                })
            except Exception as e:
                logger.warning(f"[NODE] save_to_db failed for {self.name}: {e}")

    async def load_from_db(self, name):
        """Load a node by name from the state database via DBM."""
        with self.lock:
            logger.debug(f"[NODE] load_from_db: requested name={name}")
            try:
                from FMOFP.storage.DBM import DatabaseManager
                db = DatabaseManager('FMOFP/dbConfig.xml').get_system_db('configuration_management')
                rows = db.fetch_from_table('state_nodes', filters={'name': name})
                if rows:
                    import json
                    self._handle_load_response({'status': 'success', 'node': {
                        'name': rows[0].get('name', name),
                        'value': json.loads(rows[0].get('value', 'null')),
                        'children': {},
                    }})
                else:
                    logger.debug(f"[NODE] load_from_db: no record found for {name}")
            except Exception as e:
                logger.warning(f"[NODE] load_from_db failed for {name}: {e}")

    def _handle_load_response(self, data: dict) -> None:
        """
        Handle a database load response.

        Stale docstring note removed (August 2026 audit): the "TODO: wire
        to DBM when storage layer is ready" comment predates
        load_from_db() above, which already does exactly that -- fetches
        via DatabaseManager.get_system_db('configuration_management') and
        calls this method with the result. Nothing left to wire up.
        """
        if data.get("status") == "success":
            node_data = data.get("node", {})
            self.name = node_data.get('name', self.name)
            self.value = node_data.get('value', self.value)
            self.children = node_data.get('children', self.children)
            logger.info(f"[NODE] Loaded node {self.name} from database")

    def __repr__(self):
        return f"BaseNode(name={self.name}, value={self.value})"


class LinkedListNode:
    def __init__(self, data):
        self.data = data
        self.next: Optional['LinkedListNode'] = None

    def __repr__(self):
        return f"LinkedListNode(data={self.data})"


class LinkedList:
    def __init__(self):
        self.head = None
        self.lock = threading.Lock()
        self.messaging_service = get_comms_service()

    def append(self, data):
        new_node = LinkedListNode(data)
        with self.lock:
            if not self.head:
                self.head = new_node
                return
            last_node = self.head
            while last_node.next:
                last_node = last_node.next
            last_node.next = new_node

    def prepend(self, data):
        new_node = LinkedListNode(data)
        with self.lock:
            new_node.next = self.head
            self.head = new_node

    def delete_with_value(self, data):
        with self.lock:
            if not self.head:
                return
            if self.head.data == data:
                self.head = self.head.next
                return
            current_node = self.head
            while current_node.next:
                if current_node.next.data == data:
                    current_node.next = current_node.next.next
                    return
                current_node = current_node.next

    def find(self, data):
        with self.lock:
            current_node = self.head
            while current_node:
                if current_node.data == data:
                    return current_node
                current_node = current_node.next
            return None

    def reverse(self):
        with self.lock:
            prev = None
            current = self.head
            while current:
                next_node = current.next
                current.next = prev
                prev = current
                current = next_node
            self.head = prev

    def __repr__(self):
        nodes = []
        current_node = self.head
        while current_node:
            nodes.append(repr(current_node))
            current_node = current_node.next
        return " -> ".join(nodes)


class StateNode(BaseNode):
    def __init__(self, name, value):
        super().__init__(name, value)

    def set_state(self, state):
        with self.lock:
            self.value = state
            logger.info(f"Set state of {self.name} to {state}")

    def get_state(self):
        with self.lock:
            if self.name == None:
                logger.warning(f"State of {self.value} is None")
                return self.value
            return self.value
