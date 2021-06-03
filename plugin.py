 # software includes geomag.py
# by Christopher Weiss cmweiss@gmail.com
# https://github.com/cmweiss/geomag
# Infos on NMEA0183 from:
      # https://github.com/mak08/VRDashboard/issues/31
      # https://www.nmea.org/Assets/100108_nmea_0183_sentences_not_recommended_for_new_designs.pdf
      # http://www.plaisance-pratique.com/IMG/pdf/NMEA0183-2.pdf

from avnav_nmea import NMEAParser
import math
import time
import os
from datetime import date
hasgeomag = False
import sys
try:
  # add current directory to sys.path to import library from there
  sys.path.insert(0, os.path.dirname(__file__) + '/lib')
  import geomag as geomag    
  hasgeomag = True
except:
  pass


class Config(object):

  def __init__(self, api):
    pass


class Plugin(object):
  PATHAWA = "gps.AWA"
  PATHAWD = "gps.AWD"
  PATHAWS = "gps.AWS"
  PATHTWD = "gps.TWD"
  PATHTWS = "gps.TWS"
  PATHTWA = "gps.TWA"
  PATHHDG_M = "gps.HDGm"
  PATHHDG_T = "gps.HDGt"
  PATHSTW = "gps.STW"
  PATHGMM = "gps.MagVar"
  WMM_FILE = 'WMM2020.COF'
  OWNID = 'IN'
  outFilter = []
 
  FILTER = ['$HDG','$HDM','$HDT','$VHW', '$MWD', '$MWV','$VWR']
  #FILTER = []
  CONFIG = [
      {
      'name': 'sourceName',
      'description': 'source name to be set for the generated records (defaults to more_nmea)',
      'default': 'more_nmea'
      },

      {
      'name':'WMM_FILE',
      'description':'File with WMM-coefficents for magnetic deviation',
      'default':'WMM2020.COF'
      },
      {
      'name':'WMM_PERIOD',
      'description':'Time in sec to recalculate magnetic deviation',
      'default':10,
      'type': 'NUMBER'
      },
      {
        'name':'computePeriod',
        'description': 'Compute period (s) for wind data',
        'type': 'FLOAT',
        'default': 0.5
      },
      {
        'name':'NewNMEAPeriod',
        'description': 'period (s) for NMEA records',
        'type': 'FLOAT',
        'default': 1
      },
      {
        'name':'FILTER_NMEA_OUT',
        'description': 'Filter  for transmitted NMEA records',
        'default': ""
      },
      ]

  @classmethod
  def pluginInfo(cls):
    """
    the description for the module
    @return: a dict with the content described below
            parts:
               * description (mandatory)
               * data: list of keys to be stored (optional)
                 * path - the key - see AVNApi.addData, all pathes starting with "gps." will be sent to the GUI
                 * description
    """
    return {
      'description': 'a plugin that calculates true wind data, magnetic deviation at the current position, speed through water and magnetic and true heading',
      'version': '1.0',
      'config': cls.CONFIG,
      'data': [
        {
          'path': cls.PATHAWD,
          'description': 'apparent Wind direction',
        },
        {
          'path': cls.PATHAWA,
          'description': 'apparent Wind angle',
        },
        {
          'path': cls.PATHAWS,
          'description': 'apparent Wind speed',
        },
        {
          'path': cls.PATHTWD,
          'description': 'true Wind direction',
        },
        {
          'path': cls.PATHTWS,
          'description': 'true Wind speed',
        },
        {
          'path': cls.PATHTWA,
          'description': 'true Wind angle',
        },
        {
          'path': cls.PATHHDG_M,
          'description': 'Heading Magnetic',
        },
        {
          'path': cls.PATHHDG_T,
          'description': 'Heading True',
        },
        {
          'path': cls.PATHSTW,
          'description': 'Speed through water',
        },
        {
          'path': cls.PATHGMM,
          'description': 'Magnetic Deviation',
        },
      ]
    }

  def __init__(self, api):
    """
        initialize a plugins
        do any checks here and throw an exception on error
        do not yet start any threads!
        @param api: the api to communicate with avnav
        @type  api: AVNApi
    """
    self.api = api
    self.api.registerEditableParameters(self.CONFIG, self.changeParam)
    self.api.registerRestart(self.stop)
    self.oldtime = 0
    self.variation_time = 0
    self.variation_val = None

    self.userAppId = None
    self.startSequence = 0
    self.receivedTags = []
    self.WindData = []
    self.source=self.api.getConfigValue("sourceName",None)
    self.saveAllConfig()
    
  def stop(self):
    pass
  
  def getConfigValue(self, name):
    defaults = self.pluginInfo()['config']
    for cf in defaults:
      if cf['name'] == name:
        return self.api.getConfigValue(name, cf.get('default'))
    return self.api.getConfigValue(name)
  
  def saveAllConfig(self):
    d = {}
    defaults = self.pluginInfo()['config']
    for cf in defaults:
      v = self.getConfigValue(cf.get('name'))
      d.update({cf.get('name'):v})
    self.api.saveConfigValues(d)
    return 
  
  def changeConfig(self, newValues):
    self.api.saveConfigValues(newValues)
  
  def changeParam(self, param):
    self.api.saveConfigValues(param)
    self.startSequence += 1

  def run(self):
    """
    the run method
    @return:
    """
    lastnmea = 0
    startSequence = None
    seq = 0
    self.api.log("started")
    self.api.setStatus('STARTED', 'running')
    gm = None
    computePeriod = 0.5
    source='more_nmea'
    while not self.api.shouldStopMainThread():
      if startSequence != self.startSequence:
        self.outFilter = self.getConfigValue('FILTER_NMEA_OUT')
        if not (isinstance(self.outFilter, list)):
            self.outFilter = self.outFilter.split(',')
        try:
          source=self.api.getConfigValue("sourceName",None)
          computePeriod = float(self.getConfigValue('computePeriod'))
          startSequence = self.startSequence
          if hasgeomag:
              wmm_filename = os.path.join(os.path.dirname(__file__) + '/lib', self.getConfigValue('WMM_FILE'))
              gm = geomag.GeoMag(wmm_filename)
        except:
          self.api.error(" WMM-File " + wmm_filename + 'not found!')
      lastTime = time.time()
      gpsdata = {}
      self.WindData = []

      computesVar = False
      computesWind = False
      try:
        gpsdata = self.api.getDataByPrefix('gps')
        if 'lat' in gpsdata and 'lon' in gpsdata and gm is not None:
          computesVar = True
          now = time.time()
          if now - self.variation_time > int(self.getConfigValue('WMM_PERIOD')) or now < self.variation_time:
            variation = gm.GeoMag(gpsdata['lat'], gpsdata['lon'])
            self.variation_time = now
            self.variation_val = variation.dec
            self.api.addData(self.PATHGMM, self.variation_val,source=source)
          else:
            self.api.addData(self.PATHGMM, self.variation_val,source=source)
      except Exception:
        self.api.error(" error in calculation of magnetic Variation")

      # fetch from queue till next compute period
      runNext = False
      while not runNext:
        now = time.time()
        if now < lastTime:
          # timeShift back
          runNext = True
          continue
        if ((now - lastTime) < computePeriod):
          waitTime = computePeriod - (now - lastTime)
        else:
          waitTime = 0.01
          runNext = True
        seq, data = self.api.fetchFromQueue(seq, number=100, waitTime=waitTime, includeSource=True,filter=self.FILTER)
        if len(data) > 0:
          for line in data:
            if not source in line.source : # KEINE Auswertung von selbst erzeugten Daten!!
                self.parseData(line.data, source=source)

      gpsdata = self.api.getDataByPrefix('gps')


      if 'AWA' in self.WindData:
        computesApparentWind = True
        computesWind = True
        if (self.calcTrueWind(gpsdata)):
            self.api.addData(self.PATHAWA, gpsdata['AWA'],source=source)
            self.api.addData(self.PATHAWD, gpsdata['AWD'],source=source)
            self.api.addData(self.PATHAWS, gpsdata['AWS'],source=source)
            self.api.addData(self.PATHTWD, gpsdata['TWD'],source=source)
            self.api.addData(self.PATHTWS, gpsdata['TWS'],source=source)
            self.api.addData(self.PATHTWA, gpsdata['TWA'],source=source)
      if computesVar or computesWind:
        stText = 'computing '
        if computesVar:
          stText += 'variation '
        if computesWind:
          stText += 'wind'
        self.api.setStatus('NMEA', stText)
      else:
        self.api.setStatus('STARTED', 'running')
      if((time.time() - lastnmea) > float(self.getConfigValue('NewNMEAPeriod'))):
          self.write_NMEA_records(gpsdata,source)
          self.receivedTags = []
          lastnmea = now

  def write_NMEA_records(self, gpsdata,source):
    #for testing:
    #self.receivedTags.sort()
    #print ("Received: "+self.receivedTags.__len__().__str__()+self.receivedTags.__str__())

    rectags = []
    rectags = self.receivedTags
    try:
        # $MWD = TWD & TWS          
        if not ('MWD' in self.receivedTags):
            if('TWD' in gpsdata and 'TWS' in gpsdata): 
                if('MagVar' in gpsdata):
                    s = self.make_sentence('MWD', gpsdata['TWD'], 'T', gpsdata['TWD'] - gpsdata['MagVar'], 'M', gpsdata['TWS'] * 1.94384, 'N', gpsdata['TWS'], 'M')
                else:
                    s = self.make_sentence('MWD', gpsdata['TWD'], 'T', '', 'M', gpsdata['TWS'] * 1.94384, 'N', gpsdata['TWS'], 'M')
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)


        if not ('MWV-T' in self.receivedTags):
            if('TWA' in gpsdata and 'TWS' in gpsdata): 
                s = self.make_sentence('MWV', gpsdata['TWA'], 'T', gpsdata['TWS'], 'M','A')
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)

        if not ('MWV-R' in self.receivedTags):
            if('AWA' in gpsdata and 'AWS' in gpsdata): 
                s = self.make_sentence('MWV', gpsdata['AWA'], 'R', gpsdata['AWS'], 'M','A')
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)

        if not ('HDM' in self.receivedTags):
            if('HDGm' in gpsdata):
                s = self.make_sentence('HDM', gpsdata['HDGm'], 'M')              
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)
                    
                    
        if not ('HDT' in self.receivedTags):
            if('HDGt' in gpsdata):
                s = self.make_sentence('HDT', gpsdata['HDGt'], 'T')              
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)
            
            
        if not ('HDG' in self.receivedTags):
            if('HDGm' in gpsdata):
                if('MagVar' in gpsdata):
                    s = self.make_sentence('HDG', gpsdata['HDGm'], '', '', gpsdata['MagVar'], 'E')      
                else:
                    s = self.make_sentence('HDG', gpsdata['HDGm'], '', '', '', '')      
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)
            elif('HDGt' in gpsdata and'MagVar' in gpsdata):
                s = self.make_sentence('HDG', gpsdata['HDGt'] - gpsdata['MagVar'], '', '', gpsdata['MagVar'], 'E')
                if NMEAParser.checkFilter(s, self.outFilter):
                    self.api.addNMEA(s, addCheckSum=True,source=source)
    except Exception:
        self.api.error(" error in NMEA writing")



      
  def make_sentence(self, title, *keys):
      s = '$' + self.OWNID + title
      for arg in keys:
          if(type(arg) == float or type(arg) == int):
              s = s + ',' + arg.__format__('06.2f')
          else:
              s = s + ',' + arg
      return(s)
  
  def nmeaChecksum(cls, part):
    chksum = 0
    if part[0] == "$" or part[0] == "!":
      part = part[1:]
    for s in part:
      chksum ^= ord(s)
    return ("%02X" % chksum)

  def parseData(self, data, source='internal'):
    valAndSum = data.rstrip().split("*")
    if len(valAndSum) > 1:
      sum = self.nmeaChecksum(valAndSum[0])
      if sum != valAndSum[1].upper():
        self.api.error("invalid checksum in %s, expected %s" % (data, sum))
        return
    darray = valAndSum[0].split(",")
    if len(darray) < 1 or (darray[0][0:1] != "$" and darray[0][0:1] != '!'):
      self.api.error("invalid nmea data (len<1) " + data + " - ignore")
      return False
    tag = darray[0][3:]
    if not tag in self.receivedTags:self.receivedTags.append(tag)
    rt = {}
    if(darray[0][1:3] == self.OWNID):
        test=3 # hier ist etwas schiefgelaufen

    try:
        
        
        
