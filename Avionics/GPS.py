#GPS Compilation Code into Raspberry Pi 5
#GPS Part #W34813- Adafruit


#3.3V/5V (PIN 1) from Pi to 3.3V (need stepdown connector if 5V on Pi)
#GPIO14 (PIN 8) - transmit to RX - recieve
#GPIO15 (PIN 10) - recieve to TX - transmit
#GND (PIN 6) to GND

#Install Adafruit GPS library
#pip3 install adafruit-circuitpython-gps

import time
import threading
import adafruit_gps
import serial


class GPSController:
    def __init__(self):
        #UART connection
        #uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=10)
        # On Pi 5, /dev/ttyAMA0 is the default hardware UART
        self.uart = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=10)
        self.gps = adafruit_gps.GPS(self.uart, debug=False)

        # Initialize the GPS module by sending commands
        # Turn on basic GGA and RMC info
        self.gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
        # Set update rate to 1000ms (1Hz)
        self.gps.send_command(b'PMTK220,1000')

        self._running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()

    def _update_loop(self):
        """Background thread to keep the GPS buffer clear and data fresh."""
        while self._running:
            self.gps.update()
            time.sleep(0.1)

    @property
    def has_fix(self):
        return self.gps.has_fix

    def get_position(self):
        """Returns a dict of the current telemetry data."""
        if not self.has_fix:
            return None

        return {
            "lat": self.gps.latitude,
            "lon": self.gps.longitude,
            "alt": self.gps.altitude_m,
            "sats": self.gps.satellites,
            "speed_kn": self.gps.speed_knots,
            "timestamp": self.gps.timestamp_utc
        }

    def stop(self):
        self._running = False
        self.thread.join()
        self.uart.close()


# --- Example Usage ---
if __name__ == "__main__":
    my_gps = GPSController()

    try:
        print("Initializing GPS...")
        while True:
            pos = my_gps.get_position()

            if pos:
                print(f"Fix: {pos['lat']:.6f}, {pos['lon']:.6f} | Alt: {pos['alt']}m | Sats: {pos['sats']}")
            else:
                print("Waiting for satellite fix...")

            time.sleep(2)

    except KeyboardInterrupt:
        print("\nStopping GPS controller...")
        my_gps.stop()
