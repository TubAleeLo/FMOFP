#!/usr/bin/env python
"""
Predefined Messages Summary Tool

This utility analyzes the Messages.py file and its related message classes to provide
a comprehensive summary of available predefined messages for easy reference.
"""

import importlib
import inspect
import sys
import os
import asyncio
from pprint import pprint
import re

def colorize(text, color_code):
    """Colorize text for terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def green(text):
    return colorize(text, "32")

def yellow(text):
    return colorize(text, "33")

def blue(text):
    return colorize(text, "34")

def magenta(text):
    return colorize(text, "35")

def cyan(text):
    return colorize(text, "36")

async def initialize_messages():
    """Initialize Messages class to explore available methods"""
    try:
        # Import Messages class
        from FMOFP.Interfaces.predefinedMessages.Messages import Messages
        
        # Create instance
        messages = Messages()
        
        # Initialize
        await messages.initialize()
        
        return messages
    except Exception as e:
        print(f"Error initializing Messages: {e}")
        return None

def get_async_methods(obj):
    """Get all async methods from an object"""
    methods = []
    
    for name, method in inspect.getmembers(obj, inspect.ismethod):
        if inspect.iscoroutinefunction(method) and not name.startswith('_'):
            methods.append(name)
    
    return methods

async def get_method_signature(obj, method_name):
    """Get method signature information"""
    method = getattr(obj, method_name)
    
    # Get signature
    sig = inspect.signature(method)
    
    # Get docstring
    doc = inspect.getdoc(method) or "No documentation available"
    
    # Format parameters
    params = []
    for name, param in sig.parameters.items():
        if name == 'self':
            continue
            
        if param.default is inspect.Parameter.empty:
            params.append(f"{name}")
        else:
            params.append(f"{name}={param.default}")
    
    return {
        'name': method_name,
        'params': params,
        'doc': doc,
        'signature': f"{method_name}({', '.join(params)})"
    }

def display_radar_type(radar_type, methods):
    """Display methods for a particular radar type"""
    print(magenta(f"\n=== {radar_type.upper()} MESSAGES ==="))
    
    # Group by method type
    mode_methods = []
    data_methods = []
    other_methods = []
    
    for method in methods:
        if method.startswith(f'{radar_type}_to_') or '_mode' in method:
            mode_methods.append(method)
        elif 'request_' in method or 'get_' in method or 'update_' in method:
            data_methods.append(method)
        else:
            other_methods.append(method)
    
    # Display mode change methods
    if mode_methods:
        print(yellow("\nMode Change Methods:"))
        for method in sorted(mode_methods):
            print(f"  • {blue(method)}")
    
    # Display data request methods
    if data_methods:
        print(yellow("\nData Request/Update Methods:"))
        for method in sorted(data_methods):
            print(f"  • {blue(method)}")
    
    # Display other methods
    if other_methods:
        print(yellow("\nOther Methods:"))
        for method in sorted(other_methods):
            print(f"  • {blue(method)}")

async def analyze_messages():
    """Analyze Messages class and its contained radar modules"""
    messages = await initialize_messages()
    if not messages:
        return
    
    print(cyan("\n============================================================"))
    print(cyan("                PREDEFINED MESSAGES SUMMARY"))
    print(cyan("============================================================"))
    
    # Get all available message modules
    modules = []
    for attr_name in dir(messages):
        if not attr_name.startswith('_') and not attr_name == 'initialize':
            attr = getattr(messages, attr_name)
            if hasattr(attr, 'request_id') or hasattr(attr, 'send_message'):
                modules.append(attr_name)
    
    # Print available modules
    print(f"\nAvailable Message Modules: {', '.join(green(mod) for mod in sorted(modules))}")
    print("\nUse this format to call any predefined message: await messages.{module}.{method}(...)")
    
    # Display detailed methods for each radar type
    for module in sorted(modules):
        attr = getattr(messages, module)
        
        # Get async methods
        methods = get_async_methods(attr)
        
        # Display methods grouped by radar type
        display_radar_type(module, methods)
    
    print(cyan("\n============================================================"))
    print(yellow("\nUSAGE EXAMPLE:"))
    print("""
# Initialize messages
messages = Messages()
await messages.initialize()

# Send a weather radar mode change request
request_id = await messages.weather_radar.weather_radar_to_surveillance_mode()

# Request precipitation data
request_id = await messages.weather_radar.request_precipitation_data()
""")
    print(cyan("============================================================\n"))

async def main():
    await analyze_messages()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