#VWR - Relative Wind Speed and Angle

#         1  2  3  4  5  6  7  8 9
#         |  |  |  |  |  |  |  | |
# $--VWR,x.x,a,x.x,N,x.x,M,x.x,K*hh<CR><LF>

# Field Number: 
#  1) Wind direction magnitude in degrees
#  2) Wind direction Left/Right of bow
#  3) Speed
#  4) N = Knots
#  5) Speed
#  6) M = Meters Per Second
#  7) Speed
#  8) K = Kilometers Per Hour
#  9) Checksum        
      if tag == 'VWR':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)
        rt['AWA'] = float(darray[1] or '0')
        rt['dir'] = darray[2] or ''
        if rt['dir']=='L':
            rt['AWA']=-rt['AWA']
        if(len(darray[5]) > 0): rt['AWS'] = float(darray[5])
        elif(len(darray[3]) > 0): rt['AWS'] = float(darray[3])* 0.514444    # speed kn-> m/s
        elif(len(darray[7]) > 0): rt['AWS'] = float(darray[7])/3.6    # speed km/h -> m/s
        if('AWA' in rt):
            self.api.addData(self.PATHAWA, self.LimitWinkel(rt['AWA']),source=source)
            self.WindData.append('AWA')
        if('AWS' in rt):
            self.api.addData(self.PATHAWS, rt['AWS'],source=source)
            self.WindData.append('AWS')
        return(True)
 
 
 
 
        
