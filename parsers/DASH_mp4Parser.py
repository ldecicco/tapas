#!/usr/bin/env python
# -*- Mode: Python -*-
# -*- encoding: utf-8 -*-
# Copyright (c) Vito Caldaralo <vito.caldaralo@gmail.com>

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE" in the source distribution for more information.
import os, sys
import StringIO
from pprint import pformat

from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientFactory, Protocol
import urllib2
from pprint import pformat
import numpy
import struct
import time
import math
#
from utils_py.util import debug, format_bytes
from utils_py.connection import parse_url, ClientFactory
from utils_py.xml2json import *
from BaseParser import BaseParser


DEBUG = 2
CONTAINER_ATOMS = ('moov', 'trak', 'mdia', 'minf', 'dinf', 'stbl', 'moof', 'traf', 'udta', 'mvex')
CONTAINER_FULL_ATOMS = ('stsd')

#http://dash-mse-test.appspot.com/media.html
#http://yt-dash-mse-test.commondatastorage.googleapis.com/media/motion-20120802-manifest.mpd
#http://www-itec.uni-klu.ac.at/ftp/datasets/mmsys12/ElephantsDream/MPDs/ElephantsDreamNonSeg_6s_isoffmain_DIS_23009_1_v_2_1c2_2011_08_30.mpd

