"""
Base Radar Data Handler

Provides base functionality for radar data handling including:
1. Topic subscription management
2. Event handling
3. Display notification
4. Database operations
"""

import json
from typing import Dict, Any, Set, Optional
from dataclasses import dataclass
from FMOFP.core.event_driven_communication import Event, get_event_bus
from FMOFP.storage.DBM import DatabaseManager
from FMOFP.Utils.logger.sys_logger import get_logger

logger = get_logger()

@dataclass
class RadarEvent:
    """Data structure for radar events"""
    radar_type: str
    event_type: str
    data: Dict[str, Any]
    timestamp: float
    request_id: str
    additional_info: Optional[Dict[str, Any]] = None

class BaseRadarDataHandler:
    def __init__(self, radar_type: str, event_bus=None):
        """Initialize radar data handler.
        
        Args:
            radar_type (str): Type of radar (e.g., 'weather_radar', 'targeting_radar')
            event_bus: Optional event bus instance. If None, gets global instance.
        """
        self.radar_type = radar_type
        self.event_bus = event_bus or get_event_bus()
        self.subscribed_topics: Set[str] = set()
        self.command_registry: Dict[str, callable] = {}
        self.current_mode = None
        
        # Initialize database connection
        self.db_manager = DatabaseManager(config_path='FMOFP/dbConfig.xml')
        self.db = self.db_manager.get_system_db('radar_management')
        
        # Track subscribed displays
        self.subscribed_displays: Set[str] = set()
        
        # Initialize command registry
        self._init_command_registry()
        
        logger.info(f"Initialized {radar_type} data handler")

    def _init_command_registry(self):
        """Initialize command registry with default handlers"""
        self.command_registry.update({
            'mode_change': self.handle_mode_change,
            'data_update': self.handle_data_update,
            'status_update': self.handle_status_update
        })

    async def subscribe_to_topic(self, topic: str):
        """Subscribe to a radar topic with validation.
        
        Args:
            topic (str): Topic to subscribe to
            
        Raises:
            ValueError: If topic is invalid for this radar type
        """
        if not self._validate_topic(topic):
            raise ValueError(f"Invalid topic for {self.radar_type}: {topic}")
            
        topic_name = f"{self.radar_type}_{topic}"
        self.event_bus.subscribe(topic_name, self._handle_event)
        self.subscribed_topics.add(topic)
        
        # Store subscription in database
        await self._store_subscription(topic)
        logger.info(f"Subscribed to topic: {topic_name}")

    def _validate_topic(self, topic: str) -> bool:
        """Validate if topic is valid for this radar type.
        
        Args:
            topic (str): Topic to validate
            
        Returns:
            bool: True if topic is valid
        """
        from FMOFP.Interfaces.userInterface.displays.radar.radar_event_system.radar_topic_registry import RADAR_TOPIC_REGISTRY
        
        if self.radar_type not in RADAR_TOPIC_REGISTRY:
            return False
            
        radar_topics = RADAR_TOPIC_REGISTRY[self.radar_type]
        return (topic in radar_topics['data_types'] or
                topic in radar_topics['commands'] or
                topic in radar_topics['events'])

    async def _store_subscription(self, topic: str):
        """Store subscription in database.
        
        Args:
            topic (str): Topic being subscribed to
        """
        try:
            # NOTE: DBM.DBHandler.execute_query_async() is a synchronous,
            # fire-and-forget method (it submits to a worker thread pool and
            # returns None) - it is not `async def` and doesn't return an
            # awaitable, so `await`ing it here raised
            # "TypeError: object NoneType can't be used in 'await' expression"
            # on every call. Call it as the synchronous method it actually is.
            self.db.execute_query_async(
                """
                INSERT INTO radar_subscriptions 
                (radar_type, topic, subscriber_id) 
                VALUES (?, ?, ?)
                """,
                (self.radar_type, topic, str(id(self))),
                query_type='insert'
            )
        except Exception as e:
            logger.error(f"Error storing subscription: {e}")
            raise

    async def _handle_event(self, event: Event):
        """Handle incoming radar event.
        
        Args:
            event (Event): Event to handle
        """
        try:
            # Extract event type from topic
            topic_parts = event.topic.split('_')
            if len(topic_parts) < 3:  # radar_type_event_type
                logger.error(f"Invalid topic format: {event.topic}")
                return
                
            event_type = '_'.join(topic_parts[2:])
            
            # Create radar event
            radar_event = RadarEvent(
                radar_type=self.radar_type,
                event_type=event_type,
                data=event.data,
                timestamp=event.timestamp,
                request_id=event.data.get('request_id', ''),
                additional_info=event.data.get('additional_info')
            )
            
            # Store event
            await self._store_event(radar_event)
            
            # Handle based on event type
            if event_type in self.command_registry:
                await self.command_registry[event_type](radar_event)
            else:
                logger.warning(f"No handler for event type: {event_type}")
                
            # Notify displays
            await self.notify_displays(event_type, radar_event)
            
        except Exception as e:
            logger.error(f"Error handling event: {e}")
            raise

    async def _store_event(self, event: RadarEvent):
        """Store radar event in database.
        
        Args:
            event (RadarEvent): Event to store
        """
        try:
            # See NOTE in _store_subscription() above: execute_query_async()
            # is synchronous/fire-and-forget, not awaitable.
            self.db.execute_query_async(
                f"""
                INSERT INTO {self.radar_type}_data
                (request_id, timestamp, mode, data_type, data_value, additional_info)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.request_id,
                    event.timestamp,
                    self.current_mode or None,
                    event.event_type,
                    json.dumps(event.data),
                    json.dumps(event.additional_info) if event.additional_info else None
                ),
                query_type='insert'
            )
        except Exception as e:
            logger.error(f"Error storing event: {e}")
            raise

    async def handle_mode_change(self, event: RadarEvent):
        """Handle mode change event.
        
        Args:
            event (RadarEvent): Mode change event
        """
        try:
            new_mode = event.data.get('mode')
            if not new_mode:
                logger.error("Mode change event missing mode")
                return
                
            self.current_mode = new_mode
            logger.info(f"Mode changed to: {new_mode}")
            
        except Exception as e:
            logger.error(f"Error handling mode change: {e}")
            raise

    async def handle_data_update(self, event: RadarEvent):
        """Handle data update event.
        
        Args:
            event (RadarEvent): Data update event
        """
        try:
            data_type = event.data.get('data_type')
            if not data_type:
                logger.error("Data update event missing data_type")
                return
                
            # Store in type-specific table if exists
            table_name = f"{self.radar_type}_{data_type}"
            if await self._table_exists(table_name):
                await self._store_typed_data(table_name, event)
                
            logger.info(f"Processed data update: {data_type}")
            
        except Exception as e:
            logger.error(f"Error handling data update: {e}")
            raise

    async def handle_status_update(self, event: RadarEvent):
        """Handle status update event.
        
        Args:
            event (RadarEvent): Status update event
        """
        try:
            status = event.data.get('status')
            if not status:
                logger.error("Status update event missing status")
                return
                
            # Update status in database.
            # See NOTE in _store_subscription() above: execute_query_async()
            # is synchronous/fire-and-forget, not awaitable.
            self.db.execute_query_async(
                f"""
                UPDATE {self.radar_type}_data
                SET status = ?
                WHERE request_id = ?
                """,
                (status, event.request_id),
                query_type='update'
            )
            
            logger.info(f"Status updated: {status}")
            
        except Exception as e:
            logger.error(f"Error handling status update: {e}")
            raise

    async def notify_displays(self, topic: str, event: RadarEvent):
        """Notify subscribed displays of event.
        
        Args:
            topic (str): Event topic
            event (RadarEvent): Event data
        """
        try:
            # Create display message
            display_message = {
                'radar_type': self.radar_type,
                'topic': topic,
                'data': event.data,
                'timestamp': event.timestamp,
                'request_id': event.request_id,
                'additional_info': event.additional_info
            }
            
            # Publish to event bus for displays
            self.event_bus.publish(Event(
                topic=f"{self.radar_type}_display_update",
                data=display_message
            ))
            
            logger.info(f"Notified displays of {topic} event")
            
        except Exception as e:
            logger.error(f"Error notifying displays: {e}")
            raise

    async def _table_exists(self, table_name: str) -> bool:
        """Check if table exists in database.
        
        Args:
            table_name (str): Name of table to check
            
        Returns:
            bool: True if table exists
        """
        try:
            # NOTE: this needs the query's actual result, but
            # execute_query_async() is fire-and-forget and never returns one
            # (see NOTE in _store_subscription() above) - `await`ing it
            # previously raised a TypeError before `result` was ever
            # assigned. Use the synchronous execute_query(), which actually
            # returns the row list.
            result = self.db.execute_query(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name=?
                """,
                (table_name,),
                query_type='select'
            )
            return bool(result)
        except Exception as e:
            logger.error(f"Error checking table existence: {e}")
            return False

    async def _store_typed_data(self, table_name: str, event: RadarEvent):
        """Store typed data in specific table.
        
        Args:
            table_name (str): Name of table to store in
            event (RadarEvent): Event containing data
        """
        try:
            # Get column names for table.
            # See NOTE in _table_exists() above: use the synchronous
            # execute_query() since the actual rows are needed here.
            columns = self.db.execute_query(
                f"PRAGMA table_info({table_name})",
                query_type='select'
            )
            column_names = [col[1] for col in (columns or [])]
            
            # Build insert query
            data_dict = {**event.data}  # Copy data
            if event.additional_info:
                data_dict.update(event.additional_info)
                
            # Filter to only existing columns
            valid_data = {k: v for k, v in data_dict.items() if k in column_names}
            
            # Add required fields
            valid_data.update({
                'request_id': event.request_id,
                'timestamp': event.timestamp
            })
            
            # Build query
            columns_str = ', '.join(valid_data.keys())
            placeholders = ', '.join(['?' for _ in valid_data])
            query = f"""
                INSERT INTO {table_name} 
                ({columns_str}) 
                VALUES ({placeholders})
            """
            
            # Execute insert.
            # See NOTE in _store_subscription() above: execute_query_async()
            # is synchronous/fire-and-forget, not awaitable.
            self.db.execute_query_async(
                query,
                tuple(valid_data.values()),
                query_type='insert'
            )
            
            logger.info(f"Stored typed data in {table_name}")
            
        except Exception as e:
            logger.error(f"Error storing typed data: {e}")
            raise

    def is_healthy(self) -> bool:
        """Check if handler is healthy.
        
        Returns:
            bool: True if handler is healthy
        """
        try:
            return (
                self.event_bus and 
                self.event_bus.is_running() and
                self.db and
                bool(self.subscribed_topics)
            )
        except Exception as e:
            logger.error(f"Error checking health: {e}")
            return False
