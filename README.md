====================================================================
TAPAS - Tool for rApid Prototyping of Adaptive Streaming algorithms
====================================================================

TAPAS is a tool that allows rapid prototyping of Adaptive Streaming control algorithms.
If you are a developer and you want to design an test a new Adaptive Streaming control algorithm
you should check the documentation placed in the doc/ directory.

If you are a user and you want to experiment with the control algorithms made available
by TAPAS you can follow the instructions given below. 

Installation
------------

Ubuntu 14.04 LTS does not ship gstreamer0.10-ffmpeg package, you need to add a repository with
the following commands: ::

    sudo add-apt-repository ppa:mc3man/trusty-media
    sudo apt-get update
    
    sudo apt-get install python-twisted python-twisted-bin python-twisted-core python-twisted-web \
        gstreamer0.10-plugins-* gstreamer0.10-ffmpeg gstreamer0.10-tools python-gst-1.0 libgstreamer0.10-dev

Usage
-----

Play a default playlist: ::
    
    $ python play.py

Play a default playlist with a "conventional" adaptive controller: ::
    
    $ python play.py -a conventional

Play a playlist specified by its URL: ::

    $ python play.py -u http://mysite.com/myplaylist.m3u8

Play a sample MPEG-DASH video: ::
    
    $ python play.py -u http://yt-dash-mse-test.commondatastorage.googleapis.com/media/car-20120827-manifest.mpd
 
Play a playlist for logs, without decoding video: ::

	$ python play.py -m nodec

Play a playlist with a fake player (emulated playout buffer and no decoding): ::

	$ python play.py -m fake

Play only the highest quality of the playlist: ::

	$ python play.py -a max

Player options: ::

	$ python play.py --help

Enable debug mode: ::
    
    $ DEBUG=2 python play.py

Reference
---------
If you use TAPAS for your research, please cite the following paper 

Luca De Cicco, Vito Caldaralo, Vittorio Palmisano, Saverio Mascolo, "TAPAS: a Tool for rApid Prototyping of Adaptive Streaming algorithms", in Proc. of ACM VideoNext Workshop, Sydney, Australia, December 2014 


