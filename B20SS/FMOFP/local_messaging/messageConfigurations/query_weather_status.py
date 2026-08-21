from dataclasses import dataclass
from FMOFP.local_messaging.messageConfigurations.base_message import BaseMessage, register_message_type
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class QueryWeatherStatus(BaseMessage):
    pass

register_message_type("queryWeatherStatus", QueryWeatherStatus)
logger.info("queryWeatherStatus registered")