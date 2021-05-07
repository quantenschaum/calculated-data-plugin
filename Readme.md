AvNav more-nmea Plugin
===========================

This project provides a plugin for [AvNav](https://www.wellenvogel.net/software/avnav/docs/beschreibung.html?lang=en) 
calculating additional useful data .

Basically this software uses the [AvNav Plugin Interface](https://www.wellenvogel.net/software/avnav/docs/hints/plugins.html?lang=en)
to calculate:

  MagVar (Magnetic Variation)    -> "gps.MagVar" (based on the World Magnetic Model 2020 der NOAA (https://www.ngdc.noaa.gov/)

if the internal data store in AvNav contains apparent Winddata ("gps.windReference"=="R", Windangle "gps.windAngle" and Windspeed "gps.WindSpeed") it calculates:

- AWD (Apparent WindDirection)  -> "gps.AWD"
  
- TWD (True WindDirection)      -> "gps.TWD"
  
- TWS (True Windspeed in m/s)   -> "gps.TWS" 
  
- TWA (True Windangle)          -> "gps.TWA" 
  
in case of true Winddata ("gps.windReference"=="T") no calculation of winddata is done!



in addition it listens for incoming NMEA records regarding course and speed.
if course NMEA records are found ($HDM or $HDG or $VHW) it calculates:

- HDGm (Heading magnetic)       -> "gps.HDGm" 
  
- HDGt (Heading true) 	        -> "gps.HDGt"

in case of $VHW it will create also
  
- STW (Speed through water)      -> "gps.STW"
  


License: [MIT](LICENSE.md)


Installation
------------
You can use the plugin in 2 different ways.
1.  Download the source code as a zip and unpack it into a directory /home/pi/avnav/data/plugins/more-nmea.
    If the directory does not exist just create it. On an normal linux system (not raspberry pi) the directory will be /home/(user)/avnav/plugins/more-nmea.
    In this case the name of the plugin will be user-more-nmea. So you can modify the files and adapt them to your needs.

1.  Download the package provided in the releases section or build your own package using buildPackage.sh (requires a linux machine with docker installed). Install the package using the command
    ```
    sudo dpkg -i avnav-more-nmea-plugin...._all.deb
    ```

User App
--------
The plugin registers no [User App](https://www.wellenvogel.net/software/avnav/docs/userdoc/addonconfigpage.html?lang=en#h1:ConfigurationofUserApps) 

Configuration (Server)
-------------
No configuration necessary


Widget
------
The plugin provides no specific Widget.
One can use the default widget from avnav to visualize the data by selecting the appropriate gps... message. 

Formatter
---------
To display values and charts in a proper unit ther necessary formatters are included in the default widget. 


Implementation Details
----------------------


STW (Spead through Water) is taken from $VHW.
Take care for NMEA200 Sources:  
- The Signalk-Plugin "sk-to-nmea0183" transmits this message only if Heading und magnetic Variation Data are available in Signalk.

- canboat instead sends $VHW also without Heading!

HDGt (Heading True) is calculated from HDGm (Heading magnetic from $HDM or $HDG or $VHW) taking into account the magnetic variation if no True Heading Data is received.

Receiving True Heading overwrites calculated Data!

If magnetic variation is received (by $VHW orr $HDG) the calculated variation is no more used!
              

Package Building
----------------
For a simple package building [NFPM](https://nfpm.goreleaser.com/) is used and started in a docker container (use [buildPkg.sh](buildPkg.sh)). In the [package.yaml](package.yaml) the properties of the packge can be set. 

Additionally a [GitHub workflow](.github/workflows/createPackage.yml) has been set up to create a release and build a package whenever you push to the release branch.
So when you fork this repository you can create a package even without a local environment.
To trigger a package build at GitHub after forking just create a release branch and push this.
