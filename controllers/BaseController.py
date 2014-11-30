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
from utils_py.util import debug

DEBUG = 1

'''feedback = dict('queued_bytes':[B],
   'queued_time':[s],
   'max_buffer_time':[s],
   'bwe':[B/s],
   'level':[],
   'max_level':[],
   'cur_rate':[B/s],
   'max_rate':[B/s],
   'min_rate':[B/s],
   'player_status':[boolean],
   'paused_time':[s],
   'last_fragment_size':[B],
   'last_download_time':[s],
   'downloaded_bytes':[B],
   'fragment_duration':[s],
   'rates':[B/s{list}],
   'is_check_buffering:[boolean]
)'''

class BaseController(object):

    def __init__(self):
        self.idle_duration = 4
        self.control_action =  None
        self.feedback = None

    def __repr__(self):
        return '<BaseController-%d>' %id(self)

    def calcControlAction(self):
        '''
        Computes the control action. It must return a value in B/s
        (It must be implemented for new controller).
        '''
        raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")

    def setControlAction(self,rate):
        '''
        Sets the value of control action in B/s

        :param rate: the result of control action.
        '''
        self.control_action = rate

    def getControlAction(self):
        '''
        Gets the value of control action in B/s
        '''
        return self.control_action

    def isBuffering(self):
        '''
        Boolean expression returning true if the state of the player is buffering

        :rtype: bool
        '''
        return self.feedback['queued_time'] < self.feedback['max_buffer_time']
   
    def getIdleDuration(self):
        '''
        Gets the ``idle duration`` when the state of player is not buffering
        '''
        return self.idle_duration

    def setIdleDuration(self, idle):
        '''
        Sets idle duration when in steady state

        :param idle: seconds of idle between two consecutive downloads.
        '''
        if idle < 0:
            idle = 0
        debug(DEBUG, '%s setting Idle duration: %.2f', self, idle)
        self.idle_duration = idle

    def onPlaying(self):
        '''
        Called when changing state from pause to play
        '''
        #raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")
        pass

    def onPaused(self):
        '''
        Called when changing state from play to pause (re-buffering event)'''
        #raise NotImplementedError("Subclasses should implement "+inspect.stack()[0][3]+"()")
        pass

    def setPlayerFeedback(self, dict_params):
        '''
        Sets the dictionary of all player feedback used for the control. 
        This method is called from ``TapasPlayer`` before ``calcControlAction``

        :param dict_params: dictionary of player feedbacks.
        '''
        self.feedback = dict_params

    def quantizeRate(self, rate):
        '''
        Returns the highest level index below the ``rate``

        :param rate: rate to be quantized.
        :rtype: int
        '''
        new_level = 0
        r=self.feedback['rates']
        for i in range(0,len(r)):
            if rate >= r[i]:
                new_level = i
        return new_level

