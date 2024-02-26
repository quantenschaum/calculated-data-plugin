# software includes geomag.py
# by Christopher Weiss cmweiss@gmail.com
# https://github.com/cmweiss/geomag
# Infos on NMEA0183 from:
# https://github.com/mak08/VRDashboard/issues/31
# https://www.nmea.org/Assets/100108_nmea_0183_sentences_not_recommended_for_new_designs.pdf
# http://www.plaisance-pratique.com/IMG/pdf/NMEA0183-2.pdf

import os
import re
import sys
import time
from math import isfinite, sin, cos, radians, degrees, sqrt, atan2

from avnav_nmea import NMEAParser

hasgeomag = False

try:
    sys.path.insert(0, os.path.dirname(__file__) + "/lib")
    import geomag

    hasgeomag = True
except:
    pass

VERSION = 20240226
SOURCE = "calculated-data"
KNOTS = 1.94384  # knots per m/s

FIELDS = {
    "LAT": "gps.lat",
    "LON": "gps.lon",
    "COG": "gps.track",
    "SOG": "gps.speed",
    "HDT": "gps.headingTrue",
    "HDM": "gps.headingMag",
    "STW": "gps.waterSpeed",
    "SET": "gps.currentSet",
    "DFT": "gps.currentDrift",
    "AWA": "gps.windAngle",
    "AWS": "gps.windSpeed",
    "TWA": "gps.trueWindAngle",
    "TWS": "gps.trueWindSpeed",
    "TWD": "gps.trueWindDirection",
    "GWA": "gps.groundWindAngle",
    "GWS": "gps.groundWindSpeed",
    "GWD": "gps.groundWindDirection",
    "VAR": "gps.magVariation",
    "LEE": "gps.leewayAngle",
    "HEL": "gps.heelAngle",
}

SENTENCES = {
    "SET,DFT": "${ID}VDR,{data.SET:.1f},T,,,{data.DFT*KNOTS:.1f},N",
    "HDM": "${ID}HDM,{data.HDM:.1f},M",
    "HDT": "${ID}HDT,{data.HDT:.1f},T",
    "TWD,TWS": "${ID}MWD,{data.TWD:.1f},T,,,{data.TWS*KNOTS:.1f},N,,",
    "TWA,TWS": "${ID}MWV,{data.TWA:.1f},T,{data.TWS*KNOTS:.1f},N,A",
    "AWA,AWS": "${ID}MWV,{data.AWA:.1f},R,{data.AWS*KNOTS:.1f},N,A",
}

PATH_PREFIX = "gps.calculated."
FILTER = ["$HDG", "$HDM", "$HDT", "$VHW", "$MWD", "$MWV", "$VWR"]
PERIOD = "period"
WMM_FILE = "wmm_file"
NMEA_FILTER = "nmea_filter"
PRIORITY = "priority"
TALKER_ID = "talker_id"
CONFIG = [
    {
        "name": PERIOD,
        "description": "compute period",
        "type": "FLOAT",
        "default": 1,
    },
    {
        "name": WMM_FILE,
        "description": "file with WMM-coefficents for magnetic deviation",
        "default": "WMM2020.COF",
    },
    {
        "name": NMEA_FILTER,
        "description": "filter for NMEA sentences to be sent",
        "default": "",
    },
    {
        "name": PRIORITY,
        "description": "NMEA source priority",
        "type": "NUMBER",
        "default": 50,
    },
    {
        "name": TALKER_ID,
        "description": "NMEA talker ID for emitted sentences",
        "default": "CA",
    },
]


