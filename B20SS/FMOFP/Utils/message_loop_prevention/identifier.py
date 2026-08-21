"""
Message Identifier Module

This module provides utilities for identifying and fingerprinting messages
regardless of their type or structure.
"""

import hashlib
import json
import time
import uuid
import sys
from typing import Any, Dict, List, Optional, Union, Callable, Set
from FMOFP.Utils.logger.sys_logger import get_logger

# NOTE (production readiness re-analysis, August 2026): this module had no
# `logger` defined anywhere -- four separate `except Exception:` blocks in
# `_serialize_for_hashing()` below call `logger.debug(...)` to report a
# fallback path (dict-conversion failure, dict/set item sorting failure),
# but referencing that undefined name raises a NameError from inside the
# except handler itself, which is not caught by that same handler and
# would propagate up to whatever called this module -- silently masking
# the original (comparatively harmless) fallback with a real crash.
# Found via `ruff check --select F821` (undefined-name); confirmed live
# after this fix that the fallback paths log correctly instead of raising.
logger = get_logger()

class MessageIdentifier:
    """Dynamically identifies and fingerprints messages regardless of type."""
    
    @staticmethod
    def generate_message_id(message: Any) -> str:
        """Generate a unique identifier for a message based on its content and type.
        
        Args:
            message: The message to generate an ID for
            
        Returns:
            A unique string identifier for the message
        """
        # Extract message type dynamically
        message_type = MessageIdentifier._extract_message_type(message)
        
        # Extract request ID or generate one if missing
        request_id = MessageIdentifier._extract_request_id(message)
        
        # Extract timestamp or use current time
        timestamp = MessageIdentifier._extract_timestamp(message)
        
        # Generate a hash of key message properties
        content_hash = MessageIdentifier._generate_content_hash(message)
        
        # Combine all components into a unique ID
        return f"{message_type}:{request_id}:{timestamp}:{content_hash}"
    
    @staticmethod
    def _extract_message_type(message: Any) -> str:
        """Extract message type from various message formats.
        
        Args:
            message: The message to extract the type from
            
        Returns:
            The message type as a string
        """
        # Check common locations for message type
        locations = [
            lambda m: m.get('message_type') if isinstance(m, dict) else None,
            lambda m: m.get('metadata', {}).get('message_type') if isinstance(m, dict) else None,
            lambda m: m.get('additional_info', {}).get('message_type') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'message_type', None) if hasattr(m, 'message_type') else None,
            lambda m: getattr(m, 'metadata', {}).get('message_type') if hasattr(m, 'metadata') else None,
            lambda m: getattr(m, 'additional_info', {}).get('message_type') if hasattr(m, 'additional_info') else None,
            lambda m: m.get('command_type') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'command_type', None) if hasattr(m, 'command_type') else None,
        ]
        
        for extractor in locations:
            try:
                message_type = extractor(message)
                if message_type:
                    return str(message_type)
            except (AttributeError, TypeError, ValueError):
                continue
                
        # Default type if none found
        return "unknown_type"
    
    @staticmethod
    def _extract_request_id(message: Any) -> str:
        """Extract request ID from various message formats.
        
        Args:
            message: The message to extract the request ID from
            
        Returns:
            The request ID as a string
        """
        # STEP 1: Check if message is MIL_STD_1553B_Message by class name
        if 'MIL_STD_1553B_Message' in str(type(message).__name__):
            # Handle MIL_STD_1553B_Message directly
            if hasattr(message, 'request_id') and message.request_id:
                return str(message.request_id)
            
            # Check message.metadata for MIL_STD_1553B_Message
            if hasattr(message, 'metadata') and isinstance(message.metadata, dict):
                if 'request_id' in message.metadata:
                    return str(message.metadata['request_id'])
                
            # Generate a UUID for MIL_STD_1553B_Message if no request_id found
            return str(uuid.uuid4())
        
        # STEP 2: Convert to dict if it's not a dict but has __dict__
        if not isinstance(message, dict) and hasattr(message, '__dict__'):
            try:
                # Convert object to dictionary
                message_dict = message.__dict__
                
                # Check if the converted dict has request_id
                if 'request_id' in message_dict:
                    return str(message_dict['request_id'])
                    
                # Check if metadata contains request_id
                if 'metadata' in message_dict and isinstance(message_dict['metadata'], dict):
                    if 'request_id' in message_dict['metadata']:
                        return str(message_dict['metadata']['request_id'])
                        
                # Use original object for further processing if dict conversion didn't help
                message = message_dict
            except Exception:
                # If conversion fails, continue with original message
                logger.debug("MessageIdentifier: dict conversion failed, using original message", exc_info=True)
        
        # STEP 3: Proceed with existing extraction logic
        # Check common locations for request ID
        locations = [
            lambda m: m.get('request_id') if isinstance(m, dict) else None,
            lambda m: m.get('metadata', {}).get('request_id') if isinstance(m, dict) else None,
            lambda m: m.get('additional_info', {}).get('request_id') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'request_id', None) if hasattr(m, 'request_id') else None,
            lambda m: getattr(m, 'metadata', {}).get('request_id') if hasattr(m, 'metadata') else None,
            lambda m: getattr(m, 'additional_info', {}).get('request_id') if hasattr(m, 'additional_info') else None,
            lambda m: m.get('id') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'id', None) if hasattr(m, 'id') else None,
            lambda m: m.get('transaction_id') if isinstance(m, dict) else None,
            lambda m: m.get('metadata', {}).get('transaction_id') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'transaction_id', None) if hasattr(m, 'transaction_id') else None,
        ]
        
        request_id = None
        for extractor in locations:
            try:
                request_id = extractor(message)
                if request_id:
                    return str(request_id)
            except (AttributeError, TypeError, ValueError):
                continue
        
        # STEP 4: Return a generated UUID as fallback instead of raising an error
        return str(uuid.uuid4())
    @staticmethod
    def _extract_timestamp(message: Any) -> float:
        """Extract timestamp from various message formats.
        
        Args:
            message: The message to extract the timestamp from
            
        Returns:
            The timestamp as a float
        """
        # Check common locations for timestamp
        locations = [
            lambda m: m.get('timestamp') if isinstance(m, dict) else None,
            lambda m: m.get('metadata', {}).get('timestamp') if isinstance(m, dict) else None,
            lambda m: m.get('additional_info', {}).get('timestamp') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'timestamp', None) if hasattr(m, 'timestamp') else None,
            lambda m: getattr(m, 'metadata', {}).get('timestamp') if hasattr(m, 'metadata') else None,
            lambda m: getattr(m, 'additional_info', {}).get('timestamp') if hasattr(m, 'additional_info') else None,
            lambda m: m.get('created_at') if isinstance(m, dict) else None,
            lambda m: getattr(m, 'created_at', None) if hasattr(m, 'created_at') else None,
        ]
        
        for extractor in locations:
            try:
                timestamp = extractor(message)
                if timestamp is not None:
                    # Convert to float if it's a string
                    if isinstance(timestamp, str):
                        try:
                            return float(timestamp)
                        except (ValueError, TypeError):
                            pass
                    # Return as is if it's already a number
                    elif isinstance(timestamp, (int, float)):
                        return float(timestamp)
            except (AttributeError, TypeError, ValueError):
                continue
                
        # Use current time if none found
        return time.time()
    
    @staticmethod
    def _generate_content_hash(message: Any) -> str:
        """Generate a hash of key message properties.
        
        Args:
            message: The message to generate a hash for
            
        Returns:
            A hash of the message content
        """
        try:
            # Convert message to a serializable format with cycle detection
            serialized = MessageIdentifier._serialize_for_hashing(message, set())
            
            # Generate hash
            hash_obj = hashlib.md5(json.dumps(serialized, sort_keys=True).encode('utf-8'))
            return hash_obj.hexdigest()
        except Exception as e:
            # Fallback to a simpler hash if serialization fails
            try:
                # Try to get a simple representation
                if isinstance(message, dict):
                    # Use request_id and message_type if available
                    request_id = message.get('request_id', '')
                    message_type = message.get('message_type', '')
                    command_type = message.get('command_type', '')
                    simple_hash = f"{request_id}:{message_type}:{command_type}"
                    hash_obj = hashlib.md5(simple_hash.encode('utf-8'))
                    return hash_obj.hexdigest()
                elif hasattr(message, 'request_id') and hasattr(message, 'message_type'):
                    # Use request_id and message_type if available
                    request_id = getattr(message, 'request_id', '')
                    message_type = getattr(message, 'message_type', '')
                    command_type = getattr(message, 'command_type', '')
                    simple_hash = f"{request_id}:{message_type}:{command_type}"
                    hash_obj = hashlib.md5(simple_hash.encode('utf-8'))
                    return hash_obj.hexdigest()
                else:
                    # Use string representation
                    hash_obj = hashlib.md5(str(type(message)).encode('utf-8'))
                    return hash_obj.hexdigest()
            except Exception:
                # Last resort: use a random hash
                return hashlib.md5(str(uuid.uuid4()).encode('utf-8')).hexdigest()
    
    @staticmethod
    def _serialize_for_hashing(obj: Any, visited: Set[int]) -> Any:
        """Serialize an object for hashing with cycle detection.
        
        Args:
            obj: The object to serialize
            visited: Set of object IDs that have already been visited
            
        Returns:
            A serializable representation of the object
        """
        def is_logger_object(obj):
            """Safely determine if an object is a Logger instance."""
            # Check for most common logger types
            return (obj.__class__.__name__ in ('Logger', 'SysLogger', 'RootLogger', 'LoggerAdapter') or
                    hasattr(obj, 'debug') and hasattr(obj, 'info') and 
                    hasattr(obj, 'warning') and hasattr(obj, 'error'))
        # Check for cycles
        obj_id = id(obj)
        if obj_id in visited:
            return "<circular-reference>"
        
        # Add to visited set
        visited.add(obj_id)
        
        try:
            # Handle None
            if obj is None:
                return None
                
            # Handle basic types
            if isinstance(obj, (str, int, float, bool)):
                return obj
                
            # Special case for logger objects
            if is_logger_object(obj):
                logger_name = getattr(obj, 'name', 'unknown')
                return f"<logger:{logger_name}>"
                
            # Handle lists and tuples
            if isinstance(obj, (list, tuple)):
                return [MessageIdentifier._serialize_for_hashing(item, visited.copy()) for item in obj]
                
                # Handle dictionaries
            if isinstance(obj, dict):
                # Filter out metadata fields that change with each processing
                filtered_dict = {}
                # Get list of items, attempt sorting safely
                items = list(obj.items())
                try:
                    # Check if any keys are None
                    has_none_keys = any(k is None for k, v in items)
                    # Check if any keys or values are logger objects
                    has_logger = any(is_logger_object(k) or is_logger_object(v) for k, v in items)
                    
                    if not has_logger and not has_none_keys:
                        # Only attempt sorting if no logger objects or None keys are present
                        items = sorted(items)
                    # Otherwise, use unsorted list
                except Exception:
                    # If any error occurs during sorting, fall back to unsorted list
                    logger.debug("MessageIdentifier: dict item sorting failed, using unsorted", exc_info=True)
                
                for k, v in items:
                    # Skip processing metadata
                    if k == 'metadata' and isinstance(v, dict):
                        metadata = {mk: mv for mk, mv in v.items() 
                                  if not mk.startswith('_processed_by') and mk != '_processing_timestamp'}
                        if metadata:
                            filtered_dict[k] = MessageIdentifier._serialize_for_hashing(metadata, visited.copy())
                    # Skip processing flags
                    elif isinstance(k, str) and not k.startswith('_processed_by'):
                        filtered_dict[k] = MessageIdentifier._serialize_for_hashing(v, visited.copy())
                
                return filtered_dict
                
            # Handle sets
            if isinstance(obj, set):
                set_items = list(obj)
                try:
                    # Only sort if we don't have logger objects
                    has_logger = any(is_logger_object(item) for item in set_items)
                    if not has_logger:
                        set_items = sorted(set_items)
                except Exception:
                    # If sorting fails, use the original order
                    logger.debug("MessageIdentifier: set item sorting failed, using original order", exc_info=True)
                return [MessageIdentifier._serialize_for_hashing(item, visited.copy()) for item in set_items]
                
            # Handle objects with __dict__ attribute
            if hasattr(obj, '__dict__'):
                obj_dict = {}
                for k, v in obj.__dict__.items():
                    # Skip processing metadata
                    if k == 'metadata' and isinstance(v, dict):
                        metadata = {mk: mv for mk, mv in v.items() 
                                  if not mk.startswith('_processed_by') and mk != '_processing_timestamp'}
                        if metadata:
                            obj_dict[k] = MessageIdentifier._serialize_for_hashing(metadata, visited.copy())
                    # Skip processing flags
                    elif isinstance(k, str) and not k.startswith('_processed_by'):
                        obj_dict[k] = MessageIdentifier._serialize_for_hashing(v, visited.copy())
                
                return obj_dict
                
            # Handle objects with to_dict method
            if hasattr(obj, 'to_dict') and callable(getattr(obj, 'to_dict')):
                try:
                    obj_dict = obj.to_dict()
                    return MessageIdentifier._serialize_for_hashing(obj_dict, visited.copy())
                except Exception:
                    logger.debug("MessageIdentifier: to_dict() failed, falling through to __str__", exc_info=True)

            # Handle objects with __str__ method
            if hasattr(obj, '__str__'):
                return str(obj)
                
            # Default to string representation
            return str(obj)
            
        except Exception as e:
            # If any error occurs, return a placeholder
            return f"<error-serializing-{type(obj).__name__}>"
        finally:
            # Remove from visited set
            visited.remove(obj_id)
