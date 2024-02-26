# Calculated Data Plugin for AvNav

This plugin calculates wind and course data from the data that is supplied to AvNav.

## Calculated Data

It calculates the Magnetic Variation at the actual position based on the [World Magnetic Model 2020](https://www.ngdc.noaa.gov/).
Using this variation, it can calculate true heading from magnetic heading and vice-versa.

If COG/SOG and HDT/STW are supplied, it will calculate set and drift SET/DFT.

It will calculate true wind angle TWA and speed TWS from apparent wind angle AWA and speed AWS and water speed STW.

All calculated and input values are available in AvNav under `gps.calculated.*`. It reads its input data from the AvNav data model, after NMEA parsing hase been done by AvNav.

It also can write NMEA sentences (`VDR,HDM,HDT,MWD,MWV`), which are parsed by AvNav itself and are forwarded to NMEA outputs. 
