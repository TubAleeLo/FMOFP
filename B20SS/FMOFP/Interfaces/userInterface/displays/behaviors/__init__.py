"""
Display Behaviors Package

Provides behavior handlers for connecting data sources to display nodes.
Behaviors handle the logic of updating display nodes based on external data.
"""

from .fms_orientation_behavior import FMSOrientationBehavior, get_fms_orientation_behavior

__all__ = [
    'FMSOrientationBehavior',
    'get_fms_orientation_behavior'
]
