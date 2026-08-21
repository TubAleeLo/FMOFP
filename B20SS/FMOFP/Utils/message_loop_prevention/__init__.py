"""
Message Loop Prevention Package

This package provides utilities for preventing message loops in the radar system,
particularly for VIL (Vertically Integrated Liquid) and precipitation data.
"""

from FMOFP.Utils.message_loop_prevention.identifier import MessageIdentifier
from FMOFP.Utils.message_loop_prevention.registry import MessageRegistry
from FMOFP.Utils.message_loop_prevention.prevention import MessageLoopPrevention
from FMOFP.Utils.message_loop_prevention.decorators import prevent_message_loops, prevent_message_loops_async
from FMOFP.Utils.message_loop_prevention.middleware import MessageLoopPreventionMiddleware, get_loop_prevention_middleware
from FMOFP.Utils.message_loop_prevention.config import MessageLoopPreventionConfig, get_config

__all__ = [
    'MessageIdentifier',
    'MessageRegistry',
    'MessageLoopPrevention',
    'prevent_message_loops',
    'prevent_message_loops_async',
    'MessageLoopPreventionMiddleware',
    'get_loop_prevention_middleware',
    'MessageLoopPreventionConfig',
    'get_config',
]

# Version information
__version__ = '0.3.0'
