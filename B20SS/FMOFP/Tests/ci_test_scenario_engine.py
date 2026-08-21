"""CI test — ScenarioEngine parses both XML scenario files."""
import sys
sys.path.insert(0, '.')

from FMOFP.Interfaces.scenarios.scenarioEngine import ScenarioEngine

engine = ScenarioEngine()
ok = engine.load('trainingScenario.xml')
assert ok, "Failed to load trainingScenario.xml"
status = engine.get_status()
assert status['events_total'] > 0, "No events parsed from training scenario"
print(f"Training scenario: {status['events_total']} events parsed OK")

engine2 = ScenarioEngine()
ok2 = engine2.load('failureScenario.xml')
assert ok2, "Failed to load failureScenario.xml"
status2 = engine2.get_status()
assert status2['events_total'] > 0, "No events parsed from failure scenario"
print(f"Failure scenario: {status2['events_total']} events parsed OK")

print("Scenario engine: all assertions passed")