#MWV - Wind Speed and Angle
#
#        1   2 3   4 5
#        |   | |   | |
# $--MWV,x.x,a,x.x,a*hh<CR><LF>#

 #Field Number: 
 # 1) Wind Angle, 0 to 360 degrees
 # 2) Reference, R = Relative, T = True
 # 3) Wind Speed
 # 4) Wind Speed Units, K/M/N
 # 5) Status, A = Data Valid
 # 6) Checksum        
        
      if tag == 'MWV':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)

        rt['status'] = darray[5] or ''
        if(rt['status'] == 'A'): # valid:
            rt['speedunit'] = darray[4] or ''
            if(rt['speedunit']=='M'):    
                rt['speed'] = float(darray[3] or '0')
            elif(rt['speedunit']=='K'):
                rt['speed'] = float(darray[3] or '0')/3.6
            elif(rt['speedunit']=='N'):
                rt['speed'] = float(darray[3] or '0')*0,514444
            rt['relortrue'] = darray[2] or ''
            if(rt['relortrue']=='R'):
                rt['AWS'] = rt['speed']
                rt['AWA'] = self.LimitWinkel(float(darray[1] or '0'))
                if not (tag + '-R') in self.receivedTags:self.receivedTags.append(tag+'-R')
            else:
                rt['TWA'] = self.LimitWinkel(float(darray[1] or '0'))
                rt['TWS'] = rt['speed']
                if not (tag + '-T') in self.receivedTags:self.receivedTags.append(tag+'-T')
            if('AWA' in rt):
                self.api.addData(self.PATHAWA, rt['AWA'],source=source)
                self.WindData.append('AWA')
            if('AWS' in rt):
                self.api.addData(self.PATHAWS, rt['AWS'],source=source)
                self.WindData.append('AWS')
            if('TWA' in rt):
                self.api.addData(self.PATHTWA, rt['TWA'],source=source)
                self.WindData.append('TWA')
            if('TWS' in rt):
                self.api.addData(self.PATHTWS, rt['TWS'],source=source)
                self.WindData.append('TWS')
        return True
    
    