class DASH_mp4Parser(BaseParser):
    
    def __init__(self,url,playlist_type='DASH',video_container='MP4'):
        super(DASH_mp4Parser, self).__init__(url,playlist_type,video_container)
        self.json_mpd = None
        self.profiles = ''
        self.deferredList = []
        self.connection_list = []
        self.fd = []
        #self.videorates_real = []

    def __repr__(self):
        return '<ParserDASH-%d>' %id(self)
    
    def loadPlaylist(self):
        self.levels = []                   
        self.playlists = []
        self.caps_demuxer = []
        print self.url
        try:
            response = urllib2.urlopen(self.url)
            xmlstring = response.read()
        except KeyError:
            print "Error get_mpd"
            self.loadPlaylist()
            return
        self.json_mpd=json.loads(xml2json(xmlstring))
        def get_duration_mpd(duration):
            #PT0H3M1.63S
            duration = duration[2:]
            _h = duration.split("H")
            h = float(_h[0])*3600
            _m = _h[1].split("M")
            m = float(_m[0])*60
            _s = _m[1].split("S")
            s = float(_s[0])
            return str(h+m+s)

        duration = get_duration_mpd(self.json_mpd["MPD"]["@mediaPresentationDuration"])
        self.profiles = self.json_mpd["MPD"]["@profiles"]

        json_adaptation_set = self.json_mpd["MPD"]["Period"]["AdaptationSet"]
        pl = []
        rates = []
        types = []
        if isinstance(json_adaptation_set, dict):
            len_adaptation_set = 1
        elif isinstance(json_adaptation_set, list):
            len_adaptation_set = len(json_adaptation_set)
        for i in range(0,len_adaptation_set):
            if len_adaptation_set == 1:
                json_representation = json_adaptation_set["Representation"]
            else:
                json_representation = json_adaptation_set[i]["Representation"]
            for j in range(0,len(json_representation)):
                isOfType = json_representation[j]["@mimeType"]
                if isOfType == "video/mp4":
                    itag = json_representation[j]["@id"]
                    rate = int(json_representation[j]["@bandwidth"])/8.  #in B/s
                    if "isoff-main" in self.profiles:
                        BaseURL = self.json_mpd["MPD"]["BaseURL"]
                        url_level = BaseURL+json_representation[j]["SegmentBase"]["Initialization"]["@sourceURL"]
                    elif "isoff-on-demand" in self.profiles:    
                        url_level = "/".join(self.url.split("/")[:-1])+"/"+json_representation[j]["BaseURL"]
                    init = index = sidx_atom = "0-0"
                    if "@range" in json_representation[j]["SegmentBase"]["Initialization"].keys():
                        init = json_representation[j]["SegmentBase"]["Initialization"]["@range"]
                        sidx_atom = json_representation[j]["SegmentBase"]["Initialization"]["@range"]
                    if "isoff-on-demand" in self.profiles:
                        index = json_representation[j]["SegmentBase"]["@indexRange"]
                        sidx_atom = "0-"+index.split("-")[1]
                    resolution = json_representation[j]["@width"]+"x"+json_representation[j]["@height"]
                    m_type = json_representation[j]["@mimeType"]
                    #url_init = url_level+"&range="+init
                    #response_init = urllib2.urlopen(url_init)
                    pl.append(dict(level=-1,rate=int(rate),res=str(resolution),
                        url_level=str(url_level),
                        itag=str(itag),type=str(m_type),
                        init=str(init),index=str(index),sidx=str(sidx_atom),
                        header_data=None,
                        duration=duration))                
                    rates.append(dict(rate=int(rate),type=m_type,level=0))
                    #Check for new MIME type        
                    extType = 0;
                    if len(types) == 0:
                        types.append(dict(type=m_type,level=0))
                    else:
                        for k in range(0, len(types)):
                            if m_type == types[k]["type"]:
                                extType = 1
                                break
                            if extType == 0:
                                types.append(dict(type=m_type,level=0))
        #Sort levels based only on rate
        for i in range(0,len(rates)-1):
            for j in range(i+1,len(rates)):
                if (rates[i]["rate"]) > int(rates[j]["rate"]) and (rates[i]["type"] == rates[j]["type"]):
                    swap = rates[j]
                    rates[j] = rates[i]
                    rates[i] = swap
                    del swap
                    swap = pl[j]
                    pl[j] = pl[i]
                    pl[i] = swap
        for i in range(0, len(rates)):
            indexType = -1
            for j in range(0,len(types)):
                if rates[i]["type"] == types[j]["type"]:
                    indexType = j
                    break
            if indexType != -1:
                rates[i]["level"] = types[indexType]["level"]
                types[indexType]["level"] += 1
        for i in range(len(pl)):
            for j in range(0, len(rates)):
                if pl[i]["rate"] == rates[j]["rate"]:
                    pl[i]["level"] = rates[j]["level"];
        
        for i in range(len(rates)):
            self.levels.append(dict(rate=rates[i]["rate"],resolution=pl[len(rates)-i-1]["res"]))
            #self.videorates_real.append([])

        for i in range(0, len(pl)):
            self.playlists.append(dict(url=pl[i]["url_level"],
                is_live=False, 
                segments=[], 
                start_index=-1, end_index=-1,
                duration=float(pl[i]["duration"]),
                header_data=None, 
                init=pl[i]["init"], sidx=pl[i]["sidx"]))
            self.caps_demuxer.append(dict(data_format="",codec_data="",width="",height=""))
        for l in range(len(self.playlists)):
            self.connection_list.append(None)
            self.fd.append(None)
            self.deferredList.append(defer.Deferred())
            self.updateLevelSegmentsList(l)
        dl = defer.DeferredList(self.deferredList)
        def _on_done(res):
            if "isoff-main" in self.profiles:
                for level in range(len(self.playlists)):
                    self.parseSegmentsList(level)
            self.deferred.callback(True)    
        dl.addCallback(_on_done)
        
    def updateLevelSegmentsList(self, level):
        url = self.playlists[level]["url"]
        if self.playlists[level]["sidx"] == '0-0':
            byterange = ''
        else:
            byterange = self.playlists[level]["sidx"]
        self.startDownload(self.playlists[level]["url"], byterange, level)

    def startDownload(self, url, byterange, level):
        # start download
        debug(DEBUG+1, '%s startDownload %s %s', self, url, byterange)
        # start a new connection
        if not self.connection_list[level]:
            self.init_connection(url, byterange, level)
            return
        if not self.connection_list[level].client:
            return
        _, _, path = parse_url(url)
        self.connection_list[level].makeRequest(path, byterange)

    def init_connection(self, url, byterange, level):
        if self.connection_list[level]:
            self.connection_list[level].stop()
        debug(DEBUG+1, '%s init_connection: %s', self, url)
        self.connection_list[level] = ClientFactory(url)
        self.connection_list[level].connect('connection-made', self.on_connection_made, url, byterange, level)
        self.connection_list[level].connect('connection-lost', self.on_connection_lost)
        self.connection_list[level].connect('data-received', self.on_data_received, level)

    def on_connection_made(self, connection, host, url, byterange, level):
        debug(DEBUG+1, '%s on_connection_made: %s', self, host)
        reactor.callLater(0.1, self.startDownload, url, byterange, level)

    def on_connection_lost(self, connection):
        debug(DEBUG+1, '%s on_connection_lost', self)
        self.connection = None

    def on_data_received(self, connection, data, level):
        debug(DEBUG+1, '%s on_data_received: %s', self, format_bytes(len(data)))
        self.fd[level] = StringIO.StringIO(data)
        #print "level", level
        self.playlists[level]["header_data"]=data
        self.parse_atom(0,len(data)-1, level)
        self.deferredList[level].callback(1)
        self.connection_list[level].stop()

    def parse_atom(self, start, end, level):
        s = []
        self.fd[level].seek(start)
        data = self.fd[level].read(8)
        while data:
            atom_size, atom_type = struct.unpack('!I4s', data)
            if not atom_size:
                break
            children = []
            contents = {}
            if atom_type == 'hdlr':
                self.fd[level].seek(start+16) #skip version, flags and 0 pad (1 uint of 0)
                self.handler_type,res= struct.unpack('!4s12s',self.fd[level].read(16))
                name = struct.unpack('!{0}s'.format(atom_size-32),self.fd[level].read(atom_size-32))
                contents = dict(handler_type = self.handler_type, name = name)
            elif atom_type == 'stsd':
                self.fd[level].seek(start+8) #skip size and name
                version,flags = struct.unpack('!B3s', self.fd[level].read(4))
                entry_count, = struct.unpack('!I',self.fd[level].read(4))
                for i in xrange(0,entry_count):
                    # parse sampleEntry box (all the box extend this one)
                    size,box_type = struct.unpack('!I4s',self.fd[level].read(8))
                    if size==1:
                        largesize = struct.unpack('!Q',self.fd[level].read(8))
                    if box_type == 'uuid':
                        user_type = struct.unpack('!16s',self.fd[level].read(16))
                    reserved, data_ref_idx = struct.unpack('!6sH',self.fd[level].read(8))
                    cnt = []
                    if self.handler_type == 'vide':
                        # parse video
                        version,revision,vendor,temporal_quality,spatial_quality,width,height,h_resolution,v_resolution,datasize,framecount,compressor,depth,color_table_id = struct.unpack('!2H4s2I2H3IH32sHh',self.fd[level].read(70))
                        v_resolution = v_resolution/2**16
                        h_resolution = h_resolution/2**16
                        internal = {}
                        if box_type == 'avc1':
                            # parse specific avc1 codec data
                            internal = self.parseAvcC(level)
                            #print pformat(internal)
                        data = dict( size = size, box_type = box_type, reserved = reserved, data_ref_idx = data_ref_idx, # common data
                            version = version,revision = revision, vendor = vendor, temporal_quality = temporal_quality, spatial_quality = spatial_quality,
                            width = width, height = height, h_resolution = h_resolution, v_resolution = v_resolution, datasize = datasize, framecount = framecount,
                            compressor = compressor, depth = depth, color_table_id = color_table_id, internal = internal)
                        self.create_gst_codec_data(data,level)
                        cnt.append(data)
                    contents = dict(entry_count = entry_count,version = version, flags = flags, entries = cnt)
            elif atom_type == 'sidx':
                index = []
                brange = []
                self.fd[level].seek(start+4+4)
                version, flags = struct.unpack('!B3s', self.fd[level].read(4))
                reference_ID, = struct.unpack('!I', self.fd[level].read(4))
                timescale, = struct.unpack('!I', self.fd[level].read(4))
                if version == 0:
                    earliest_presentation_time, = struct.unpack('!I', self.fd[level].read(4))
                    first_offset, = struct.unpack('!I', self.fd[level].read(4))
                else:
                    earliest_presentation_time, = struct.unpack('!Q', self.fd[level].read(8))
                    first_offset, = struct.unpack('!Q', self.fd[level].read(8))
                reserved, = struct.unpack('!H', self.fd[level].read(2))
                reference_count, = struct.unpack('!H', self.fd[level].read(2))
                #print locals()
                index.append(start + atom_size)
                brange.append([0,start + atom_size-1])
                playlist = []
                rate_value = []
                for i in xrange(0,reference_count):
                    _, = struct.unpack('!I', self.fd[level].read(4))
                    reference_type = _ >> 31
                    reference_size = _ & 0x7fffffff
                    subsegment_duration, = struct.unpack('!I', self.fd[level].read(4))
                    segment_duration = float(subsegment_duration/timescale)
                    _, = struct.unpack('!I', self.fd[level].read(4))
                    starts_with_SAP = _ >> 31
                    SAP_type = (_ >> 28) & 0x7
                    SAP_delta_time = _ & 0x0fffffff
                    #print locals()
                    index.append(index[-1] + reference_size)
                    brange.append([brange[-1][1]+1, brange[-1][1]+reference_size])
                    rate_value.append(reference_size)
                    if len(playlist) != 0:
                        byterange = str(brange[-1][0])+"-"+str(brange[-1][1])
                    else:
                        byterange = "0-"+str(brange[-1][1])
                    #byterange = str(brange[-1][0])+"-"+str(brange[-1][1])
                    _c = dict(url=self.playlists[level]["url"],byterange=str(byterange),dur=segment_duration)
                    playlist.append(_c)
                self.playlists[level]["segments"] = playlist
                self.playlists[level]["end_index"] = len(playlist)
                self.fragment_duration = math.ceil(self.playlists[level]["duration"]/len(playlist))
                #vr_real = [float(x/self.fragment_duration) for x in rate_value]
                #self.videorates_real[level] = vr_real
                contents = dict(index=index)
            #
            # parse children
            if atom_type in CONTAINER_ATOMS:
                children = self.parse_atom(start+8, start+atom_size, level)
            elif atom_type in CONTAINER_FULL_ATOMS:
                children = self.parse_atom(start+16, start+atom_size, level)
            #
            s.append(dict(start=start, size=atom_size, a_name=atom_type,
                contents=contents, children=children))
            #
            start += atom_size
            if start >= end:
                break
            self.fd[level].seek(start)
            data = self.fd[level].read(8)
        #print pformat(s)

    def parseAvcC(self, level):
        size,box_type = struct.unpack('!I4s',self.fd[level].read(8))
        # AVCDecoderConfigurationRecord
        configurationVersion,AVCProfileIndication,profile_compatibility,AVCLevelIndication,lengthSizeMinusOne,numOfSequenceParameterSets = struct.unpack('!6B',self.fd[level].read(6))
        lengthSizeMinusOne = lengthSizeMinusOne & 0x3 #mask to obtain only 2 bit
        numOfSequenceParameterSets = numOfSequenceParameterSets & 0x1f # mask to obtain only 5 bit
        sequenceParameters = []
        for i in xrange(0,numOfSequenceParameterSets):
            sequenceParameterSetLength, = struct.unpack('!H',self.fd[level].read(2))
            st = '!{0}s'.format(sequenceParameterSetLength)
            sequenceParameterSetNALUnit, = struct.unpack(st,self.fd[level].read(sequenceParameterSetLength))
            sequenceParameters.append(dict(sequenceParameterSetLength = sequenceParameterSetLength, sequenceParameterSetNALUnit = sequenceParameterSetNALUnit ))
        numOfPictureParameterSets, = struct.unpack('!B',self.fd[level].read(1))
        pictureParameters = []
        for i in xrange(0,numOfPictureParameterSets):
            pictureParameterSetLength, = struct.unpack('!H',self.fd[level].read(2))
            st = '!{0}s'.format(pictureParameterSetLength)
            pictureParameterSetNALUnit, = struct.unpack(st,self.fd[level].read(pictureParameterSetLength))
            pictureParameters.append(dict(pictureParameterSetLength = pictureParameterSetLength, pictureParameterSetNALUnit = pictureParameterSetNALUnit))
        sizeN,box_typeN = struct.unpack('!I4s',self.fd[level].read(8))
        MPEG4BitRateBox = {}
        if box_typeN == 'btrt':
            bufferSizeDB, maxBitrate, avgBitrate = struct.unpack('!3I',self.fd[level].read(12))
            MPEG4BitRateBox = dict(bufferSizeDB = bufferSizeDB, maxBitrate = maxBitrate, avgBitrate = avgBitrate)
        elif box_typeN == 'm4ds':
            pass #not well known implementation

        return dict(size = size, box_type = box_type, 
            configurationVersion = configurationVersion,
            AVCProfileIndication = AVCProfileIndication, profile_compatibility = profile_compatibility,
            AVCLevelIndication = AVCLevelIndication, 
            lengthSizeMinusOne = lengthSizeMinusOne, 
            numOfSequenceParameterSets = numOfSequenceParameterSets, sequenceParameters = sequenceParameters,
            numOfPictureParameterSets = numOfPictureParameterSets, pictureParameters = pictureParameters, 
            MPEG4BitRateBox = MPEG4BitRateBox)

    def create_gst_codec_data(self, d, level):
        caps_dict = dict(width=d["width"], height=d["height"])
        internal = d["internal"]
        def AVCDecoderConfigurationRecord():
            def to_hex(value, num_byte):
                if isinstance(value, int):
                    hexa = hex(value)[2:].zfill(num_byte*2)
                elif isinstance(value, str):
                    hexa = value.encode('hex').zfill(num_byte*2)
                return hexa
            c_d = to_hex(internal["configurationVersion"],1) #delete 0x, 1byte
            c_d += to_hex(internal["AVCProfileIndication"],1) #delete 0x, 1byte
            c_d += to_hex(internal["profile_compatibility"],1) #delete 0x, 1byte
            c_d += to_hex(internal["AVCLevelIndication"],1) #delete 0x, 1byte
            reserved = '111111'+str(bin(internal["lengthSizeMinusOne"]))[2:].zfill(2)  #delete 0b, 1byte
            c_d += to_hex(int(reserved, 2),1) #delete 0x
            reserved = '111'+str(bin(internal["numOfSequenceParameterSets"]))[2:].zfill(5) #delete 0b
            c_d += to_hex(int(reserved, 2),1) #delete 0x
            for i in xrange(0,internal["numOfSequenceParameterSets"]):
                spsl = internal["sequenceParameters"][i]["sequenceParameterSetLength"]
                c_d += to_hex(internal["sequenceParameters"][i]["sequenceParameterSetLength"],2)    #delete 0x, 2byte
                c_d += to_hex(internal["sequenceParameters"][i]["sequenceParameterSetNALUnit"],spsl)
            c_d += to_hex(internal["numOfPictureParameterSets"],1)
            for i in xrange(0,internal["numOfPictureParameterSets"]):
                ppsl = internal["pictureParameters"][i]["pictureParameterSetLength"]
                c_d += to_hex(internal["pictureParameters"][i]["pictureParameterSetLength"],2)    #delete 0x, 2byte
                c_d += to_hex(internal["pictureParameters"][i]["pictureParameterSetNALUnit"],ppsl)
            return c_d
        codec_data = AVCDecoderConfigurationRecord()
        caps_dict.update(codec_data=codec_data)
        self.caps_demuxer[level] = caps_dict

    def parseSegmentsList(self,level):
        json_adaptation_set = self.json_mpd["MPD"]["Period"]["AdaptationSet"]
        if isinstance(json_adaptation_set, dict):
            len_adaptation_set = 0
        elif isinstance(json_adaptation_set, list):
            len_adaptation_set = len(json_adaptation_set)
        if len_adaptation_set == 0:
            json_representation = json_adaptation_set["Representation"]
        else:
            json_representation = json_adaptation_set[level]["Representation"]    
        segment_list = json_representation[level]["SegmentList"]
        segment_duration = json_representation[level]["SegmentList"]["@duration"]
        segment_urls = segment_list["SegmentURL"]
        playlist = []
        rate_value = []
        for i in range(0, len(segment_urls)):
            BaseURL = self.json_mpd["MPD"]["BaseURL"]
            url_segment = BaseURL+segment_urls[i]["@media"]
            byterange = ''
            if "@mediaRange" in segment_urls[i].keys():
                if len(playlist) != 0:
                    byterange = segment_urls[i]["@mediaRange"]
                else:
                    byterange = "0-"+segment_urls[i]["@mediaRange"].split("-")[1]
                #byterange = segment_urls[i]["@mediaRange"]
                reference_size = byterange.split("-")
                rate_value.append(int(reference_size[1])-int(reference_size[0]))
            _c = dict(url=str(url_segment),byterange=str(byterange),dur=segment_duration)
            playlist.append(_c)
        self.playlists[level]["segments"] = playlist
        self.playlists[level]["end_index"] = len(playlist)
        self.fragment_duration = math.ceil(self.playlists[level]["duration"]/len(playlist))
        #vr_real = [float(x/self.fragment_duration) for x in rate_value]
        #self.videorates_real[level] = vr_real




