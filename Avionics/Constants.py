
Pluto_Ground_IP = "192.168.4.1"
Pluto_Ground_Hostname = "ip:pluto-ground.local"
Pluto_Pi_IP = "192.168.3.1"
Pluto_Pi_Hostname = "ip:pluto-pi.local"

Laptop_IP = "10.42.0.1"
Laptop_Port = 10001

CALLSIGN = "K0VDR"

IS_FLIGHT_MODE = True   # Set TRUE for RF, Set false for Ethernet to laptop
USE_OVERLAY    = True    # Set TRUE to draw telemetry overlay

if IS_FLIGHT_MODE:
    BITRATE = 500_000
    IDR_VAL = 10
else:
    BITRATE = 3_000_000
    IDR_VAL  = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"






