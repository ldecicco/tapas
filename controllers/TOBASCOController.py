#!/usr/bin/env python
# -*- Mode: Python -*-
# -*- encoding: utf-8 -*-
# Copyright (c) Patrick Bartels <pckbls@gmail.com>

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE" in the source distribution for more information.

import math
from utils_py.util import debug, format_bytes
from BaseController import BaseController

DEBUG = 1

# This controller is an implementation of the TOBASCO Controller
# (Threshold-Based Adaptation Scheme for on-Demand Streaming)
# as described in "Adaptation Algorithm for Adaptive Streaming over HTTP"
# by K. Miller, E. Quacchio, G. Gennari and A. Wolisz

class TOBASCOController(BaseController):

    def __init__(self):
        super(TOBASCOController, self).__init__()

        # shows whether we are in fast start mode
        self.runningFastStart = True

        # algorithm configuration parameters
        self.conf = {
            "B_min": 5,
            "B_low": 10,
            "B_high": 50,
            "delta_beta": 1,
            "delta_t": 5,
            "alpha_1": 0.75,
            "alpha_2": 0.33,
            "alpha_3": 0.5,
            "alpha_4": 0.75,
            "alpha_5": 1.5 # choose 0.5 if a more conservative adaptation behavior is desired
        }

        # refer to isBuffering function for description
        self.isBufferingHack = True

        # the algorithm relies on past data, thus as an simple approach we simply save
        # all feedback data in a history list
        self.feedback_hist = []

    def __repr__(self):
        return '<TOBASCOController-%d>' % id(self)

    def setPlayerFeedback(self, dict_params):
        super(TOBASCOController, self).setPlayerFeedback(dict_params)

        # append the data to our feedback history
        self.feedback_hist.append(self.feedback)

    def isBuffering(self):
        # We want to control when to download a chunk at all times.
        # Therefore we explicitly disable TAPAS' buffering mode
        # except for the the very first call. This makes TAPAS
        # immediately start the download of the first chunk.
        if self.isBufferingHack:
            self.isBufferingHack = False
            return True
        else:
            return False

    def calcControlAction(self):
        # call the actual adaptation algorithm
        next_level, Bdelay = self.adaptationAlgorithm()

        # debug prints
        debug(DEBUG, "%s feedback %s", self, self.feedback)
        debug(DEBUG, "%s fast start mode = %d", self, self.runningFastStart)
        debug(DEBUG, "%s next_level = %d, Bdelay = %f", self, next_level, Bdelay)

        # The algorithm returns Bdelay which represents the minimum buffer level
        # in seconds of playback when the next download must be started.
        # TAPAS wants to know how long it has to wait until the download of the
        # next segment.
        # Therefore we assume the that the buffer fill state falls below Bdelay
        # after (buffered seconds - Bdelay) seconds.
        self.setIdleDuration(0 if Bdelay == 0 else (self.feedback["queued_time"] - Bdelay))

        return self.feedback['rates'][next_level]

    # for two time intervals t1 = [t1_b; t2_b] and t2 = [t2_b; t2_e]
    # calculate the intersecting amount of time
    def time_intersect(self, t1_b, t1_e, t2_b, t2_e):
        if t1_e <= t2_b or t1_b >= t2_e:
            # t2        |----| or |----|
            # t1 |----|                  |----|
            return 0
        elif t1_b < t2_b and t1_e > t2_b:
            # t2    |----|
            # t1 |----|
            return t1_e - t2_b
        elif t1_b < t2_e and t1_e > t2_e:
            # t2 |----|
            # t1    |----|
            return t2_e - t1_b
        else:
            # t2 |----|
            # t1  |--|
            return (t2_e - t2_b) - (t1_b - t2_b) - (t2_e - t1_e)

    # returns lowest buffer level observed in a certain interval around t
    def beta_min(self, t):
        result = -1

        t_start = math.floor(t / self.conf["delta_beta"]) * self.conf["delta_beta"]
        t_end = t_start + self.conf["delta_beta"]

        for feedback in self.feedback_hist:
            if feedback["stop_segment_request"] < t_start:
                continue

            if feedback["stop_segment_request"] > t_end:
                break

            if result == -1 or feedback["queued_time"] < result:
                result = feedback["queued_time"]

        return result

    # determines if beta_min is monotonically increasing until time t
    def beta_min_mono_incr(self, t):
        beta_min = -1

        for feedback in self.feedback_hist:
            if feedback["stop_segment_request"] > t:
                break

            beta_min_cmp = self.beta_min(feedback["stop_segment_request"])
            if beta_min == -1 or beta_min <= beta_min_cmp:
                beta_min = beta_min_cmp
            else:
                return False

        return True

    # calculates the average segment throughput during the time interval [t1, t2]
    def p_tilde(self, t1, t2):
        sum_o = 0
        sum_u = 0

        # loop over every segment
        for feedback in self.feedback_hist[1:]:
            # calculate time difference between segment download start and end
            t_i_b = feedback["start_segment_request"]
            t_i_e = feedback["stop_segment_request"]
            download_duration = t_i_e - t_i_b

            # ignore all segments that have been downloaded after t2
            if t_i_e > t2:
                break

            # get average bit-rate of representation
            p_dach_r_i = feedback["cur_rate"]

            # get segment duration
            tau = feedback["fragment_duration"]

            # calculate segment throughput of segment i
            #p_tilde_i = (p_dach_r_i * tau) / download_duration
            #p_tilde_i = feedback["last_fragment_size"] / download_duration
            p_tilde_i = feedback["bwe"]

            sum_o += p_tilde_i * self.time_intersect(t_i_b, t_i_e, t1, t2)
            sum_u += self.time_intersect(t_i_b, t_i_e, t1, t2)

        return sum_o / sum_u

    # the actual adaptation algorithm
    def adaptationAlgorithm(self):
        # several values that we need for the algorithm
        print(self.feedback)
        t = self.feedback["stop_segment_request"]
        tau = self.feedback["fragment_duration"]
        current_level = self.feedback["level"]
        max_level = self.feedback["max_level"]
        min_level = 0
        current_rate = self.feedback["cur_rate"]
        higher_rate = self.feedback["rates"][current_level if current_level == max_level else (current_level + 1)]
        lower_rate = self.feedback["rates"][current_level if current_level == 0 else (current_level - 1)]
        beta_t = self.feedback["queued_time"]
        p_tilde = self.p_tilde(t - self.conf["delta_t"], t)
        download_duration = self.feedback["stop_segment_request"] - self.feedback["start_segment_request"]
        B_opt = 0.5 * (self.conf["B_low"] + self.conf["B_high"])

        # We would like to manually calculate p_tilde_i however in some rare cases the calculation fails.
        # TAPAS provides a bandwidth estimator which does the same calculation reliably.
        #p_tilde_i = (current_rate * tau) / download_duration
        #p_tilde_i = self.feedback["last_fragment_size"] / download_duration
        p_tilde_i = self.feedback["bwe"]

        # this is going to be our result
        Bdelay = 0
        next_level = current_level

        # determine whether we should continue with fast start mode
        fastStartCond = self.runningFastStart

        # (i) check whether we have converged to the highest representation available
        fastStartCond = fastStartCond and current_level != max_level

        # (ii) check whether buffer level is monotonically increasing
        fastStartCond = fastStartCond and self.beta_min_mono_incr(t)

        # (iii) check if bitrate of the selected representation is too close to the measured throughput
        fastStartCond = fastStartCond and current_rate <= self.conf["alpha_1"] * p_tilde

        if fastStartCond:
            if beta_t < self.conf["B_min"]:
                if higher_rate <= self.conf["alpha_2"] * p_tilde:
                    next_level = current_level + 1
            elif beta_t < self.conf["B_low"]:
                if higher_rate <= self.conf["alpha_3"] * p_tilde:
                    next_level = current_level + 1
            else:
                if higher_rate <= self.conf["alpha_4"] * p_tilde:
                    next_level = current_level + 1
                if beta_t > self.conf["B_high"]:
                    Bdelay = self.conf["B_high"] - tau
        else:
            if self.runningFastStart:
                debug(DEBUG, "%s Leaving fast start mode", self)

            self.runningFastStart = False

            if beta_t < self.conf["B_min"]:
                next_level = min_level
            elif beta_t < self.conf["B_low"]:
                if current_level != min_level and current_rate > p_tilde_i:
                    next_level = current_level - 1
            elif beta_t < self.conf["B_high"]:
                if current_level == max_level or higher_rate >= self.conf["alpha_5"] * p_tilde:
                    Bdelay = max(beta_t - tau, B_opt)
            else:
                if current_level == max_level or higher_rate >= self.conf["alpha_5"] * p_tilde:
                    Bdelay = max(beta_t - tau, B_opt)
                else:
                    next_level = current_level + 1

        return (next_level, Bdelay)
