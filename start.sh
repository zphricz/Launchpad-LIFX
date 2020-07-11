rm -f nohup.out
pkill -f launchpad-lifx.py
nohup ./launchpad-lifx.py &
