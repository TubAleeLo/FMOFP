"""
Message Loop Prevention Decorators

This module provides decorators for integrating message loop prevention
with existing services.
"""

import functools
import inspect
import logging
from typing import Any, Callable, TypeVar, cast, Optional, Dict, Union, Awaitable

from FMOFP.Utils.message_loop_prevention.prevention import MessageLoopPrevention

# Type variables for function signatures
T = TypeVar('T')
R = TypeVar('R')

# Get logger
try:
    from FMOFP.Utils.logger.sys_logger import get_logger
    logger = get_logger()
except ImportError:
    # Fall back to standard logging if system logger not available
    logger = logging.getLogger(__name__)

def prevent_message_loops(service_name: str, log_level: str = 'warning'):
    """Decorator for service methods to prevent message loops.
    
    This decorator can be applied to any method that processes messages,
    and will prevent the method from processing the same message multiple times.
    
    Args:
        service_name: Name of the service (used for logging and metadata)
        log_level: Logging level for loop detection messages ('debug', 'info', 'warning', 'error')
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Get loop prevention service
            loop_prevention = MessageLoopPrevention.get_instance()
            
            # Find the message parameter
            message = _find_message_parameter(func, args, kwargs)
            
            if message is None:
                # If no message parameter found, just call the original function
                logger.debug(f"[LOOP_PREVENTION] No message parameter found for {func.__name__}, skipping loop prevention")
                return func(*args, **kwargs)
                
            # Process message
            should_process, enhanced_message = loop_prevention.process_message(message, service_name)
            
            # Skip processing if already processed
            if not should_process:
                _log_loop_detection(service_name, func.__name__, log_level)
                return None
                
            # Replace message in args or kwargs
            args, kwargs = _replace_message_parameter(func, args, kwargs, enhanced_message)
                
            # Call original function with enhanced message
            return func(*args, **kwargs)
            
        return wrapper
    
    return decorator

def prevent_message_loops_async(service_name: str, log_level: str = 'warning'):
    """Decorator for async service methods to prevent message loops.
    
    This decorator can be applied to any async method that processes messages,
    and will prevent the method from processing the same message multiple times.
    
    Args:
        service_name: Name of the service (used for logging and metadata)
        log_level: Logging level for loop detection messages ('debug', 'info', 'warning', 'error')
        
    Returns:
        Decorated async function
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get loop prevention service
            loop_prevention = MessageLoopPrevention.get_instance()
            
            # Find the message parameter
            message = _find_message_parameter(func, args, kwargs)
            
            if message is None:
                # If no message parameter found, just call the original function
                logger.debug(f"[LOOP_PREVENTION] No message parameter found for {func.__name__}, skipping loop prevention")
                return await func(*args, **kwargs)
                
            # Process message
            should_process, enhanced_message = loop_prevention.process_message(message, service_name)
            
            # Skip processing if already processed
            if not should_process:
                _log_loop_detection(service_name, func.__name__, log_level)
                return None
                
            # Replace message in args or kwargs
            args, kwargs = _replace_message_parameter(func, args, kwargs, enhanced_message)
                
            # Call original function with enhanced message
            return await func(*args, **kwargs)
            
        return wrapper
    
    return decorator

def _find_message_parameter(func: Callable, args: tuple, kwargs: Dict[str, Any]) -> Optional[Any]:
    """Find the message parameter in a function call.
    
    Args:
        func: The function being called
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        The message parameter, or None if not found
    """
    # Get function signature
    sig = inspect.signature(func)
    parameters = list(sig.parameters.values())
    
    # Skip 'self' parameter for instance methods
    if parameters and parameters[0].name == 'self':
        parameters = parameters[1:]
        
    # Check if there's a parameter named 'message'
    for i, param in enumerate(parameters):
        if param.name == 'message':
            # Check if it's in kwargs
            if 'message' in kwargs:
                return kwargs['message']
            # Check if it's in args
            elif i < len(args):
                return args[i]
    
    # If no parameter named 'message', try to find a parameter with a common message type name
    common_message_param_names = ['msg', 'data', 'event', 'payload', 'request', 'response']
    for name in common_message_param_names:
        for i, param in enumerate(parameters):
            if param.name == name:
                # Check if it's in kwargs
                if name in kwargs:
                    return kwargs[name]
                # Check if it's in args
                elif i < len(args):
                    return args[i]
    
    # If still not found, assume the first non-self parameter is the message
    if parameters:
        param = parameters[0]
        # Check if it's in kwargs
        if param.name in kwargs:
            return kwargs[param.name]
        # Check if it's in args
        elif len(args) > 0:
            return args[0]
    
    # No message parameter found
    return None

def _replace_message_parameter(func: Callable, args: tuple, kwargs: Dict[str, Any], enhanced_message: Any) -> tuple:
    """Replace the message parameter in a function call.
    
    Args:
        func: The function being called
        args: Positional arguments
        kwargs: Keyword arguments
        enhanced_message: The enhanced message
        
    Returns:
        Tuple of (args, kwargs) with the message parameter replaced
    """
    # Get function signature
    sig = inspect.signature(func)
    parameters = list(sig.parameters.values())
    
    # Skip 'self' parameter for instance methods
    if parameters and parameters[0].name == 'self':
        parameters = parameters[1:]
        
    # Check if there's a parameter named 'message'
    for i, param in enumerate(parameters):
        if param.name == 'message':
            # Check if it's in kwargs
            if 'message' in kwargs:
                kwargs['message'] = enhanced_message
                return args, kwargs
            # Check if it's in args
            elif i < len(args):
                args_list = list(args)
                args_list[i] = enhanced_message
                return tuple(args_list), kwargs
    
    # If no parameter named 'message', try to find a parameter with a common message type name
    common_message_param_names = ['msg', 'data', 'event', 'payload', 'request', 'response']
    for name in common_message_param_names:
        for i, param in enumerate(parameters):
            if param.name == name:
                # Check if it's in kwargs
                if name in kwargs:
                    kwargs[name] = enhanced_message
                    return args, kwargs
                # Check if it's in args
                elif i < len(args):
                    args_list = list(args)
                    args_list[i] = enhanced_message
                    return tuple(args_list), kwargs
    
    # If still not found, assume the first non-self parameter is the message
    if parameters:
        param = parameters[0]
        # Check if it's in kwargs
        if param.name in kwargs:
            kwargs[param.name] = enhanced_message
            return args, kwargs
        # Check if it's in args
        elif len(args) > 0:
            args_list = list(args)
            args_list[0] = enhanced_message
            return tuple(args_list), kwargs
    
    # No message parameter found, return original args and kwargs
    return args, kwargs

def _log_loop_detection(service_name: str, function_name: str, log_level: str) -> None:
    """Log a loop detection message.
    
    Args:
        service_name: Name of the service
        function_name: Name of the function
        log_level: Logging level
    """
    message = f"[LOOP_PREVENTION] Breaking loop - message already processed by {service_name}.{function_name}"
    
    if log_level.lower() == 'debug':
        logger.debug(message)
    elif log_level.lower() == 'info':
        logger.info(message)
    elif log_level.lower() == 'error':
        logger.error(message)
    else:
        # Default to warning
        logger.warning(message)
