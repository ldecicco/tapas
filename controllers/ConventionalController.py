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
from utils_py.util import debug, format_bytes, CircularBuffer
from BaseController import BaseController

DEBUG = 1

class ConventionalController(BaseController):

    def __init__(self):
        super(ConventionalController, self).__init__()
        self.iteration = 0
        self.t_last = -1
        self.filter_old = -1
        #Controller parameters
        self.Q = 15 #seconds
        self.alpha = 0.2 #Ewma filter
        self.eps = 0.15
        self.steady_state = False

    def __repr__(self):
        return '<ConventionalController-%d>' %id(self)

    def calcControlAction(self):    
        T = self.feedback['last_download_time']
        cur = self.feedback['cur_rate']
        tau = self.feedback['fragment_duration']
        x = cur * tau / T
        y = self.__ewma_filter(x) 
        self.setIdleDuration(tau-T)
        debug(DEBUG, "%s calcControlAction: y: %s/s x: %s/s T: %.2f", self, 
            format_bytes(y), format_bytes(x), T)
        return y

    def isBuffering(self):
        return self.feedback['queued_time'] < self.Q

    def quantizeRate(self,rate):
        video_rates = self.feedback['rates']
        cur = self.feedback['cur_rate'] 
        level = self.feedback['level']
        D_up = self.eps*rate
        D_down = 0
        
        r_up = self.__levelLessThanRate(rate - D_up)
        r_down = self.__levelLessThanRate(rate - D_down)
        new_level = 0
        if level < r_up:
            new_level = r_up
        elif r_up <= level and level <= r_down:
            new_level = level
        else:
            new_level = r_down
        debug(DEBUG, "%s quantizeRate: rate: %s/s cur: %s/s D_up: %s/s D_down: %s/s r_up: %d r_down: %d new_level: %d", self, 
            format_bytes(rate), format_bytes(cur), format_bytes(D_up), format_bytes(D_down), r_up, r_down, new_level)
        debug(DEBUG, "%s quantizeRate: rates: %s", self, video_rates)
        return new_level

    def __ewma_filter(self, x):
        #First time called
        if self.filter_old < 0:
            self.filter_old = x
            return x
        T = self.feedback['last_download_time']
        y_old = self.filter_old
        y = y_old - T * self.alpha * ( y_old - x )
        self.filter_old = y
        return y

    def __levelLessThanRate(self, rate):
        vr = self.feedback['rates']
        l = 0
        for i in range(0,len(vr)):
            if rate >= vr[i]:
                l = i
        return l
