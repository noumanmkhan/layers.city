"""Run fetch_parking.py from a branch that isn't main (Scout Toronto data commits only raw/scouting/):
writes its files to raw/scouting/parking-fetch/, to be moved into raw/parking/ by hand. One-off, for the first data on dev."""
import os, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ['PARKING_OUT'] = os.path.join(HERE, 'raw', 'scouting', 'parking-fetch')
runpy.run_path(os.path.join(HERE, 'fetch_parking.py'), run_name='__main__')
