from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
import time
import xml.etree.ElementTree as ET

@dataclass
class weather_radarAcknowledgment(BaseMessage):
    """Command acknowledgment message for weather radar operations"""
    command: str = ""  # The command being acknowledged
    status: str = ""   # Success/failure status
    timestamp: float = 0.0  # When the command was processed
    request_id: str = ""  # ID of the original request being acknowledged

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()

    def to_xml(self):
        """Convert to XML format as specified in message templates"""
        root = ET.Element("message")
        
        type_elem = ET.SubElement(root, "type")
        type_elem.text = "command_acknowledgment"
        
        command_elem = ET.SubElement(root, "command")
        command_elem.text = self.command
        
        status_elem = ET.SubElement(root, "status")
        status_elem.text = self.status
        
        timestamp_elem = ET.SubElement(root, "timestamp")
        timestamp_elem.text = str(self.timestamp)
        
        request_id_elem = ET.SubElement(root, "request_id")
        request_id_elem.text = self.request_id
        
        return ET.tostring(root, encoding='unicode')

    def from_xml(self, xml_str: str):
        """Update from XML format"""
        root = ET.fromstring(xml_str)
        
        command_elem = root.find("command")
        if command_elem is not None:
            self.command = command_elem.text
            
        status_elem = root.find("status")
        if status_elem is not None:
            self.status = status_elem.text
            
        timestamp_elem = root.find("timestamp")
        if timestamp_elem is not None:
            self.timestamp = float(timestamp_elem.text)
            
        request_id_elem = root.find("request_id")
        if request_id_elem is not None:
            self.request_id = request_id_elem.text

register_message_type("weather_radarAcknowledgment", weather_radarAcknowledgment)
