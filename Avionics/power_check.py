import adi
import numpy as np

sdr = adi.Pluto("usb:")
sdr.sample_rate             = 10_000_000
sdr.rx_rf_bandwidth         = 10_000_000
sdr.rx_lo                   = 915_000_000
sdr.gain_control_mode_chan0 = "slow_attack"  # try slow_attack this time
sdr.rx_buffer_size          = 8192

print(f"RX port: {sdr._ctrl.find_channel('voltage0', False).attrs['rf_port_select'].value}")
print(f"RX gain: {sdr._ctrl.find_channel('voltage0', False).attrs['hardwaregain'].value}")
print("Watching for signal...")

while True:
    samples = sdr.rx().astype(np.complex64)
    power   = np.mean(np.abs(samples)**2)
    print(f"power={power:.0f}")