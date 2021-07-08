# -*- coding: utf-8 -*-
"""
Created on Wed Jul  7 15:47:27 2021

@author: jpeacock
"""
from pathlib import Path
from obspy import read, UTCDateTime
from obspy.core.inventory import read_inventory

from mt_metadata.timeseries.stationxml import XMLInventoryMTExperiment
from mth5.mth5 import MTH5
from mth5.timeseries import RunTS

station = "CAS04"
h5_fn = Path(r"c:\Users\jpeacock\from_iris_dmc.h5")
if h5_fn.exists():
    h5_fn.unlink()

# get the data
streams = read(r"c:\Users\jpeacock\Documents\test_data\miniseed_cas04\cas04.mseed") 

# get the metadata
inventory = read_inventory(r"c:\Users\jpeacock\Documents\test_data\miniseed_cas04\cas04_response.xml")
# translate obspy.core.Inventory to an mt_metadata.timeseries.Experiment
translator = XMLInventoryMTExperiment()
experiment = translator.xml_to_mt(inventory)
run_metadata = experiment.surveys[0].stations[0].runs[0]

# initiate MTH5 file
m = MTH5()
m.open_mth5(h5_fn, "w")

# fill metadata
m.from_experiment(experiment)
station_group = m.get_station(station)

# runs can be split into channels with similar start times and sample rates
start_times = sorted(list(set([tr.stats.starttime.isoformat() for tr in streams])))
end_times = sorted(list(set([tr.stats.endtime.isoformat() for tr in streams])))

for index, times in enumerate(zip(start_times, end_times), 1):
    run_stream = streams.slice(UTCDateTime(times[0]), UTCDateTime(times[1]))
    run_ts_obj = RunTS()
    run_ts_obj.from_obspy_stream(run_stream, run_metadata)
    
    
    run_group = station_group.add_run(f"{index:03}")
    run_group.from_runts(run_ts_obj)
    
    
m.close_mth5()
    
    