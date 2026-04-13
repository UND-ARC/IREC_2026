#Pluto_Ground_IP = "192.168.2.110"# for some reason the config file didn't set the correct address so don't use this
Pluto_Ground_Hostname = "ip:pluto-ground.local"
#Pluto_Pi_IP = "192.168.2.90" # for some reason the config file didn't set the correct address so don't use this
Pluto_Pi_Hostname = "ip:pluto-pi.local"

Laptop_IP = "10.42.0.1"
Laptop_Port = 10001

IS_FLIGHT_MODE = True   # Set TRUE for RF, Set false for Ethernet to laptop
USE_OVERLAY    = True    # Set TRUE to draw telemetry overlay

if IS_FLIGHT_MODE:
    BITRATE = 800_000
    IDR_VAL = 15
else:
    BITRATE = 3_000_000
    IDR_VAL  = 60

MODE_STR = "FLIGHT" if IS_FLIGHT_MODE else "BENCH"

TX_FREQ           = 915_000_000
TX_BW             = 10_000_000
SAMPLE_RATE       = 10_000_000
RX_GAIN           = 20
RX_BUFFER_SAMPLES = 8192

TX_GAIN           = -50
TX_BUFFER_SAMPLES = 8192

CHUNK_SIZE        = 1024
PREAMBLE_LEN      = 64