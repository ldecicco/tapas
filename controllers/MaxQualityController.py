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
from utils_py.util import debug, format_bytes
from BaseController import BaseController

DEBUG = 1

'''return always the max quality level without idle period between segments download'''
'''used as greedy tcp flow if estimated bandwidth is lower than the rate of the maximum level'''

class MaxQualityController(BaseController):

    def __init__(self):
        super(MaxQualityController, self).__init__()

    def __repr__(self):
        return '<MaxQualityController-%d>' %id(self)

    def calcControlAction(self):
        self.setIdleDuration(0.0)
        max_level = self.feedback['max_level']
        video_rates = self.feedback['rates']
        return video_rates[max_level]*1.5

        