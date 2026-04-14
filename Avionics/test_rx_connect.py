# test_rx_connect.py
import gnuradio.iio as iio
import Constants

s = iio.fmcomms2_source_fc32(
    Constants.Pluto_Ground_IP,
    [True, False, False, False],
    32768,
)
s.set_frequency(Constants.RX_FREQ)
s.set_samplerate(Constants.SAMP_RATE)
s.set_gain_mode(0, "manual")
s.set_gain(0, Constants.RX_GAIN)
print("Connected to ground Pluto OK")