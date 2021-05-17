**AvNav more-nmea Plugin**

===========================



This project provides a plugin for AvNav to calculate additional (hopefully) useful data .



Basically this software uses the [AvNav Plugin Interface](https://www.wellenvogel.net/software/avnav/docs/hints/plugins.html?lang=en)

to calculate the Magnetic Variation on the actual position

 (based on the World Magnetic Model 2020 of [NOAA]([https://www.ngdc.noaa.gov/](https://www.ngdc.noaa.gov/)) )
 
if the internal data store in AvNav contains apparent Winddata ("gps.windReference"=="R", Windangle "gps.windAngle" and Windspeed "gps.WindSpeed") it calculates:

·  

| Value | Format | Storename | Description |
| --- | --- | --- | --- |
| MagVar | 0…360[°] | gps.MagVar | Magnetic Variation |
| AWA | +/- 180 [°] | gps.AWA | Apparent WindAngle |
| AWD | 0…360[°] | gps.AWD | Apparent WindDirection |
| AWS | 0..∞ [m/s] | gps.AWS | Apparent WindSpeed |
| TWA | +/- 180 [°] | gps.TWA | True WindAngle |
| TWD | 0…360[°] | gps.TWD | True WindDirection |
| TWS | 0..∞ [m/s] | gps.TWS | True WindSpeed |
|  |  |  |  |

· 

in case of true Winddata ("gps.windReference"=="T") **no** calculation of winddata is done!

in adition it listens for incoming NMEA records regarding course and speed.

if NMEA records with course data are received (\$HDM or \$HDG or \$VHW) it calculates:

| Value | Format | Storename | Description |
| --- | --- | --- | --- |
| HDGm | +/- 180 [°] | gps.HDGm | Heading magnetic |
| HDGt | +/- 180 [°] | gps.HDGt | Heading true |



in case of $VHW records it will also create 

| Value | Format | Storename | Description |
| --- | --- | --- | --- |
| STW | 0..∞ [m/s] | gps.STW | Speed through water |


**NEW**
Since Release 20210517 the Plugin is able to create the following NMEA records: **\$MWD,** **\$MWV,** **\$HDT,** **\$HDM and** **\$HDG**. These are are available i.e. on the SocketWriter Ports. They are only transmitted if the necessary signals are available and if there are no record with the same name in the NMEA data stream.
One can avoid to transmit a record by putting its name (i.e. “\$HDT”’) in the Filter_NMEA_OUT parameter.

The Plugin can be configured in the avnav-Server.xml with the following parmeters:

| Name | Default Value | Description |
| --- | --- | --- |
| WMM_FILE | "WMM2020.COF” | The WMM-Coefficent-File in the Plugin Directory |
| WMM_PERIOD | "10" | Intervall (sec) to calculate Variation |
| NMEAPeriod | “1” | Intervall (sec) to transmit new NMEA-records |
| computePeriod | "0.5” | Intervall (sec) to read NMEA-records |
| FILTER_NMEA_OUT | “” | Filter for transmitting new NMEA-records |



Please report any Errors to my [Repository](https://github.com/kdschmidt1/avnav-more-nmea-plugin/issues)


License: [MIT](LICENSE.md)





**Installation**

------------

You can use the plugin in 2 different ways.

1. Download the source code as a zip and unpack it into a directory /home/pi/avnav/data/plugins/more-nmea.

 If the directory does not exist just create it. On an normal linux system (not raspberry pi) the directory will be /home/(user)/avnav/plugins/more-nmea.

 In this case the name of the plugin will be user-more-nmea. So you can modify the files and adapt them to your needs.



1. Download the package provided in the releases section or build your own package using buildPackage.sh (requires a linux machine with docker installed). Install the package using the command

 ```

 sudo dpkg -i avnav-more-nmea-plugin...._all.deb

 ```



**User App**

--------

The plugin registers no [User App](https://www.wellenvogel.net/software/avnav/docs/userdoc/addonconfigpage.html?lang=en#h1:ConfigurationofUserApps)



Configuration (Server)

-------------

No configuration necessary





**Widget**

------

The plugin provides no specific Widget.

One can use the default widget from avnav to visualize the data by selecting the appropriate gps... message.



**Formatter**

---------

To display values in a proper unit the necessary formatters are included in the default widget.





**Implementation Details**

----------------------





STW (Spead through Water) is taken from \$VHW.

**Take care for NMEA200 Sources: **

- The Signalk-Plugin "sk-to-nmea0183" has some bugs:

It transmits this message only if Heading und magnetic Variation Data are available in Signalk.
 
- \$VHW false : see https://github.com/SignalK/signalk-to-nmea0183/issues/63

- \$HDG  false : Deviation instead of Variation



- the sentences from canboat are ok, as far as tested!



HDGt (Heading True) is calculated from HDGm (Heading magnetic from \$HDM or \$HDG or \$VHW) taking into account the magnetic variation if no True Heading Data is received.



Receiving True Heading overwrites calculated Data!



If magnetic variation is received (by \$VHW or \$HDG) the calculated variation is no more used!

             



**Package Building**

----------------

For a simple package building [NFPM](https://nfpm.goreleaser.com/) is used and started in a docker container (use [buildPkg.sh](buildPkg.sh)). In the [package.yaml](package.yaml) the properties of the packge can be set.



Additionally a [GitHub workflow](.github/workflows/createPackage.yml) has been set up to create a release and build a package whenever you push to the release branch.

So when you fork this repository you can create a package even without a local environment.

To trigger a package build at GitHub after forking just create a release branch and push this.**content****content**