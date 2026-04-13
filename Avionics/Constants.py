
Pluto_Ground_IP = "ip:192.168.4.1"
Pluto_Ground_Hostname = "ip:pluto-ground.local"
Pluto_Pi_IP = "ip:192.168.3.1"
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




RX_FREQ    = 915_000_000
RX_GAIN           = 20   # dB, 0 to 73
RX_BUFFER_SAMPLES = 8192

TX_FREQ           = 915_000_000
TX_BW             = 10_000_000
TX_GAIN           = -50 # dB, -90 to 0
TX_BUFFER_SAMPLES = 8192

CHUNK_SIZE        = 1024
PREAMBLE_LEN      = 64
SAMP_RATE       = 1_000_000
SPS        = 4           # samples per symbol