class Plugin(object):
    @classmethod
    def pluginInfo(cls):
        return {
            "description": "calculates missing wind and course data from present input data",
            "version": VERSION,
            "config": CONFIG,
            "data": [
                {
                    "path": "gps.calculated.*",
                    "description": "calculated and copyied values",
                },
            ],
        }

    def __init__(self, api):
        self.api = api
        self.api.registerEditableParameters(CONFIG, self.changeParam)
        self.api.registerRestart(self.stop)
        self.variation_model = None
        self.saveAllConfig()

    def stop(self):
        pass

    def getConfigValue(self, name):
        defaults = self.pluginInfo()["config"]
        for cf in defaults:
            if cf["name"] == name:
                return self.api.getConfigValue(name, cf.get("default"))
        return self.api.getConfigValue(name)

    def saveAllConfig(self):
        d = {}
        defaults = self.pluginInfo()["config"]
        for cf in defaults:
            v = self.getConfigValue(cf.get("name"))
            d.update({cf.get("name"): v})
        self.api.saveConfigValues(d)
        return

    def changeConfig(self, newValues):
        self.api.saveConfigValues(newValues)

    def changeParam(self, param):
        self.api.saveConfigValues(param)
        self.config_changed = True

    def readValue(self, path):
        "prevents reading values that we self have calculated"
        a = self.api.getSingleValue(path, includeInfo=True)
        if a is not None and SOURCE not in a.source:
            return a.value

    def writeValue(self, data, key, path):
        "do not overwrite existing values"
        if key not in data:
            return
        a = self.api.getSingleValue(path, includeInfo=True)
        if a is None or SOURCE in a.source:
            self.api.addData(path, data[key])

    def mag_variation(self, lat, lon):
        if not self.variation_model:
            try:
                filename = self.getConfigValue(WMM_FILE)
                if "/" not in filename:
                    filename = os.path.join(
                        os.path.dirname(__file__) + "/lib", filename
                    )
                self.variation_model = geomag.GeoMag(filename)
                self.variation_time = 0
                self.variation = None
            except Exception as x:
                self.api.log(f"error loading WMM {x}")
                return
        if time.monotonic() - self.variation_time > 600:
            self.variation = self.variation_model.GeoMag(lat, lon).dec
            self.variation_time = time.monotonic()
        return self.variation

    def run(self):
        # print("start")
        self.api.setStatus("STARTED", "running")
        wait = float(self.getConfigValue(PERIOD))
        nmea_filter = self.getConfigValue(NMEA_FILTER)
        nmea_priority = int(self.getConfigValue(PRIORITY))
        ID = self.getConfigValue(TALKER_ID)
        while not self.api.shouldStopMainThread():
            # print("compute", time.monotonic())

            data = {k: self.readValue(p) for k, p in FIELDS.items()}

            if all(data.get(k) is not None for k in ("LAT", "LON")):
                data["VAR"] = self.mag_variation(data["LAT"], data["LON"])

            # print(data)
            present = {k for k in data.keys() if data[k] is not None}

            data = CourseData(**data)
            # print(data)
            calculated = {k for k in data.keys() if data[k] is not None}
            calculated -= present
            # print("present", present)
            # print("calculated", calculated)

            for k in data.keys():
                self.writeValue(data, k, PATH_PREFIX + k)

            sending = set()
            for f, s in SENTENCES.items():
                if all(k in calculated for k in f.split(",")):
                    s = eval(f"f'{s}'")
                    if NMEAParser.checkFilter(s, nmea_filter):
                        self.api.addNMEA(
                            s,
                            source=SOURCE,
                            addCheckSum=True,
                            sourcePriority=nmea_priority,
                        )
                    sending.add(s[:6])

            self.api.setStatus("NMEA", f"{present} --> {calculated} sending {sending}")
            time.sleep(wait)


