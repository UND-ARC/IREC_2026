#!/bin/bash

# The -u flag forces Python to write logs instantly, saving them during a crash
python3 -u /home/arc/Github/IREC_2026/Avionics/LiveVideo.py &

python3 -u /home/arc/Github/IREC_2026/Avionics/TX_GNU_radio.py &



# Wait keeps the script running as long as the background tasks are running
wait