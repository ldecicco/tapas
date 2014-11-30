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
import inspect
from twisted.internet import defer

class BaseParser(object):
    
    def __init__(self,url,playlists_type,video_container):
        self.url = url
        self.fragment_duration = -1
        self.levels = None
        self.playlists = None
        self.caps_demuxer = None
        self.playlists_type = playlists_type
        self.video_container = video_container
        self.deferred = defer.Deferred()

    def __repr__(self):
        return '<BaseParser-%d>' %id(self)
    
    def loadPlaylist(self):
        '''
        Called to start the download of the playlists for each level. 
        (It must be implemented for new parser).
        '''
        raise NotImplementedError("Subclass must implement "+inspect.stack()[0][3]+"()")
       
    def getPlaylists(self):
        '''
        For eache level, gets its playlist with the segments properties (e.g. list of segment url, segments duration etc.)

        :rtype: list of dictionaries
        ''' 
        if not self.playlists or not isinstance(self.playlists,list):
            raise AttributeError("Playlist is empty")
        return self.playlists
     
    def getLevels(self):
        '''
        Gets the list of levels.
        Returns a list of dictionary with rate (in B/s) and resolution for each entry

        :rtype: list of dictionaries
        '''
        if not self.levels or not isinstance(self.levels,list):
            raise AttributeError("Video levels is empty. Check the documentation for further details on the structure of this attribute")
        return self.levels

    def getFragmentDuration(self):
        '''
        Gets the nominal fragment duration in seconds for the current playlist

        :rtype: int
        '''
        if self.fragment_duration < 0:
            raise AttributeError("Fragment duration has not been set yet.")
        return self.fragment_duration

    def getVideoContainer(self):
        '''
        Gets the video container type (e.g. MP4 or MPEGTS)

        :rtype: str
        '''
        return self.video_container

    def getPlaylistType(self):
        '''
        Gets the playlist type (e.g. HLS or DASH)
        
        :rtype: str
        '''
        return self.playlists_type

    #FIXME on level switch for mp4 segments
    def _getCapsDemuxer(self):
        return self.caps_demuxer
