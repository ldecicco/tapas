Media Engine
=============

This module provides methods to fill/drain the playout buffer and to decode and play the video stream.
The logic for draining the buffer, decode and play the video stream depends on the particular media engine. 
TAPAS already includes three media engines that allow to give different levels of detail to the experimental evaluation: 
	1) ``FullMediaEngine`` is a complete player that decodes and renders the raw video to the screen (for now it works only with MPEGTS container);
	2) ``NodecMediaEngine`` is a player that only demuxes the video stream without decoding and rendering the video;
	3) ``FakeMediaEngine`` only keeps track of the playout buffer length, but does not demux, decode, and render the video.
Both the ``FullMediaEngine`` and the ``NodecMediaEngine`` employ the *GStreamer* multimedia framework for playing the received video.

Base class methods
------------------

.. autoclass:: media_engines.BaseMediaEngine.BaseMediaEngine
   :members:
