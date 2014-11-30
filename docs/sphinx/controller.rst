Controller
===========

The controller is the central component of the adaptive video streaming system. Its goal is to decide the video level,
among those advertised in the manifest files, based on ``feedback``, such as the estimated bandwidth or the playout buffer
length, and the player *state*.

The default ``feedback`` dictionary, that ``TapasPlayer`` updates before calling any new ``calcControlAction()``, is presented in the following table:

+------------------------+------------------------+
| Key                    | Unit                   |
+========================+========================+
| queued_bytes           | Bytes                  |
+------------------------+------------------------+
| queued_time            | seconds                |
+------------------------+------------------------+
| max_buffer_time        | seconds                |
+------------------------+------------------------+
| bwe                    | Bytes/sec              |
+------------------------+------------------------+
| level                  | [ ]                    |
+------------------------+------------------------+
| max_level              | [ ]                    |
+------------------------+------------------------+
| cur_rate               | Bytes/sec              |
+------------------------+------------------------+
| max_rate               | Bytes/sec              |
+------------------------+------------------------+
| min_rate               | Bytes/sec              |
+------------------------+------------------------+
| player_status          | boolean                |
+------------------------+------------------------+
| paused_time            | seconds                |
+------------------------+------------------------+
| last_fragment_size     | Bytes                  |
+------------------------+------------------------+
| last_fragment_time     | seconds                |
+------------------------+------------------------+
| downloaded_bytes       | Bytes                  |
+------------------------+------------------------+
| fragment_duration      | seconds                |
+------------------------+------------------------+
| rates                  | Bytes/sec {list}       |
+------------------------+------------------------+
| is_check_buffering     | boolean                |
+------------------------+------------------------+

Typically, an adaptive video streaming controller can be in two different states: *buffering* or *steady state*. When in *buffering*, the client requests a new segment right after the previous has been downloaded in order to quickly build up the player queue; on the other hand,
during the *steady state* an ``idle period`` has to elapse to request a new video segment after the last segment download has been completed.

Base class methods
------------------

.. autoclass:: controllers.BaseController.BaseController
   :members:

Rapid prototyping
-----------------

Now we consider an example showing how an adaptive streaming controller can be implemented. To the purpose we consider a simple controller, named *ConventionalController*, that is described in details `here`_.

.. _here: http://arxiv.org/pdf/1305.0510.pdf

.. code-block:: python
   :linenos:
	
   class ConventionalController(BaseController):
      def __init__(self):
         super(ConventionalController, self).__init__()
         #Controller parameters
         self.Q = 15 #seconds
         self.alpha = 0.2 #Ewma filter
         self.steady_state = False

      def calcControlAction(self):
         T = self.feedback[’last_download_time’]
         cur = self.feedback[’cur_rate’]
         tau = self.feedback[’fragment_duration’]
         x = cur * tau / T
         y = self.ewma_filter(x)
         self.setIdleDuration(tau - T)
         return y

      def isBuffering(self):
         return self.feedback[’queued_time’]<self.Q

      def quantizeRate(self,rate):
         ...
         return level

      def ewma_filter(self,rate):
         ...
         return filtered_rate

After that, we associate a string to this controller (e.g 'conventional') and update the options and imports in ``play.py`` to use this controller with TAPAS from command line.