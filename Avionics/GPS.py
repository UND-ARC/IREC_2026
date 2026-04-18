#GPS Compilation Code into Raspberry Pi 5
#GPS Part #W34813- Adafruit


#3.3V/5V (PIN 1) from Pi to 3.3V (need stepdown connector if 5V on Pi)
#GPIO14 (PIN 8) - transmit to RX - recieve
#GPIO15 (PIN 10) - recieve to TX - transmit
#GND (PIN 6) to GND

#Install Adafruit GPS library
#pip3 install adafruit-circuitpython-gps

import time
import board
import busio
import adafruit_gps
import serial

#UART connection
#uart = busio.UART(board.TX, board.RX, baudrate=9600, timeout=10)
# On Pi 5, /dev/ttyAMA0 is the default hardware UART
uart = serial.Serial("/dev/ttyAMA0", baudrate=9600, timeout=10)
gps = adafruit_gps.GPS(uart, debug=False)

# Initialize the GPS module by sending commands
# Turn on basic GGA and RMC info
gps.send_command(b'PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0')
# Set update rate to 1000ms (1Hz)
gps.send_command(b'PMTK220,1000')

while True:
    gps.update()
    if not gps.has_fix:
        print('Waiting for fix...')
        time.sleep(1)
        continue
    print('Latitude: {0:.6f} degrees'.format(gps.latitude))
    print('Longitude: {0:.6f} degrees'.format(gps.longitude))
    time.sleep(1)
