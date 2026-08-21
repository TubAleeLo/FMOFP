#!/usr/bin/env python
"""
Test Results Parser and Analyzer

This utility parses predefined_messages_latest_results.json and provides a rich formatted display
with summary statistics and detailed test results. It also provides recommendations for failed tests.
"""

import json
import sys
import os
from datetime import datetime
from pprint import pprint

def colorize(text, color_code):
    """Colorize text for terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def red(text):
    return colorize(text, "31")

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

def parse_results(results_file="predefined_messages_latest_results.json"):
    """Parse the JSON results file"""
    try:
        with open(results_file, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: Results file '{results_file}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: '{results_file}' is not a valid JSON file.")
        return None

def display_header(data):
    """Display header with test run information"""
    print()
    print(cyan("=" * 80))
    print(cyan(f"PREDEFINED MESSAGES TEST RESULTS"))
    print(cyan("=" * 80))
    
    print(f"Start Time: {data['start_time']}")
    print(f"End Time:   {data['end_time']}")
    print(f"Duration:   {data['duration_seconds']:.2f} seconds")
    print()
    
    # Summary statistics
    total = data['summary']['total']
    success = data['summary']['success']
    failure = data['summary']['failure']
    
    success_rate = success / total * 100 if total > 0 else 0
    
    print(f"Total Tests: {total}")
    print(f"Successful:  {green(str(success))} ({success_rate:.1f}%)")
    print(f"Failed:      {red(str(failure))} ({100 - success_rate:.1f}%)")
    print()

def display_system_results(system_name, tests):
    """Display results for a specific system"""
    print(magenta(f"=== {system_name} ==="))
    
    success_count = sum(1 for test in tests if test['success'])
    total_count = len(tests)
    success_rate = success_count / total_count * 100 if total_count > 0 else 0
    
    print(f"Tests: {total_count}, Success Rate: {success_rate:.1f}%\n")
    
    for test in tests:
        if test['success']:
            status = green("[PASS]")
        else:
            status = red("[FAIL]")
        
        print(f"{status} {test['name']}")
        
        if test['request_id']:
            print(f"       Request ID: {test['request_id']}")
            
        if test['error']:
            print(f"       Error: {yellow(test['error'])}")
            
            # Provide recommendation based on error type
            if "no attribute" in test['error']:
                print(f"       {blue('RECOMMENDATION:')} Implement the missing method in the appropriate class")
            elif "Failed to get request ID" in test['error']:
                print(f"       {blue('RECOMMENDATION:')} Check that the messaging system is properly handling request IDs")
        
        print()

def display_detailed_results(data):
    """Display detailed results by system"""
    for system_name, tests in data['by_system'].items():
        display_system_results(system_name, tests)

def main():
    results_file = "predefined_messages_latest_results.json"
    if len(sys.argv) > 1:
        results_file = sys.argv[1]
    
    data = parse_results(results_file)
    if data:
        display_header(data)
        display_detailed_results(data)

if __name__ == "__main__":
    main()
