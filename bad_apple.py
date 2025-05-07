"""Script to run bad apple using bsm module in bombsquad."""

import bascenev1 as bs
import bsm


def play():
    """
    Play the bad-apple video in the current activity.
    NOTE: It will take some time to load the video frames.
    """
    # dont change resolution, frames are 50x50 by default
    screen = bsm.Screen(resolution=(50, 50), char="@")
    video = bsm.Video(folder_name="bapf", resolution=(50, 50))
    bs.timer(5, bs.Call(screen.load, video, 30))
