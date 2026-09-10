# Domain Reference for evo-seismic-data-io

**Responsibility**: Reading waveform files with ObsPy, parsing station CSV with Pandas, grouping traces by network.station, and building station dictionaries/DataFrames for downstream use.

**Key functions to implement**: load_waveforms, load_stations, group_traces_by_station, get_station_dict

---

## 1. ObsPy: Reading MiniSEED and Station Data


ObsPy is the *de facto* standard framework for processing seismological data using Python [cite: 1, 2]. It provides a comprehensive suite of utilities for handling time-series data, connecting to data centers, and managing metadata.

### 1.1 Reading MiniSEED Files

To load seismic waveform data, ObsPy provides a universal `read()` function. This function automatically detects the file format (such as MiniSEED, SAC, or StationXML) and returns a `Stream` object [cite: 2, 3].

**Function Signature and Return Type**
```python
import obspy

### 1.2 Creating an Inventory from CSV Station Metadata

Station metadata (coordinates, elevation, responses) is typically distributed in StationXML or dataless SEED formats, which ObsPy reads into an `obspy.core.inventory.Inventory` object [cite: 5]. However, if you are provided with a standard CSV file of station metadata, you must construct the `Inventory` manually or use an extension package like `obsplus` [cite: 6, 7].

**Method A: Pure ObsPy Manual Construction**
You can iterate over a Pandas DataFrame and build the hierarchical `Inventory` -> `Network` -> `Station` -> `Channel` structure [cite: 8, 9].

```python
import pandas as pd
from obspy.core.inventory import Inventory, Network, Station, Channel, Site

def csv_to_inventory(csv_path):
    df = pd.read_csv(csv_path)
    
    # Initialize an empty inventory
    inv = Inventory(networks=[], source="CustomCSV")
    
    # Group by network to avoid duplicate Network objects
    for net_code, net_df in df.groupby('network'):
        network = Network(code=net_code, stations=[])
        
        # Group by station within the network
        for sta_code, sta_df in net_df.groupby('station'):
            # Take the first row for station-level coordinates
            sta_info = sta_df.iloc
            station = Station(
                code=sta_code,
                latitude=sta_info['latitude'],
                longitude=sta_info['longitude'],
                elevation=sta_info['elevation'],
                site=Site(name=sta_code)
            )
            
            # Add channels to the station
            for _, row in sta_df.iterrows():
                channel = Channel(
                    code=row.get('channel', 'HHZ'),
                    location_code=row.get('location', ''),
                    latitude=row['latitude'],
                    longitude=row['longitude'],
                    elevation=row['elevation'],
                    depth=row.get('depth', 0.0),
                    sample_rate=row.get('sample_rate', 100.0)
                )
                station.channels.append(channel)
                
            network.stations.append(station)
        inv.networks.append(network)
        
    return inv
```

**Method B: Alternative Dictionary for Downstream Use**
Often, full `Inventory` objects are unnecessary if you only need station coordinates for phase association. A simple dictionary mapping is highly efficient:
```python
station_dict = {}
df = pd.read_csv("stations.csv")
for _, row in df.iterrows():
    # Use Network.Station as the key
    sta_key = f"{row['network']}.{row['station']}"
    station_dict[sta_key] = {
        'latitude': row['latitude'],
        'longitude': row['longitude'],
        'elevation': row['elevation']
    }
```

### 1.4 Grouping Traces by Station

SeisBench models often expect a 3-component stream (Z, N, E) for a single station to accurately pick phases. Standard `obspy.read()` may return a flat list of traces. You must group these traces by network and station.

```python
from collections import defaultdict
import obspy

def group_traces_by_station(stream):
    """Groups a flat ObsPy stream into a dictionary of 3C streams."""
    station_streams = defaultdict(obspy.Stream)
    
    for trace in stream:
        net = trace.stats.network
        sta = trace.stats.station
        key = f"{net}.{sta}"
        station_streams[key].append(trace)
        
    return station_streams