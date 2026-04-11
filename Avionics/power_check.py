import adi
import numpy as np

sdr = adi.Pluto("usb:")
sdr.sample_rate             = 10_000_000
sdr.rx_rf_bandwidth         = 10_000_000
sdr.rx_lo                   = 915_000_000
sdr.gain_control_mode_chan0 = "fast_attack"
sdr.rx_buffer_size          = 8192

print("Watching for signal — start Pi TX now")
while True:
    samples = sdr.rx().astype(np.complex64)
    power   = np.mean(np.abs(samples)**2)
    print(f"power={power:.0f}")