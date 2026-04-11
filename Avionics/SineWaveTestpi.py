import adi
import numpy as np

sdr = adi.Pluto("ip:pluto.local")
sdr.sample_rate      = int(1e6)
sdr.tx_rf_bandwidth  = int(1e6)
sdr.tx_lo            = int(915e6)
sdr.tx_hardwaregain_chan0 = -50  # very low for direct cable
sdr.tx_cyclic_buffer = True      # repeat forever

# Simple sine wave at +100kHz offset
N       = 10000
t       = np.arange(N) / 1e6
samples = 0.5 * np.exp(2.0j * np.pi * 100e3 * t)
samples *= 2**14

sdr.tx(samples)
print("Transmitting — press Ctrl+C to stop")
import time
while True:
    time.sleep(1)