#MWD - Wind Direction & Speed
#The direction from which the wind blows across the earth’s surface, with respect to north, and the speed of
#the wind.
#$--MWD,x.x,T,x.x,M,x.x,N,x.x,M*hh<CR><LF>
# 1 Wind direction, 0 to 359 degrees True
#2  'T'
# 3 Wind direction, 0 to 359 degrees Magnetic
#4 'M'
# 5 Wind speed knots
#6 'N'
# 7 Wind speed m/s
#8 'M'     
      if tag == 'MWD':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)
        if(len(darray[7]) > 0):
             rt['TWS'] = float(darray[7] or '0')
        else:
             if(len(darray[5]) > 0): 
                 rt['TWS'] = float(darray[5] or '0')*0.51444
        if(len(darray[3]) > 0): rt['TWDmag'] = float(darray[3] or '0')
        if(len(darray[1]) > 0): rt['TWD'] = float(darray[1] or '0')
        if('TWD' in rt):
            self.api.addData(self.PATHTWD, rt['TWD'],source=source)
            self.WindData.append('TWD')
        if('TWS' in rt):
            self.api.addData(self.PATHTWS, rt['TWS'],source=source)
            self.WindData.append('TWS')
        return True


#HDG - Heading - Deviation & Variation
#
#        1   2   3 4   5 6
#        |   |   | |   | |
# $--HDG,x.x,x.x,a,x.x,a*hh<CR><LF>

