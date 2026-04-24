import time
import board
import busio
import digitalio
import adafruit_bme680


class BMEControllerI2C:
    def __init__(self, sea_level_pressure=1013.25):
        # Create I2C bus
        self.i2c = board.I2C()

        # Initialize sensor
        # If you wired SDO to GND, add address=0x76 inside the parentheses
        self.sensor = adafruit_bme680.Adafruit_BME680_I2C(self.i2c)

        self.sensor.sea_level_pressure = sea_level_pressure

    def get_data(self):
        """Returns a dictionary of all sensor readings."""
        return {
            "temperature": self.sensor.temperature,
            "pressure": self.sensor.pressure,
            "altitude": self.sensor.altitude,
            "humidity": self.sensor.relative_humidity,
            "gas": self.sensor.gas
        }

    def calibrate_ground_level(self):
        """Sets the current pressure as the 0-meter reference."""
        print("Calibrating ground level...")
        readings = [self.sensor.pressure for _ in range(20)]
        self.sea_level_pressure = sum(readings) / len(readings)
        self.sensor.sea_level_pressure = self.sea_level_pressure
        print(f"Ground reference set to {self.sea_level_pressure:.2f} hPa")


# --- Example Usage ---
if __name__ == "__main__":
    # Initialize with local sea level pressure if known
    bme = BMEControllerI2C()
    bme.calibrate_ground_level()

    try:
        while True:
            data = bme.get_data()
            print(f"Alt: {data['altitude']:.2f}m | Temp: {data['temperature']:.1f}C")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nExiting...")