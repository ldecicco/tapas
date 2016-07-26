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
import os, sys, inspect
from twisted.internet import defer, reactor
import time, datetime
from pprint import pformat
from utils_py.util import debug, format_bytes, Logger, getPage, send_json, makeJsonUrl, RateCalc, ProcessStats
from utils_py.connection import parse_url, ClientFactory

DEBUG = 2
USER_AGENT = 'Mozilla/5.0 (iPad; PythonHlsPlayer 0.1) AppleWebKit/531.21.10 (KHTML, like Gecko) Version/4.0.4 Mobile/7B334b Safari/531.21.10'

class TapasPlayer(object):

    def __init__(self, controller, parser, media_engine, 
        log_sub_dir='', log_period=0.1,
        max_buffer_time=60,
        inactive_cycle=1, initial_level=1,
        use_persistent_connection=True,
        check_warning_buffering=True,
        stress_test=False):

        # player components
        self.controller = controller
        self.parser = parser
        self.media_engine = media_engine
        # log
        self.logger = None
        self.log_file = None
        self.log_dir='logs'
        self.log_sub_dir=log_sub_dir
        self.log_period = log_period
        self.log_prefix='' 
        self.log_comment='' 
        #
        self.max_buffer_time = max_buffer_time
        self.inactive_cycle = inactive_cycle #active control action after inactive_cycle+1 segments
        #
        self.use_persistent_connection = use_persistent_connection
        self.connection = None
        #
        self.cur_level = initial_level
        self.cur_index = 0
        self.enable_stress_test = stress_test #flag to enable stress test, switch level every segment cyclically 
        #
        self.check_warning_buffering = check_warning_buffering #flag to enable check for warning buffering
        self.rate_calc = RateCalc(period=3.0, alpha=0.0)
        self.remaining_data = 0
        #
        self.bwe = 0
        self.downloaded_bytes = 0
        self.downloaded_segments = 0
        self.last_fragment_size = 0
        self.start_segment_request = -1.0
        self.stop_segment_request = -1.0
        self.last_downloaded_time = -1.0
        self.t_paused = time.time()
        self.paused_time = 0.0
        self.queuedBytes = 0
        self.queuedTime = 0.0
        #
        self.proc_stats = ProcessStats()

        #Initialize the parameters passed at the controller after the download of every segment
        self.feedback = dict(queued_bytes=0,
           queued_time=0.0,
           max_buffer_time=self.max_buffer_time,
           bwe=0.0,
           level=self.cur_level,
           max_level=-1,
           cur_rate=0.0,
           max_rate=0.0,
           min_rate=0.0,
           player_status=0,
           paused_time=0.0,
           last_fragment_size=0,
           last_download_time=0.0,
           start_segment_request=0.0,
           stop_segment_request=time.time(),
           downloaded_bytes=0,
           fragment_duration=0.0,
           rates=[]
        )
        self.controller.setPlayerFeedback(self.feedback)
        
    def __repr__(self):
        return '<TapasPlayer-%d>' %id(self)

    def play(self):
        '''
        Starts Parser, creates Logger, initializes MediaEngine, and fetches the first segment when the parser has finished
        '''
        self.parser.loadPlaylist()
        def _on_done(res): 
            playlists = self.parser.getPlaylists()
            levels = self.parser.getLevels()
            fragment_duration = self.parser.getFragmentDuration()
            caps = self.parser._getCapsDemuxer()
            self.controller.setIdleDuration(fragment_duration)  #Default pause interval when isBuffering return False
            if self.getCurrentLevel() > self.getMaxLevel() or self.getCurrentLevel() == -1:
                self.setCurrentLevel(self.getMaxLevel())
            #opts for Logger
            opts = [
                ('enqueued_b', int, ''),                        #2
                ('enqueued_t', float, 'visible=1,subplot=2'),   #3
                ('bwe', float, 'visible=1,subplot=1'),          #4
                ('cur', int, 'visible=1,subplot=1'),            #5
                ('level', int, 'visible=1,subplot=3'),          #6
                ('max_level', int, ''),                         #7
                ('player_status', int, 'visible=1,subplot=3'),  #8
                ('paused_time', float, ''),                     #9
                ('downloaded_bytes', int, ''),                  #10
                ('cpu', float, 'visible=1,subplot=4'),          #11
                ('mem', float, 'visible=1,subplot=5'),          #12
                ('rss', float, ''),                             #13
                ('vms', float, ''),                             #14
                ('ts_start_req', float, ''),                    #15
                ('ts_stop_req', float, ''),                     #16
            ]
            for i in range(0,len(levels)):
                opts.append(('q%d' %i, int, 'visible=0'))
            if self.log_sub_dir:     
                self.log_dir = self.log_dir + '/'+ self.log_sub_dir
                #Create Logger
                self.logger = Logger(opts, log_period=self.log_period, 
                    log_prefix=self.log_prefix, comment=self.log_comment, 
                    log_dir=self.log_dir)
                debug(DEBUG+1, 'levels: %s', levels)
                debug(DEBUG+1, 'playlists: %s', playlists)
            if self.enable_stress_test:
                self.inactive_cycle = 0
            if self.check_warning_buffering:
                self.rate_calc.start()
                self.rate_calc.connect('update', self.checkBuffering)
            #Init media_engine
            self.media_engine.setVideoContainer(self.parser.getVideoContainer())
            self.media_engine.connect('status-changed', self._onStatusChanged)
            self.media_engine.start()
            #start logger
            reactor.callLater(self.log_period, self.log)
            #
            self.fetchNextSegment()
        self.parser.deferred.addCallback(_on_done)

    def getMaxBufferTime(self):
        '''
        Gets max buffer in seconds under which the playback is considered in Buffering by default
        '''
        return self.max_buffer_time

    def getCurrentLevel(self):
        '''
        Gets index of current level starting from 0 for the lowest video quality level
        '''
        return self.cur_level

    def setCurrentLevel(self,level):
        '''
        Sets index of current level starting from 0 for the lowest video quality level

        :param level: the level index
        '''
        self.cur_level = level

    def getMaxLevel(self):
        '''
        Gets index of maximum level starting from 0 for the lowest video quality level
        '''
        return len(self.parser.getLevels())-1

    def getCurrentSegmentIndex(self):
        '''
        Gets index of the current segment of the sub-playlist
        '''
        return self.cur_index

    def setCurrentSegmentIndex(self,index):
        '''
        Sets index of the current segment of the sub-playlist

        :param index: segment index
        '''
        self.cur_index = index

    def getCurrentRate(self):
        '''
        Gets current video quality level rate in B/s
        '''
        levels = self.parser.getLevels()
        cur_rate = float(levels[self.getCurrentLevel()]['rate'])
        return cur_rate

    def getMaxRate(self):
        '''
        Gets maximum video quality level rate in B/s
        '''
        levels = self.parser.getLevels()
        rates = [float(i['rate']) for i in levels]
        return max(rates)

    def getMinRate(self):
        '''
        Gets minimum video quality level rate in B/s
        '''
        levels = self.parser.getLevels()
        rates = [float(i['rate']) for i in levels]
        return min(rates)

    def getLevelRates(self):
        '''
        Gets a list of video quality level rates in B/s
        '''
        levels = self.parser.getLevels()
        _r= [float(i['rate']) for i in levels]
        rates = []
        for i in range(0,len(_r)):
            rates.append(_r[i])
        return rates

    def getLevelResolutions(self):
        '''
        Gets a list of available video resolutions
        '''
        levels = self.parser.getLevels()
        resolutions = [i['resolution'] for i in levels]
        return resolutions

    def getLastDownloadedTime(self):
        '''
        Gets time spent to download the last segment
        '''
        return self.last_downloaded_time

    def getStartSegmentRequest(self):
        '''
        Gets timestamp when starts the download of the last segment
        '''
        return self.start_segment_request  

    def getStopSegmentRequest(self):
        '''
        Gets timestamp when stops the download of the last segment
        '''
        return self.stop_segment_request  

    def getLastFragmentBytes(self):
        '''
        Gets the last fragment size in B
        '''
        return self.last_fragment_size

    def getDownloadedBytes(self):
        '''
        Gets total downloaded bytes in B
        '''
        return self.downloaded_bytes

    def getDownloadedSegments(self):
        '''
        Gets total number of downloaded segments
        '''
        return self.downloaded_segments

    def getBandwidth(self):
        '''
        Gets last estimated available bandwidth in B/s
        '''
        return self.bwe

    def getPausedTime(self):
        '''
        Gets time spent on pause
        '''
        return self.paused_time

    def getInactiveCycles(self):
        '''
        Gets the number of inactive cycles before activate the control action
        '''
        return self.inactive_cycle
    
    def getLogFileName(self):
        '''
        Gets log file name
        '''
        return self.log_file  

    def fetchNextSegment(self): 
        '''
        Schedules the download of the next segment at current level
        '''
        playlist = self.parser.playlists[self.getCurrentLevel()]
        debug(DEBUG+1, '%s fetchNextSegment level: %d cur_index: %d', self, self.getCurrentLevel(), self.getCurrentSegmentIndex())
        #
        if self.getCurrentSegmentIndex() < playlist['start_index']:
            self.setCurrentSegmentIndex(playlist['start_index'])
        if self.getCurrentSegmentIndex() > playlist['end_index']:
            # else live video (ONLY HLS!!)
            if playlist['is_live'] and self.parser.getPlaylistType() == 'HLS':
                debug(DEBUG, '%s fetchNextSegment cur_index %d', self, self.getCurrentSegmentIndex())
                self.parser.updateLevelSegmentsList(self.getCurrentLevel()).addCallback(self._updatePlaylistDone)
            # if video is vod
            else:
                debug(DEBUG, '%s fetchNextSegment last index', self)
            return
        cur_index=self.getCurrentSegmentIndex()
        levels = self.parser.getLevels()
        url_segment = playlist['segments'][cur_index]['url']
        byterange = playlist['segments'][cur_index]['byterange']
        if byterange != '':
            debug(DEBUG, '%s fetchNextSegment level: %d (%s/s) %d/%d : %s (byterange=%s)', self,
                self.getCurrentLevel(), 
                format_bytes(float(levels[self.getCurrentLevel()]['rate'])),
                self.getCurrentSegmentIndex(), 
                playlist['end_index'], url_segment, byterange)
        else:
            debug(DEBUG, '%s fetchNextSegment level: %d (%s/s) %d/%d : %s', self,
                self.getCurrentLevel(), 
                format_bytes(float(levels[self.getCurrentLevel()]['rate'])),
                self.getCurrentSegmentIndex(), 
                playlist['end_index'], url_segment)
        if self.controller.isBuffering():
            idle_duration = 0.0 #fetch segment after the last segment download is completed
        else:
            idle_duration = self.controller.getIdleDuration()
        # load the next segment
        reactor.callLater(idle_duration, self.startDownload, url_segment, byterange)

    def startDownload(self, url, byterange=''):
        '''
        Starts the segment download and set the timestamp of start segment download

        :param url: segment url
        :param byterange: segment byterange (logical segmentation of video level)
        '''
        debug(DEBUG+1, '%s startDownload %s (byterange %s)', self, url, byterange)
        # start download
        if self.use_persistent_connection:
            # start a new connection
            if not self.connection:
                self._initConnection(url)
                return
            if not self.connection.client:
                return
            _, _, path = parse_url(url)
            self.connection.makeRequest(path, byterange)
        else:
            if byterange == '':
                d = getPage(url, agent=USER_AGENT)
            else:
                d = getPage(url, agent=USER_AGENT, headers=dict(range='bytes='+byterange))
            d.deferred.addCallback(self.playNextGotRequest, d)
            d.deferred.addErrback(self.playNextGotError, d)
        self.start_segment_request = time.time()
        
    # callback if do not use persistent connection
    def playNextGotRequest(self, data, factory):
        '''
        Updates feedbacks, calculates the control action and sets level of the next segment.

        :param data: downloaded data
        :param factory: the twisted factory (used without persistent connection)
        '''
        self.stop_segment_request = time.time()
        download_time = (self.stop_segment_request - self.start_segment_request)
        self.last_downloaded_time = download_time
        self.bwe = len(data)/download_time
        self.last_fragment_size = len(data)
        self.downloaded_bytes += len(data)
        self.downloaded_segments += 1
        debug(DEBUG, '%s __got_request: bwe: %s/s (fragment size: %s)', self, 
            format_bytes(self.bwe), format_bytes(len(data)))
        self.queuedTime = self.media_engine.getQueuedTime() + self.parser.getFragmentDuration()
        self.queuedBytes = self.media_engine.getQueuedBytes() + len(data)
        self.media_engine.pushData(data, self.parser.getFragmentDuration(), self.getCurrentLevel(), self.parser._getCapsDemuxer())
        del data
        self.cur_index += 1
        #Do something before calculating new control action
        self._onNewSegment()
        #Passing player parameters at the controller to calculate the control action
        self.updateFeedback(flag_check_buffering=False)
        #calc control action
        self.controller.setControlAction(self.controller.calcControlAction())
        # set new level
        if self.getDownloadedSegments() > self.getInactiveCycles():
            if self.enable_stress_test:
                self.stressTest()
            else:
                self.setLevel(self.controller.getControlAction())
        self.fetchNextSegment()

    # error handling if do not use persistent connection
    def playNextGotError(self, error, factory):
        '''
        Handles error when download a segment without persistent connection

        :param error: the occurred error
        :param factory: the twisted factory (used without persistent connection)
        '''
        debug(0, '%s playNextGotError url: %s error: %s', self, factory.url, error)
        # update playlist
        if self.parser.getPlaylistType()=='HLS':
            self.parser.updateLevelSegmentsList(self.cur_level).addCallback(self._updatePlaylistDone)

    def setLevel(self, rate):
        '''
        Sets the level corresponding to the rate specified in B/s

        :param rate: rate in B/s that determines the level. The level is the one whose rate is the highest below ``rate``.
        '''
        new_level = self.controller.quantizeRate(rate)
        if new_level != self.getCurrentLevel():
            debug(DEBUG, "%s setLevel: level: %d", self, new_level)
            self.setCurrentLevel(new_level)
            #self.onLevelChanged()
        return new_level

    def stressTest(self):
        '''
        Switches the video quality level cyclically every segment        
        '''
        self.check_warning_buffering = False
        if self.getCurrentLevel() == self.getMaxLevel():
           new_level = 0
        else:
            new_level = self.getCurrentLevel() + 1
        self.setCurrentLevel(new_level)
        #self.onLevelChanged()
        return new_level

    def checkBuffering(self, _arg):
        '''
        Checks if the playback is going to buffering.
        Estimates the time required to complete the download of the current segment and verifies that it is less than the playout buffer lenght.

        In the case of "warning buffering", it deletes the current segment download, calculates the control action and sets the new level.
        This feature is available only with persistent connection.
        '''
        #FIXME Can't use it without persistent connection
        if self.rate_calc.rate and self.cur_index > self.inactive_cycle:
            remaining_secs = float(self.remaining_data/self.rate_calc.rate)
            debug(DEBUG+1,"%s checkBuffering: rate %s/s, remaining_data %s, remaining_secs %.3f, queued_time %.2f ", self, 
                format_bytes(self.rate_calc.rate), format_bytes(self.remaining_data), remaining_secs, self.media_engine.getQueuedTime()) 
            #Can cancel download only if the current level is greater than 0
            if self.media_engine.getQueuedTime() < remaining_secs and self.getCurrentLevel() > 0: 
                self.connection.stop()
                self.stop_segment_request = time.time() #update stop reqest when warning buffering occurs
                self.bwe = self.rate_calc.rate
                #Passing player parameters at the controller to calculate the control action
                self.updateFeedback(flag_check_buffering=True)
                #calc control action
                self.controller.setControlAction(self.controller.calcControlAction())
                # set new level
                if self.cur_index > self.inactive_cycle:
                    self.setLevel(self.controller.getControlAction())
                    debug(0,"%s WARNING BUFFERING!!! Delete and reload segment at level: %d", self, self.getCurrentLevel())
        else:
            return
       
    def updateFeedback(self, flag_check_buffering):
        '''
        Updates dictionary of feedbacks before passing it to the controller.

        :param flag_check_buffering: true if this method is called from ``checkBuffering``. False otherwise.
        '''
        self.feedback = dict(queued_bytes=self.media_engine.getQueuedBytes(),
           queued_time=self.media_engine.getQueuedTime(),
           max_buffer_time=self.getMaxBufferTime(),
           bwe=self.getBandwidth(),
           level=self.getCurrentLevel(),
           max_level=self.getMaxLevel(),
           cur_rate=self.getCurrentRate(),
           max_rate=self.getMaxRate(),
           min_rate=self.getMinRate(),
           player_status=self.media_engine.getStatus(),
           paused_time=self.getPausedTime(),
           last_fragment_size=self.getLastFragmentBytes(),
           last_download_time=self.getLastDownloadedTime(),
           start_segment_request=self.getStartSegmentRequest(),
           stop_segment_request=self.getStopSegmentRequest(),
           downloaded_bytes=self.getDownloadedBytes(),
           fragment_duration=self.parser.getFragmentDuration(),
           rates=self.getLevelRates(),
           is_check_buffering=flag_check_buffering
        )
        self.controller.setPlayerFeedback(self.feedback)
        
    def log(self):
        '''
        Logs useful metrics every ``log_period`` seconds
        '''
        if not self.logger:
           return
        stats = self.proc_stats.getStats()
        opts = dict(
           enqueued_b=self.media_engine.getQueuedBytes(),   #2
           enqueued_t=self.media_engine.getQueuedTime(),    #3
           bwe=self.getBandwidth(),                         #4
           cur=self.getCurrentRate(),                       #5
           level=self.getCurrentLevel(),                    #6
           max_level=self.getMaxLevel(),                    #7
           player_status=self.media_engine.getStatus(),     #8
           paused_time=self.getPausedTime(),                #9
           downloaded_bytes=self.getDownloadedBytes(),      #10
           cpu=stats["cpu_percent"],                        #11
           mem=stats["memory_percent"],                     #12    
           rss=stats["memory_rss"],                         #13
           vms=stats["memory_vms"],                         #14
           ts_start_req=self.getStartSegmentRequest(),      #15                      
           ts_stop_req=self.getStopSegmentRequest(),        #16                         
        )
        levels = self.parser.getLevels()
        for i in range(0,len(self.getLevelRates())):
           opts['q%d' %i] = float(levels[i]['rate'])
        self.logger.log(opts)
        del opts
        reactor.callLater(self.log_period, self.log)

    def _onNewSegment(self):
        '''
        Does something before calculating new control action
        '''
        pass

    # callback
    def _onDataReceiving(self, connection, data_diff, remaining_data):
        '''
        Does something before segment download is completed (used with persistent connection)
        '''
        self.remaining_data = remaining_data
        debug(DEBUG+1, '%s _onDataReceiving: %s %s', self, format_bytes(data_diff), format_bytes(remaining_data))
        self.rate_calc.update(data_diff)

    # callback
    def _onDataReceived(self, connection, data):
        '''
        Does something when segment download is completed (used with persistent connection)
        '''

        debug(DEBUG+1, '%s _onDataReceived: %s', self, format_bytes(len(data)))  
        self.playNextGotRequest(data, None)
        
    def _initConnection(self, url):
        '''
        Initializes connection with url (only with persistent connection)
        '''
        if self.connection:
            self.connection.stop()
        debug(DEBUG+1, '%s _initConnection: %s', self, url)
        self.connection = ClientFactory(url)
        self.connection.connect('connection-made', self._onConnectionMade)
        self.connection.connect('connection-lost', self._onConnectionLost)
        self.connection.connect('data-received', self._onDataReceived)
        self.connection.connect('data-receiving', self._onDataReceiving)

    def _onConnectionMade(self, connection, host):
        '''
        Does something when connection with host is established (only with persistent connection).
        '''
        debug(DEBUG+1, '%s _onConnectionMade: %s', self, host)
        if self.logger:
            self.logger.log_comment('Host: %s' %host)
        reactor.callLater(0.1, self.fetchNextSegment)

    def _onConnectionLost(self, connection):
        '''
        Does something when connection with host is lost (only with persistent connection).
        '''
        self.connection = None
        if self.parser.getPlaylistType()=='HLS':
            debug(0, '%s _onConnectionLost', self)
            self.parser.updateLevelSegmentsList(self.cur_level).addCallback(self._updatePlaylistDone)
        else:   #only for youtube (for check buffering)
            debug(DEBUG, '%s _onConnectionLost', self)
            self.fetchNextSegment()

    #When status changes calls 'onPlaying' and 'onPaused' hooks
    #callback
    def _onStatusChanged(self, media_engine):
        '''
        Does something when player status change from play to pause and viceversa
        '''
        if media_engine.status == media_engine.PLAYING:
            self.controller.onPlaying()
            self.paused_time += time.time() - self.t_paused 
        else:
            self.controller.onPaused()
            self.t_paused = time.time()

    #callback
    def _updatePlaylistDone(self, data):
        '''
        Called when the playlist for the current level is update
        '''
        playlist = self.parser.playlists[self.getCurrentLevel()]
        debug(DEBUG+1, '%s playlist: %s', self, pformat(playlist))
        # start play if playlist has more than 2 fragments
        if len(playlist['segments']) > 2 and self.getCurrentSegmentIndex() < playlist['end_index']:
            self.fetchNextSegment()
        else:
            reactor.callLater(self.parser.getFragmentDuration(), self.fetchNextSegment)