#Field Number: 
 # 1) Magnetic Sensor heading in degrees
#  2) Magnetic Deviation, degrees
#  3) Magnetic Deviation direction, E = Easterly, W = Westerly
#  4) Magnetic Variation degrees
#  5) Magnetic Variation direction, E = Easterly, W = Westerly
#  6) Checksum      
      
      if tag == 'HDG':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)
        if(len(darray[1]) > 0):rt['SensorHeading'] = float(darray[1] or '0') 
        if(len(darray[2]) > 0): 
            rt['MagDeviation'] = float(darray[2] or '0')  # --> Ablenkung
            if(len(darray[3]) > 0):rt['MagDevDir'] = darray[3] or 'X'
        if(len(darray[4]) > 0): 
            rt['MagVariation'] = float(darray[4] or '0')  # --> Missweisung
            if(len(darray[5]) > 0):rt['MagVarDir'] = darray[5] or 'X'
#        self.addToNavData(rt,source=source,record=tag)

        heading_m = rt['SensorHeading']

        # Kompassablenkung korrigieren
        if('MagDevDir' in rt and rt['MagDevDir'] == 'E'):
            heading_m = heading_m + rt['MagDeviation']
        elif('MagDevDir' in rt and rt['MagDevDir'] == 'W'): 
            heading_m = heading_m - rt['MagDeviation']
        if not (tag + '-M') in self.receivedTags:self.receivedTags.append(tag + '-M')
        self.api.addData(self.PATHHDG_M, self.LimitWinkel(heading_m),source=source)
        # Wahrer Kurs unter Berücksichtigung der Missweisung
        heading_t = None
        if('MagVarDir' in rt):
            if(rt['MagVarDir'] == 'E'):
                heading_t = heading_m + rt['MagVariation']
                self.variation_val = rt['MagVariation']
            elif(rt['MagVarDir'] == 'W'): 
                heading_t = heading_m - rt['MagVariation']
                self.variation_val = -rt['MagVariation']
            self.variation_time = time.time()
            self.api.addData(self.PATHGMM, self.variation_val,source=source)
        if heading_t is not None:
          self.receivedTags.append(tag + '-T')
          self.api.addData(self.PATHHDG_T, self.LimitWinkel(heading_t),source=source)
        return True

      if tag == 'HDM' or tag == 'HDT':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)
        if(len(darray[1]) > 0):rt['Heading'] = float(darray[1] or '0')
        rt['magortrue'] = darray[2]
        if(rt['magortrue'] == 'T'):
          self.api.addData(self.PATHHDG_T, self.LimitWinkel(rt['Heading']),source=source)
          if(self.variation_val):
              self.api.addData(self.PATHHDG_M, self.LimitWinkel(rt['Heading'] - self.variation_val),source=source)
        else:
          self.api.addData(self.PATHHDG_M, self.LimitWinkel(rt['Heading']))
          if(self.variation_val):
              self.api.addData(self.PATHHDG_T, self.LimitWinkel(rt['Heading'] + self.variation_val),source=source)
        return True



#VHW - Water speed and heading

#        1   2 3   4 5   6 7   8 9
#        |   | |   | |   | |   | |
# $--VHW,x.x,T,x.x,M,x.x,N,x.x,K*hh<CR><LF>

