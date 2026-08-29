"""
Rule 005 - SUSPICIOUS_CONFIGURATION_CHANGE. DELIBERATELY NOT
IMPLEMENTED YET. This module exists as a placeholder so the rule
numbering/file layout matches the spec, and so nobody mistakes its
absence for an oversight - it's a documented, deliberate scope
decision.

    unexpected PLC configuration/register modification
    -> SUSPICIOUS_CONFIGURATION_CHANGE

Why we can't build this honestly yet:

    Modbus TCP, as implemented in Milestone 2, has NO built-in
    authentication or authorization. This is not a bug in our
    simulator - it's a faithful reproduction of the real protocol's
    biggest well-known security weakness: any client that can reach
    the TCP port can send a "write single register" (FC06) or "write
    multiple registers" (FC16) request, and our server (like most real
    PLCs on unsegmented OT networks) will honor it with no check on
    who's asking.

    To detect a "suspicious" configuration change, a rule needs to
    distinguish a LEGITIMATE write (nobody currently writes to our
    registers except the simulator's own internal updater loop) from
    an UNAUTHORIZED one (an external Modbus client writing directly to
    a register, bypassing the PLC's control logic entirely). We have
    not yet built:

      1. Any mechanism that allows/models a legitimate external write
         at all (e.g. an "engineering workstation" that's supposed to
         be able to push setpoint changes).
      2. Any way for the collector/detection engine to observe WHO
         wrote a value or WHEN, as opposed to just what the current
         value is - Modbus registers only ever expose current state,
         not write history or origin.

    Faking this rule (e.g. "alert if the pump-state register doesn't
    match what we expect" using knowledge only the simulator's
    internals have) would violate the same rule this whole detection
    engine has to respect in the collector layer: never assume access
    you would not actually have in a real deployment.

When this gets built for real, it will need at minimum: a write-audit
path on the Modbus server (logging every FC06/16 request with its
source), and a definition of what a legitimate writer looks like, to
compare against - a natural companion to Milestone 12
(network security integration / Wireshark/Suricata/Zeek), since a
Modbus write instrumentation layer is itself a form of security
monitoring.
"""
