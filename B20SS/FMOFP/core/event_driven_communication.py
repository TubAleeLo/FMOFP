"""
Event-Driven Communication System

This module implements a hybrid communication system that supports both:
1. Event-based publish-subscribe for general system events
2. Direct MIL-STD-1553B message handling for radar systems

Key features:
1. Thread-safe singleton EventBus
2. Asynchronous event processing
3. Topic-based subscription
4. MIL-STD-1553B message support
5. Enhanced message validation
"""

import threading
import time
from typing import Dict, List, Callable, Union
from queue import Queue
from FMOFP.MIL_STD_1553B.mil_std_1553B  import MIL_STD_1553B_Message
from Utils.logger.sys_logger import get_logger

logger = get_logger()

class Event:
    def __init__(self, topic: str, data: Dict):
        self.topic = topic
        self.data = data
        self.timestamp = time.time()

class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EventBus, cls).__new__(cls)
                    cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_queue = Queue()
        self.running = False
        self.thread = None
        self.started = False
        self._health_status = True
        self._last_event_time = time.time()
        self._event_count = 0
        self._error_count = 0

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic with callback."""
        try:
            with self._lock:
                if topic not in self.subscribers:
                    self.subscribers[topic] = []
                self.subscribers[topic].append(callback)
                logger.info(f"Subscribed callback to topic: {topic}")
        except Exception as e:
            logger.error(f"Error subscribing to topic {topic}: {e}")
            self._error_count += 1
            raise

    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """Remove a previously subscribed callback from a topic.

        Added (August 2026 re-analysis round, Round 11, EventBus
        subscriber leak sweep): subscribe() had no counterpart anywhere
        in this class -- every subscription was permanent for the life of
        the process. Since EventBus._handle_event() invokes every
        subscribed callback synchronously on every publish(), and several
        widgets (WeatherRadarWidget, HolographicMFD) are recreated over
        the app's lifetime via their respective display factories'
        cache-eviction/reset paths, each recreation subscribed a *new*
        callback without ever removing the old one -- confirmed live via
        get_weather_radar_widget(force_reset=True): the old widget
        instance's EventBus subscription (and therefore the old widget
        object itself, kept alive by the callback reference the
        subscribers list holds) was never released, and the stale
        callback kept firing on every subsequent publish(). Returns True
        if the callback was found and removed, False if the topic or
        callback wasn't present (not treated as an error -- callers may
        legitimately call this during cleanup without knowing whether the
        subscription is still there).
        """
        try:
            with self._lock:
                callbacks = self.subscribers.get(topic)
                if not callbacks or callback not in callbacks:
                    return False
                callbacks.remove(callback)
                logger.info(f"Unsubscribed callback from topic: {topic}")
                return True
        except Exception as e:
            logger.error(f"Error unsubscribing from topic {topic}: {e}")
            self._error_count += 1
            return False

    def publish(self, event: Union[Event, MIL_STD_1553B_Message]):
        """Publish an event or MIL-STD-1553B message."""
        try:
            # Validate message
            if not self._validate_message(event):
                return

            # Update metrics
            self._event_count += 1
            self._last_event_time = time.time()

            # Log based on message type
            if isinstance(event, MIL_STD_1553B_Message):
                logger.info(f"Publishing MIL-STD-1553B message: {event.message_type}")
            else:
                logger.info(f"Publishing event to topic: {event.topic}")

            # Add to queue
            self.event_queue.put(event)

        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            self._error_count += 1
            raise

    def _validate_message(self, message) -> bool:
        """Validate message format."""
        try:
            if isinstance(message, Event):
                return bool(message.topic and hasattr(message, 'data'))
            elif isinstance(message, MIL_STD_1553B_Message):
                return bool(message.message_type and hasattr(message, 'data'))
            else:
                logger.warning(f"Invalid message type: {type(message)}")
                return False
        except Exception as e:
            logger.error(f"Error validating message: {e}")
            return False

    def start(self):
        """Start the event bus."""
        try:
            with self._lock:
                if self.started:
                    logger.warning("EventBus is already started")
                    return
                if not self.running and (self.thread is None or not self.thread.is_alive()):
                    self.running = True
                    self.thread = threading.Thread(target=self._process_events, name="EventBus_Processor")
                    self.thread.daemon = True
                    self.thread.start()
                    self.started = True
                    self._health_status = True
                    logger.info("EventBus started successfully")
        except Exception as e:
            logger.error(f"Error starting EventBus: {e}")
            self._health_status = False
            raise

    def stop(self):
        """Stop the event bus."""
        try:
            with self._lock:
                if not self.started:
                    logger.warning("EventBus is not running")
                    return
                self.running = False
                if self.thread and self.thread.is_alive():
                    self.thread.join()
                self.started = False
                logger.info("EventBus stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping EventBus: {e}")
            self._health_status = False
            raise

    def _process_events(self):
        """Process events from queue."""
        logger.info("Event processing thread started")
        while self.running:
            try:
                # Check if we need to stop
                if not self.running:
                    break

                # Get next event if available
                if not self.event_queue.empty():
                    event = self.event_queue.get()
                    try:
                        if isinstance(event, MIL_STD_1553B_Message):
                            logger.info(f"Processing MIL-STD-1553B message: {event.message_type}")
                            self._handle_1553b_message(event)
                        else:
                            logger.info(f"Processing event for topic: {event.topic}")
                            self._handle_event(event)
                        self.event_queue.task_done()
                    except Exception as e:
                        logger.error(f"Error handling event: {e}")
                        self._error_count += 1
                else:
                    # No events to process, sleep briefly
                    time.sleep(0.1)

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                self._error_count += 1
                if not self.running:
                    break
                time.sleep(1)  # Sleep longer on error

        logger.info("Event processing thread ended")

    def _handle_event(self, event: Event):
        """Handle standard event."""
        if event.topic in self.subscribers:
            logger.info(f"Found {len(self.subscribers[event.topic])} subscribers for topic: {event.topic}")
            for callback in self.subscribers[event.topic]:
                try:
                    callback(event.data)
                    logger.info(f"Successfully executed callback for topic: {event.topic}")
                except Exception as e:
                    logger.error(f"Error processing event {event.topic}: {e}")
                    self._error_count += 1
        else:
            logger.warning(f"No subscribers found for topic: {event.topic}")

    def _handle_1553b_message(self, message: MIL_STD_1553B_Message):
        """Handle MIL-STD-1553B message."""
        try:
            # Route message based on RT address
            rt_address = message.rt_address
            if rt_address in self.subscribers:
                logger.info(f"Found subscribers for RT address: {rt_address}")
                for callback in self.subscribers[rt_address]:
                    try:
                        callback(message)
                        logger.info(f"Successfully routed message to RT: {rt_address}")
                    except Exception as e:
                        logger.error(f"Error routing message to RT {rt_address}: {e}")
                        self._error_count += 1
            else:
                logger.warning(f"No subscribers found for RT address: {rt_address}")
        except Exception as e:
            logger.error(f"Error handling 1553B message: {e}")
            self._error_count += 1

    def check_health(self) -> bool:
        """Enhanced health check."""
        try:
            with self._lock:
                # Check basic health
                basic_health = (
                    self.started and 
                    self.running and 
                    self.thread and 
                    self.thread.is_alive()
                )

                # Check event processing
                event_timeout = 60  # seconds
                event_processing_ok = (
                    time.time() - self._last_event_time < event_timeout or
                    self._event_count == 0  # No events yet is ok
                )

                # Check error rate
                error_threshold = 0.1  # 10% error rate threshold
                error_rate_ok = (
                    self._event_count == 0 or  # No events yet is ok
                    (self._error_count / self._event_count) < error_threshold
                )

                # Update overall health status
                self._health_status = all([
                    basic_health,
                    event_processing_ok,
                    error_rate_ok
                ])

                # Log health metrics
                logger.debug(f"EventBus Health Metrics:")
                logger.debug(f"- Basic Health: {basic_health}")
                logger.debug(f"- Event Processing: {event_processing_ok}")
                logger.debug(f"- Error Rate OK: {error_rate_ok}")
                logger.debug(f"- Event Count: {self._event_count}")
                logger.debug(f"- Error Count: {self._error_count}")

                return self._health_status

        except Exception as e:
            logger.error(f"Error checking EventBus health: {e}")
            self._health_status = False
            return False

    def is_running(self) -> bool:
        """Check if the event bus is running."""
        with self._lock:
            return (
                self.started and 
                self.running and 
                self.thread and 
                self.thread.is_alive() and
                self._health_status
            )

    def get_metrics(self) -> Dict:
        """Get event bus metrics."""
        with self._lock:
            return {
                'started': self.started,
                'running': self.running,
                'thread_alive': bool(self.thread and self.thread.is_alive()),
                'event_count': self._event_count,
                'error_count': self._error_count,
                'queue_size': self.event_queue.qsize(),
                'last_event_time': self._last_event_time,
                'health_status': self._health_status
            }

# Global instance
event_bus = EventBus()

def get_event_bus():
    """Get the global EventBus instance."""
    return event_bus
