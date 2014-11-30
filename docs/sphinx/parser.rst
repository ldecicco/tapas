Parser
======

The main task of a parser is to populate and update two data structures, ``playlists`` and ``levels``, which are used by ``TapasPlayer``.

The ``playlists`` data structure is a list of dictionaries, one for each available video level. The dictionary has to include the following keys:
	1) ``url``: the video level base URL;
	2) ``is_live``: true if the video is a live stream;
	3) ``segments``: a list of dictionaries. Each dictionary contains: the ``segment_url``; the ``segment_duration``; and the ``byterange``, when the video segmentation is logic.
	4) ``start_index``: index of the first chunk to be downloaded by the *Downlaoder*;
	5) ``end_index``: index of the last chunk of the current playlist;
	6) ``duration``: the duration (in seconds) of the playlist.

The ``levels`` data structure is a list of dictionaries, one for each available video level. The dictionary has to include the following keys: 
	1) ``rate``: is the encoding rate of the video level measured in bytes/s; 
	2) ``resolution``: is the video level resolution.

Base class methods
------------------

.. autoclass:: parsers.BaseParser.BaseParser
   :members: