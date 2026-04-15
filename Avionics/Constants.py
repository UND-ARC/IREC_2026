
Pluto_Ground_IP = "192.168.4.1"
Pluto_Ground_Hostname = "ip:pluto-ground.local"
Pluto_Pi_IP = "192.168.3.1"
Pluto_Pi_Hostname = "ip:pluto-pi.local"

Laptop_IP = "10.42.0.1"
Laptop_Port = 10001

IS_FLIGHT_MODE = True   # Set TRUE for RF, Set false for Ethernet to laptop
USE_OVERLAY    = False    # Set TRUE to draw telemetry overlay

if IS_FLIGHT_MODE:
    # BITRATE is the actual video payload (leaves room for shaking)
    BITRATE = 500_000
    # MUXRATE is the total pipe size. Must be just under your 750k radio limit
    MUXRATE = 720_000
    IDR_VAL = 10
else:
    BITRATE = 3_000_000
    IDR_VAL  = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"






