import time
import board
import adafruit_bno055


class IMUController:
    def __init__(self):
        self.i2c = board.I2C()
        self.sensor = adafruit_bno055.BNO055_I2C(self.i2c)

    def get_orientation(self):
        """Returns Euler angles and Quaternions."""
        return {
            "yaw": self.sensor.euler[0],  # 0-360 degrees
            "roll": self.sensor.euler[1],
            "pitch": self.sensor.euler[2],
            "quat": self.sensor.quaternion,  # (x, y, z, w)
            "cal": self.sensor.calibration_status  # (sys, gyro, accel, mag)
        }

    def get_motion(self):
        """Returns linear acceleration (gravity removed) and angular velocity."""
        return {
            "accel": self.sensor.linear_acceleration,  # m/s^2
            "gyro": self.sensor.gyro  # rad/s
        }

    def is_calibrated(self):
        """Returns True if the system is fully calibrated."""
        sys, gyro, accel, mag = self.sensor.calibration_status
        return sys == 3 and gyro == 3 and accel == 3 and mag == 3


# --- Example Usage ---
if __name__ == "__main__":
    imu = IMUController()

    print("Pre-flight IMU Check...")
    try:
        while True:
            data = imu.get_orientation()
            motion = imu.get_motion()

            # Calibration is critical for BNO055.
            # Status 0 = Uncalibrated, 3 = Fully Calibrated.
            sys, gyro, accel, mag = data['cal']

            print(f"CAL: S{sys} G{gyro} A{accel} M{mag} | "
                  f"H: {data['yaw'] or 0:.1f}° | "
                  f"P: {data['pitch'] or 0:.1f}° | "
                  f"R: {data['roll'] or 0:.1f}°")

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping IMU...")