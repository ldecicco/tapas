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
import gobject
#
from utils_py.util import debug, format_bytes

DEBUG = 2

class BaseMediaEngine(gobject.GObject):
    __gsignals__ = {
        'status-changed': (
            gobject.SIGNAL_RUN_LAST, 
            gobject.TYPE_NONE, #return
            () # args
        ),
    }

    PAUSED = 0
    PLAYING = 1

    def __init__(self, min_queue_time=10):
        gobject.GObject.__init__(self)
        self.min_queue_time = min_queue_time
        self.is_runnning = False
        self.status = self.PAUSED
        self.video_container = None

    def __repr__(self):
        return '<PlayerBase-%d>' %id(self)

    def start(self):
        '''
        Starts the media engine.
        '''
        if self.is_runnning:
            return
        debug(DEBUG, '%s start', self)
        self.is_runnning = True

    def stop(self):
        '''
        Stops the media engine.
        '''
        if not self.is_runnning:
            return
        debug(DEBUG, '%s stop', self)
        self.is_runnning = False

    def onRunning(self):
        '''
        Called when changing state from pause to play.
        (It must be implemented for new media engine).
        '''
        raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")

    def pushData(self, data, fragment_duration, level, caps):
        '''
        Enqueues data into the playout buffer. Called when the segment download is completed.
        (It must be implemented for new media engine).

        :param data: data downloaded
        :param fragment_duration: duration of the segment to be appendend
        :param level: the level of the segment downloaded.
        :param caps: codec data to be passed to the pipeline for mp4 videos.
        '''
        raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")

    def getQueuedBytes(self):
        '''
        Gets the amount of data (in bytes) in the playout buffer.
        '''
        return 0

    def getQueuedTime(self):
        '''
        Gets the amount of data (in seconds) in the playout buffer.
        '''
        raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")

    def getStatus(self):
        '''
        Gets the player status. 
        Returns true when the media engine is in play. Returns false when the media engine is in pause.

        :rtype: bool
        '''
        return self.status

    def getVideoContainer(self):
        '''
        Gets the video container type (e.g. MP4 or MPEGTS).

        :rtype: str
        '''
        return self.video_container

    def setVideoContainer(self,video_container):
        '''
        Sets the video container type. Called from the Parser instance.

        :param video_container: string of the corresponding video container (e.g. MP4 or MPEGTS).
        '''
        self.video_container = video_container
