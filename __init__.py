"""Package to run bad apple using bsm module in bombsquad."""

from babase import Plugin

import bascenev1 as bs
import bsm


# brobord collide grass
# ba_meta require api 9
# ba_meta export plugin
class BadApple(Plugin):

    def play(self):
        """
        Play the bad-apple video in the current activity.
        NOTE: It will take some time to load the video frames.
        """
        # dont change resolution, frames are 50x50 by default
        # this position looks good on football and hockey map.
        screen = bsm.Screen(position=(-3.5, 1, 3.2), resolution=(50, 50), char="@")
        video = bsm.Video(folder_name="BSM/bad_apple_ppm_frames", resolution=(50, 50))
        bs.timer(5, bs.Call(screen.load, video, 30))
