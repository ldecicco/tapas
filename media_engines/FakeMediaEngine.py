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
from math import floor
import time, datetime
from utils_py.gstfunctions import *
if __name__ == '__main__':
    gst_init()
from twisted.internet import defer, reactor
#
from utils_py.util import debug, format_bytes
from BaseMediaEngine import BaseMediaEngine

DEBUG = 2

class FakeMediaEngine(BaseMediaEngine):
    def __init__(self, min_queue_time=10):
        BaseMediaEngine.__init__(self, min_queue_time)
        self.queue =  dict(byte=0, sec=0)  #Initialized playout buffer at 0B and 0s
        self.pushed_segments = []
        self.current_time = 0
        self.min_queue_time = min_queue_time

    def __repr__(self):
        return '<FakeMediaEngine-%d>' %id(self)

    def start(self):
        BaseMediaEngine.start(self)
        self.fakePlay(-1)
    
    def stop(self):
        BaseMediaEngine.stop(self)
            
    def onRunning(self):
        debug(DEBUG, '%s running', self)
        self.status = self.PLAYING
        self.emit('status-changed')
    
    def onUnderrun(self):
        debug(DEBUG, '%s underrun', self)
        self.queue['sec'] = 0
        self.status = self.PAUSED
        self.emit('status-changed')

    def pushData(self, data, fragment_duration, level, caps_data):
        debug(DEBUG, '%s pushData: pushed %s of data for level %s', self, 
            format_bytes(len(data)),
            level)
        self.queue['byte']+=len(data)
        self.queue['sec']+=fragment_duration
        self.pushed_segments.append(dict(len_segment=len(data),dur_segment=fragment_duration))

    def fakePlay(self, t_old):
        t_now = time.time()
        if self.status == self.PLAYING:
            play_time = t_now - t_old
            self.queue['sec'] = max(0, self.queue['sec'] - play_time)
            idx = self.getCurSegment(self.current_time)
            size = self.pushed_segments[idx]["len_segment"]
            dur = self.pushed_segments[idx]["dur_segment"]
            self.queue['byte'] = max(0, self.queue['byte'] - floor(size*play_time/dur))
            self.current_time += play_time
        elif self.status == self.PAUSED and self.queue['sec'] >= self.min_queue_time:
            self.onRunning()
        elif self.status == self.PLAYING and self.queue['sec'] <= 0:
            self.onUnderrun()
        reactor.callLater(0.1, self.fakePlay, time.time())

    def getQueuedTime(self):
        return self.queue['sec']

    def getQueuedBytes(self):
        return self.queue['byte']

    def getCurSegment(self, current_time):
        total_duration = self.pushed_segments[0]["dur_segment"]
        for i in range(0,len(self.pushed_segments)-1):
            if total_duration >= current_time:
                return i
            else:
                total_duration+=self.pushed_segments[i+1]["dur_segment"]
        return len(self.pushed_segments)-1