class CourseData:
    """
    This class is a container for course data that tries to compute the missing pieces
    from the information that is supplied in the constructor.

    ## Units

    - direction - given in degrees within [0,360), relative to north, measured clockwise
    - angles - as directions, but given in degrees within [-180,+180), relative to HDG
      If you want angles in the range [0,360), set anlges360=True in the constructor.
    - speeds - given in any speed unit (but all the same), usually knots

    ## Definitions

    HDG = heading, unspecified which of the following
    HDT = true heading, direction bow is pointing to, relative to true north (also HDGt)
    HDM = magnetic heading, as reported by a calibrated compass (also HDGm)
    HDC = compass heading, raw reading of the compass (also HDGc)
    VAR = magnetic variation, given in chart or computed from model
    DEV = magnetic deviation, boat specific, depends on HDG
    COG = course over ground, usually from GPS
    SOG = speed over ground, usually from GPS
    SET = set, direction of tide/current, cannot be measured directly
    DFT = drift, rate of tide/current, cannot be measured directly
    STW = speed through water, usually from paddle wheel, water speed vector projected onto HDT (long axis of boat)
    HEL = heel angle, measured by sensor or from heel polar TWA/TWS -> HEL
    LEE = leeway angle, angle between HDT and direction of water speed vector, usually estimated from wind and/or heel and STW
    CRS = course through water
    AWA = apparent wind angle, measured by wind direction sensor
    AWD = apparent wind direction, relative to true north
    AWS = apparent wind speed, measured by anemometer
    TWA = true wind angle, relative to water, relative to HDT
    TWD = true wind direction, relative to water, relative true north
    TWS = true wind speed, relative to water
    GWA = ground wind angle, relative to ground, relative to HDT
    GWD = ground wind direction, relative to ground, relative true north
    GWS = ground wind speed, relative to ground

    Beware! Wind direction is the direction where the wind is coming FROM, SET,HDG,COG is the direction where the tide/boat is going TO.

    also see https://t1p.de/5th2j and https://t1p.de/628t7

    ## Magnetic Directions

    All directions, except HDM, are relative to true north. This is because a magnetic compass gives you a magnetic
    direction (heading or bearing). You convert it to true using deviation and variation and that's it.

    You could use something like COG magnetic, but it does not make any sense and is error-prone.
    Don't do this! If you do need this for output, then do the conversion to magnetic at the very end,
    after all calculations are done.

    ## Equations

    All of the mentioned quantities are linked together by the following equations. Some of them are
    vector equations, vectors are polar vectors of the form [angle,radius]. The (+) operator denotes the addition of
    polar vectors. see https://math.stackexchange.com/questions/1365622/adding-two-polar-vectors
    An implementation of this addition is given below in add_polar().

    ### Heading

    - HDT = HDM + VAR = HDC + DEV + VAR
    - HDM = HDT - VAR = HDC + DEV

    ### Leeway and Course

    - LEE = LEF * HEL / STW^2
    - CRS = HDT + LEE

    With leeway factor LEF = 0..20, boat specific

    ### Course, Speed and Tide

    - [COG,SOG] = [CRS,STW] (+) [SET,DFT]
    - [SET,DFT] = [COG,SOG] (+) [CRS,-STW]

    ### Wind

    angles and directions are always converted like xWD = xWA + HDT and xWA = xWD - HDT

    - [AWD,AWS] = [GWD,GWS] (+) [COG,SOG]
    - [AWD,AWS] = [TWD,TWS] (+) [CRS,STW]
    - [AWA,AWS] = [TWA,TWS] (+) [LEE,STW]

    - [TWD,TWS] = [GWD,GWS] (+) [SET,DFT]
    - [TWD,TWS] = [AWD,AWS] (+) [CRS,-STW]
    - [TWA,TWS] = [AWA,AWS] (+) [LEE,-STW]

    - [GWD,GWS] = [AWD,AWS] (+) [COG,-SOG]

    In the vector equations angle and radius must be transformed together, always!

    ## How to use it

    Create CourseData() with the known quantities supplied in the constructor. Then access the calculated
    quantities as d.TWA or d.["TWA"]. Ask with "TWD" in d if they exist. Just print(d) to see what's inside.
    See test() for examples.
    """

    def __init__(self, **kwargs):
        self._data = kwargs
        self.angles360 = kwargs.get("angles360", False)
        self.compute_missing()

    def compute_missing(self):
        if self.misses("HDM") and self.has("HDC", "DEV"):
            self.HDM = to360(self.HDC + self.DEV)

        if self.misses("HDT") and self.has("HDM", "VAR"):
            self.HDT = to360(self.HDM + self.VAR)

        if self.misses("HDM") and self.has("HDT", "VAR"):
            self.HDM = to360(self.HDT - self.VAR)

        if self.misses("LEF") and self.has("HEL", "STW"):
            self.LEF = 10

        if self.misses("LEE") and self.has("HEL", "STW", "LEF"):
            self.LEE = (
                max(-30, min(30, self.LEF * self.HEL / self.STW**2))
                if self.STW
                else 0
            )

        if self.misses("LEE"):
            self.LEE = 0

        if self.misses("CRS") and self.has("HDT", "LEE"):
            self.CRS = self.HDT + self.LEE

        if self.misses("SET", "DFT") and self.has("COG", "SOG", "CRS", "STW"):
            self.SET, self.DFT = add_polar((self.COG, self.SOG), (self.CRS, -self.STW))

        if self.misses("COG", "SOG") and self.has("SET", "DFT", "CRS", "STW"):
            self.COG, self.SOG = add_polar((self.SET, self.DFT), (self.CRS, self.STW))

        if self.misses("TWA", "TWS") and self.has("AWA", "AWS", "STW", "LEE"):
            self.TWA, self.TWS = add_polar((self.AWA, self.AWS), (self.LEE, -self.STW))
            self.TWA = self.angle(self.TWA)

        if self.misses("TWD", "TWS") and self.has("GWD", "GWS", "SET", "DFT"):
            self.TWD, self.TWS = add_polar((self.GWD, self.GWS), (self.SET, self.DFT))

        if self.misses("TWD") and self.has("TWA", "HDT"):
            self.TWD = to360(self.TWA + self.HDT)

        if self.misses("TWA") and self.has("TWD", "HDT"):
            self.TWA = self.angle(self.TWD - self.HDT)

        if self.misses("GWD", "GWS") and self.has("TWD", "TWS", "SET", "DFT"):
            self.GWD, self.GWS = add_polar((self.TWD, self.TWS), (self.SET, -self.DFT))

        if self.misses("GWA") and self.has("GWD", "HDT"):
            self.GWA = self.angle(self.GWD - self.HDT)

        if self.misses("AWA", "AWS") and self.has("TWA", "TWS", "LEE", "STW"):
            self.AWA, self.AWS = add_polar((self.TWA, self.TWS), (self.LEE, self.STW))
            self.AWA = self.angle(self.AWA)

        if self.misses("AWD") and self.has("AWA", "HDT"):
            self.AWD = to360(self.AWA + self.HDT)

    def __getattribute__(self, item):
        if re.match("[A-Z]+", item):
            return self._data.get(item)
        return super(CourseData, self).__getattribute__(item)

    def __setattr__(self, key, value):
        if re.match("[A-Z]+", key):
            self._data[key] = value
        else:
            self.__dict__[key] = value

    def __getitem__(self, item):
        return self._data.get(item)

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, item):
        v = self[item]
        return v is not None and (type(v) != float or isfinite(v))

    def __str__(self):
        return "\n".join(f"{k}={self[k]}" for k in self.keys())

    def keys(self):
        return sorted(filter(self.__contains__, self._data.keys()))

    def has(self, *args):
        return all(x in self for x in args)

    def misses(self, *args):
        return any(x not in self for x in args)

    def angle(self, a):
        return to360(a) if self.angles360 else to180(a)


def to360(a):
    "limit a to [0,360)"
    while a < 0:
        a += 360
    return a % 360


def to180(a):
    "limit a to [-180,+180)"
    return to360(a + 180) - 180


def toCart(p):
    # to cartesian with phi going clock-wise from north
    return p[1] * sin(radians(p[0])), p[1] * cos(radians(p[0]))


def toPol(c):
    # to polar with phi going clock-wise from north
    return to360(90 - degrees(atan2(c[1], c[0]))), sqrt(c[0] ** 2 + c[1] ** 2)


def add_polar(a, b):
    "sum of polar vectors (phi,r)"
    a, b = toCart(a), toCart(b)
    s = a[0] + b[0], a[1] + b[1]
    return toPol(s)