# Field Number: 
#  1) Degress True
#  2) T = True
#  3) Degrees Magnetic
#  4) M = Magnetic
#  5) Knots (speed of vessel relative to the water)
#  6) N = Knots
#  7) Kilometers (speed of vessel relative to the water)
#  8) K = Kilometers
#  9) Checksum

      
      if tag == 'VHW':
        if not tag in self.receivedTags: 
            self.receivedTags.append(tag)
        if(len(darray[1]) > 0):  # Heading True
            rt['Heading-T'] = float(darray[1] or '0')
            self.api.addData(self.PATHHDG_T, self.LimitWinkel(rt['Heading-T']),source=source)
            if not (tag + '-T') in self.receivedTags: 
                self.receivedTags.append(tag + '-T')
        if(len(darray[3]) > 0): 
            rt['Heading-M'] = float(darray[3] or '0')  # Heading magnetic
            self.api.addData(self.PATHHDG_M, self.LimitWinkel(rt['Heading-M']),source=source)
            if not (tag + '-R') in self.receivedTags:self.receivedTags.append(tag + '-R')
            if(len(darray[1]) == 0 and self.variation_val is not None):    # keinTRUE-Heading empfangen
                self.api.addData(self.PATHHDG_T, self.LimitWinkel(rt['Heading'] + self.variation_val),source=source)
        if(len(darray[7]) > 0):  # Speed of vessel relative to the water, km/hr 
            rt['STW'] = float(darray[7] or '0')  # km/h
            rt['STW'] = rt['STW'] / 3.6  # m/s
            self.api.addData(self.PATHSTW, rt['STW'],source=source)
            if not (tag + '-S') in self.receivedTags: 
                self.receivedTags.append(tag + '-S')
        elif(len(darray[5]) > 0):  # Speed of vessel relative to the water, knots
            rt['STW'] = float(darray[7] or '0')  # kn
            rt['STW'] = rt['STW'] * 0.514444  # m/s
            self.api.addData(self.PATHSTW, rt['STW'],source=source)
            if not (tag + '-S') in self.receivedTags: 
                self.receivedTags.append(tag + '-S')
      return True
    
    except Exception:
      self.api.error(" error parsing nmea data " + str(data) + "\n")
    return False
  
  def calcTrueWind(self, gpsdata):
    # https://www.rainerstumpe.de/HTML/wind02.html
    # https://www.segeln-forum.de/board1-rund-ums-segeln/board4-seemannschaft/46849-frage-zu-windberechnung/#post1263721      
        rt = gpsdata
        if not 'track' in gpsdata or not 'AWA' in gpsdata:
            return False
        try:
            if(not 'AWD' in self.WindData): 
                gpsdata['AWD'] = (gpsdata['AWA'] + gpsdata['track']) % 360
            KaW = self.toKartesisch(gpsdata['AWD'])
            KaW['x'] *= gpsdata['AWS']  # 'm/s'
            KaW['y'] *= gpsdata['AWS']  # 'm/s'
            KaB = self.toKartesisch(gpsdata['track'])
            KaB['x'] *= gpsdata['speed']  # 'm/s'
            KaB['y'] *= gpsdata['speed']  # 'm/s'

            if(gpsdata['speed'] == 0 or gpsdata['AWS'] == 0):
                if(not 'TWD' in self.WindData):
                     gpsdata['TWD'] = gpsdata['AWD'] 
            else:
                test= (self.toPolWinkel(KaW['x'] - KaB['x'], KaW['y'] - KaB['y'])) % 360
                if(not 'TWD' in self.WindData):
                     gpsdata['TWD'] = (self.toPolWinkel(KaW['x'] - KaB['x'], KaW['y'] - KaB['y'])) % 360

            if(not 'TWS' in self.WindData):
                 gpsdata['TWS'] = math.sqrt((KaW['x'] - KaB['x']) * (KaW['x'] - KaB['x']) + (KaW['y'] - KaB['y']) * (KaW['y'] - KaB['y']))
            if(not 'TWA' in self.WindData):
                 gpsdata['TWA'] = self.LimitWinkel(gpsdata['TWD'] - gpsdata['track'])

            return True
        except Exception:
            self.api.error(" error calculating TrueWind-Data " + str(gpsdata) + "\n")
        return False
    
  def LimitWinkel(self, alpha):  # [grad]   
    alpha %= 360
    if (alpha > 180): 
        alpha -= 360;
    return(alpha)  

  def toPolWinkel(self, x, y):  # [grad]
        return(180 * math.atan2(y, x) / math.pi)

  def toKartesisch(self, alpha):  # // [grad]
        K = {}
        K['x'] = math.cos((alpha * math.pi) / 180)
        K['y'] = math.sin((alpha * math.pi) / 180)
        return(K)    

