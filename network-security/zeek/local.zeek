#
# Tells Zeek's built-in Modbus analyzer to treat port 5020 as Modbus
# traffic. Zeek's default port-based dispatch expects the registered
# standard (502) - Milestone 2 deliberately used 5020 instead (see
# simulator/modbus/server.py), so without this, Zeek would see the
# TCP stream but never hand it to the Modbus analyzer, and
# modbus.log would simply never appear.
#
@load base/protocols/modbus

event zeek_init()
	{
	Analyzer::register_for_ports(Analyzer::ANALYZER_MODBUS, set(5020/tcp));
	}
