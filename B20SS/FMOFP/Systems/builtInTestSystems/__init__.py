"""
Built-In Test Systems

This system encompasses the built-in test (BIT) and diagnostic capabilities integrated across 
the FMOFP's various systems. Key functions include:

- Performing power-on self tests (POST) during system initialization
- Periodic BIT testing during operation 
- Fault isolation and diagnostics
- Interface testing between subsystems

The BIT systems execute defined test sequences, monitor results against expected values, and
report detected faults. This allows issues to be identified proactively before failures occur,
and also aids in troubleshooting efforts when problems do arise.
"""