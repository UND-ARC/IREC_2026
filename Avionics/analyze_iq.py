import numpy as np
import struct

PREAMBLE_LEN = 64
SYNC         = b'\xDE\xAD\xBE\xEF'
TX_BUFFER_SAMPLES = 8192

samples = np.load("captured_iq.npy")
print(f"Loaded {len(samples)} samples")
print(f"Power: {np.mean(np.abs(samples)**2):.1f}")

# Plot constellation to see what the signal looks like
try:
    import matplotlib.pyplot as plt
    # Take middle chunk to avoid transients
    mid   = len(samples) // 2
    chunk = samples[mid:mid + TX_BUFFER_SAMPLES]

    plt.figure(figsize=(12, 4))

    plt.subplot(1, 3, 1)
    plt.scatter(np.real(chunk), np.imag(chunk), s=1, alpha=0.3)
    plt.title("Raw constellation")
    plt.axis('equal')
    plt.grid(True)

    # After x^4 freq correction
    s4          = chunk ** 4
    phase_diff  = s4[1:] * np.conj(s4[:-1])
    freq_offset = np.angle(np.mean(phase_diff)) / (2 * np.pi * 4)
    print(f"Estimated freq offset: {freq_offset * 5e6:.1f} Hz")
    t           = np.arange(len(chunk))
    corrected   = chunk * np.exp(-1j * 2 * np.pi * freq_offset * t)

    plt.subplot(1, 3, 2)
    plt.scatter(np.real(corrected), np.imag(corrected), s=1, alpha=0.3)
    plt.title(f"After freq correction\n(offset={freq_offset*5e6:.0f} Hz)")
    plt.axis('equal')
    plt.grid(True)

    # Power over time
    plt.subplot(1, 3, 3)
    power_trace = np.abs(samples) ** 2
    plt.plot(power_trace[::10])
    plt.title("Power over time (decimated 10x)")
    plt.xlabel("Sample / 10")
    plt.ylabel("Power")
    plt.grid(True)

    plt.tight_layout()
    plt.savefig("iq_analysis.png", dpi=150)
    print("Saved iq_analysis.png")
    plt.show()

except ImportError:
    print("matplotlib not installed — skipping plots")

# Try brute force demod across the entire capture
print("\nSearching entire capture for sync word...")
found_at = []
for start in range(0, len(samples) - TX_BUFFER_SAMPLES, TX_BUFFER_SAMPLES // 4):
    chunk = samples[start:start + TX_BUFFER_SAMPLES]

    # x^4 freq correction per chunk
    s4          = chunk ** 4
    phase_diff  = s4[1:] * np.conj(s4[:-1])
    freq_offset = np.angle(np.mean(phase_diff)) / (2 * np.pi * 4)
    t           = np.arange(len(chunk))
    chunk       = chunk * np.exp(-1j * 2 * np.pi * freq_offset * t)

    data = chunk[PREAMBLE_LEN:]
    for rot in [1+0j, 0+1j, -1+0j, 0-1j]:
        s      = data * rot
        i_bits = (np.real(s) > 0).astype(np.uint8)
        q_bits = (np.imag(s) > 0).astype(np.uint8)
        bits   = np.empty(len(i_bits) * 2, dtype=np.uint8)
        bits[0::2] = i_bits
        bits[1::2] = q_bits
        bits   = bits[:len(bits) - len(bits) % 8]
        result = np.packbits(bits).tobytes()
        if SYNC in result:
            found_at.append((start, rot))
            print(f"  SYNC FOUND at sample offset {start}, rotation {rot}")
            break

if not found_at:
    print("  SYNC NOT FOUND anywhere in capture")
    print("  This means either:")
    print("  1. TX stopped before RX captured signal (check power trace)")
    print("  2. Frequency offset too large for x^4 corrector")
    print("  3. Sample rate mismatch between TX and RX")