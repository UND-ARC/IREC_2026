import adi
import numpy as np

sdr = adi.Pluto("usb:7.5.5")
sdr.sample_rate             = int(1e6)
sdr.rx_rf_bandwidth         = int(1e6)
sdr.rx_lo                   = int(915e6)
sdr.gain_control_mode_chan0 = "manual"
sdr.rx_hardwaregain_chan0   = 20
sdr.rx_buffer_size          = 10000

print("Receiving — Ctrl+C to stop")
while True:
    samples = sdr.rx()
    power   = np.mean(np.abs(samples)**2)
    peak    = np.max(np.abs(samples)**2)
    print(f"power={power:.0f}  peak={peak:.0f}")