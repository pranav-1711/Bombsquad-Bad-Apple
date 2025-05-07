# BSMedia - Play media in the scene
# Copyright 2025 - Solely by BrotherBoard
# Feedback is appreciated - Telegram >> @GalaxyA14user

"""
BSMedia Plugin for BombSquad

Provides functionality to display static images (PPM format) and play video
sequences (PPM frames with a stamps.json timing file) within the BombSquad
scene using a grid of text nodes as pixels.

Supports concurrent loading of media data and offers playback controls
for video media.

Classes:
    Pixel: Represents a single text node used as a pixel.
    Image: Handles concurrent loading of a single PPM image.
    Video: Handles concurrent loading and playback of a video sequence
           from a folder containing PPM frames and a stamps.json file.
    Screen: Manages a grid of Pixel nodes and loads/displays Image or Video media.
    byBordd: The main BombSquad Plugin class.

Functions:
    calc: Parses PPM image data and resizes it to a target resolution.
    ROOT: Returns the base directory for BSMedia files (user mods/BSM).
"""

from os import makedirs
from os.path import join, isabs, exists
from json import load, JSONDecodeError
from math import floor
from bascenev1 import (
    timer as tick,
    newnode,
    Call,
    getactivity,
    Activity
)
from babase import (
    Plugin,
    env,
    pushcall
)
from threading import Thread
from time import time
from traceback import print_exc

ROOT = lambda: join(env()['python_directory_user'], 'BSM')

try:
    makedirs(ROOT(), exist_ok=True)
except Exception as e:
    print(f"BSM Error: Failed to create root directory {ROOT()}: {e}")

class Pixel:
    __doc__ = """
        Represents a single pixel (text node) in the BombSquad scene.

        Each Pixel instance corresponds to a single text node used to
        display a colored character, forming part of the overall image
        or video frame on a Screen.

        Attributes:
            node: The bascenev1.Node of type 'text' representing the pixel.
                  None if node creation failed.
    """
    def __init__(
        s,
        pos: tuple[float, float, float],
        color: tuple[float, float, float],
        scale: float,
        dsp: str
    ) -> None:
        """
        Initializes a Pixel instance and creates its text node.

        Args:
            pos: The (x, y, z) position of the pixel node in world coordinates.
            color: The initial (r, g, b) color tuple for the pixel node.
            scale: The scale of the pixel node.
            dsp: The character string to display for the pixel (e.g., '\u25A0').
        """
        s.node = None
        try:
            s.node = newnode(
                'text',
                delegate=s,
                attrs={
                    'text': dsp,
                    'position': pos,
                    'in_world': True,
                    'color': color,
                    'shadow': 0.0,
                    'flatness': 1.0,
                    'scale': scale
                }
            )
        except Exception as e:
            print(f"BSMPixel Error: Could not create node at {pos}: {e}")

    def set(s,c) -> None:
        """
        Sets the color of the pixel node.

        Args:
            c: The (r, g, b) color tuple to set.
        """
        if s.node and s.node.exists():
            s.node.color = c

    def delete(s) -> None:
        """
        Deletes the pixel node from the scene.
        """
        if s.node and s.node.exists():
            try:
                s.node.delete()
            except Exception as e:
                 print(f"BSMPixel Error during node deletion: {e}")
            s.node = None

class Image:
    __doc__ = """
        Handles concurrent loading of a single PPM image file.

        The Image class is used to load static images onto a Screen.
        It specifically requires PPM (Portable Pixmap) files in P6 binary format.
        The image file should be placed within the ROOT() directory or a subfolder
        thereof, and the 'path' argument should be relative to ROOT().

        Example File Structure:
            <BombSquad User Directory>/BSM/my_image.ppm
            <BombSquad User Directory>/BSM/images/another_image.ppm

        Loading Examples:
            # If my_image.ppm is directly in the BSM folder
            img = Image(path='my_image.ppm', resolution=(100, 50))

            # If another_image.ppm is in BSM/images/
            img = Image(path='images/another_image.ppm', resolution=(100, 50))


        The image data is loaded and processed in a separate thread to
        avoid blocking the main BombSquad thread. A callback can be
        registered to be notified when processing is complete.

        Attributes:
            path: The path to the PPM file (relative to ROOT()).
            res: The target resolution (width, height) for resizing, or None.
            data: The processed pixel data (list of color tuples) once complete.
                  None if processing failed or not yet complete.
            processing_complete: True if processing has finished (successfully or with error).
            error: An error message string if processing failed, otherwise None.
            on_data_ready_callback: A function to call when processing is complete.
    """
    def __init__(
        s,
        path: str,
        resolution: tuple[int,int] = None
    ) -> None:
        """
        Initializes an Image instance and starts background processing.

        Args:
            path: The path to the PPM file (relative to ROOT()).
            resolution: An optional tuple (width, height) to resize the image to.
                        If None, the original PPM resolution is used.
        """
        s.path = path
        s.res = resolution
        s.data = None
        s.processing_complete = False
        s.error = None
        s.on_data_ready_callback = None

        s.start_processing()

    def start_processing(s) -> None:
        """Initiates background thread for image processing."""
        act = getactivity()
        if act is None or act.expired:
             print("BSMImage Warning: No active activity when starting processing.")

        thread = Thread(target=s._perform_calc)
        thread.daemon = True
        thread.start()

    def _perform_calc(s) -> None:
        """Internal method run in a separate thread to call the calc function."""
        try:
            pa = calc(s.path, s.res)
            pushcall(lambda: s._on_calc_complete(pa), from_other_thread=True)
        except Exception as e:
            error_msg = f"Error processing image {s.path}: {e}"
            print(f"BSMImage Error: {error_msg}")
            pushcall(lambda: s._on_calc_complete(None, error_msg), from_other_thread=True)

    def _on_calc_complete(s, pa, err = None) -> None:
        """Callback executed in the main thread when background processing finishes."""
        s.data = pa
        s.error = err
        s.processing_complete = True

        if s.on_data_ready_callback:
            act = getactivity()
            if act and not act.expired:
                try:
                    with act.context:
                        s.on_data_ready_callback(s)
                except Exception as e:
                    print(f"BSMImage Error in callback: {e}")
                    print_exc()
            else:
                 print("BSMImage Warning: No valid activity context for callback.")


    def set_on_data_ready_callback(s, callback) -> None:
        """
        Sets a callback function to be called when the image data is ready.

        Args:
            callback: A function that takes the Image instance as its argument.
                      Called in the main BombSquad thread within an activity context.
        """
        s.on_data_ready_callback = callback
        if s.processing_complete:
             act = getactivity()
             if act and not act.expired:
                 try:
                    with act.context:
                        s.on_data_ready_callback(s)
                 except Exception as e:
                    print(f"BSMImage Error in callback: {e}")
                    print_exc()
             else:
                 print("BSMImage Warning: No valid activity context for immediate callback.")

class Video:
    __doc__ = """
        Handles concurrent loading and playback of a video sequence.

        The Video class loads a sequence of PPM frames from a specified folder
        located inside the ROOT() directory. This folder must contain:
        1.  PPM frame files (e.g., frame_0000.ppm, frame_0001.ppm, ...).
        2.  A 'stamps.json' file mapping cumulative timestamps (in seconds)
            to the corresponding frame filenames.

        The 'stamps.json' file should be a JSON object where keys are string
        representations of cumulative timestamps (e.g., "0.0", "0.04", "0.08")
        and values are the corresponding frame filenames (e.g., "frame_0000.ppm").
        Timestamps should be sorted in ascending order.

        Example File Structure:
            <BombSquad User Directory>/BSM/my_video/stamps.json
            <BombSquad User Directory>/BSM/my_video/frame_0000.ppm
            <BombSquad User Directory>/BSM/my_video/frame_0001.ppm
            ...

        Loading Example:
            # If your video files are in <User Dir>/BSM/my_video/
            video = Video(folder_name='my_video', resolution=(80, 40))
            my_screen.load(video, speed=1.0, loop=True)

        Loading and processing of individual frames happen concurrently
        in background threads. Playback is managed by a timer in the
        main BombSquad thread.

        Attributes:
            folder_name: The name of the folder (relative to ROOT()) containing video files.
            res: The target resolution (width, height) for resizing frames, or None.
            data: A dictionary {timestamp: pixel_array} storing loaded frame data.
            timestamp_map: A dictionary {timestamp: filename} read from stamps.json.
            frames_to_process: Total number of frames to load.
            processed_frames: Number of frames successfully processed so far.
            error: An error message string if loading/processing failed, otherwise None.
            processing_complete: True if all frames have finished processing.
            on_data_ready_callback: A function to call when all frame data is loaded.
            video_play_timer: The BombSquad timer used for playback.
            current_video_frame_index: The index of the currently displayed frame in the sorted timestamps.
            video_playback_speed: The multiplier for playback speed (1.0 is normal).
            video_loop: True if the video should loop when it reaches the end.
    """
    def __init__(
        s,
        folder_name: str,
        resolution: tuple[int, int] = None
    ) -> None:
        """
        Initializes a Video instance and starts background loading of frames.

        Args:
            folder_name: The name of the folder located inside ROOT()
                         This folder must contain 'stamps.json' and the frame files.
            resolution: An optional tuple (width, height) to resize each frame to.
                        If None, the original PPM resolution is used.
        """
        s.folder_name = folder_name
        s.res = resolution
        s.data = {}
        s.timestamp_map: dict[float | int, str] = {}
        s.frames_to_process = 0
        s.processed_frames = 0
        s.error = None
        s.processing_complete = False
        s.on_data_ready_callback = None

        s.start_processing()

    def start_processing(s) -> None:
        """Initiates background process to read timestamps and load frames."""
        act = getactivity()
        if act is None or act.expired:
             print("BSMVideo Warning: No active activity when starting processing.")

        timestamp_map = s._read_timestamp_map_from_folder()
        if timestamp_map is None:
            s.error = f"Failed to read timestamps from folder '{s.folder_name}'"
            s.processing_complete = True
            print(f"BSMVideo Error: {s.error}")
            s._on_processing_complete()
            return

        s.timestamp_map = timestamp_map
        s.frames_to_process = len(s.timestamp_map)

        if s.frames_to_process == 0:
            print("BSMVideo: No frames found in stamps.json, complete.")
            s.processing_complete = True
            s._on_processing_complete()
            return

        print(f"BSMVideo: Start processing {s.frames_to_process} frames from folder '{s.folder_name}'.")
        s.processed_frames = 0
        s.error = None
        s.processing_complete = False

        for timestamp, filename in s.timestamp_map.items():
            thread = Thread(target=s._process_frame, args=(timestamp, filename, s.res))
            thread.daemon = True
            thread.start()

    def _read_timestamp_map_from_folder(s) -> dict[float | int, str] | None:
        """Reads and returns the timestamp map from stamps.json in the folder."""
        folder_full_path = join(ROOT(), s.folder_name)
        json_path = join(folder_full_path, 'stamps.json')
        try:
            if not exists(json_path):
                 print(f"BSMVideo Error: stamps.json not found in folder '{s.folder_name}'.")
                 return None

            with open(json_path, 'r') as f:
                timestamp_map = load(f)
                converted_map = {}
                for key, value in timestamp_map.items():
                     try:
                         if '.' in key:
                             converted_key = float(key)
                         else:
                             converted_key = int(key)
                     except ValueError:
                         converted_key = key
                     converted_map[converted_key] = value
                return converted_map

        except FileNotFoundError:
            print(f"BSMVideo Error: stamps.json not found at '{json_path}'.")
            return None
        except JSONDecodeError:
            print(f"BSMVideo Error: Could not decode '{json_path}'. Is it valid JSON?")
            return None
        except Exception as e:
            print(f"BSMVideo Error reading '{json_path}': {e}")
            return None


    def _process_frame(s, timestamp, filename, res) -> None:
        """Internal method run in a separate thread to load and process a single frame."""
        frame_relative_path = join(s.folder_name, filename)
        try:
            pa = calc(frame_relative_path, res)
            pushcall(lambda: s._on_frame_processed(timestamp, pa), from_other_thread=True)
        except Exception as e:
            error_msg = f"Error frame '{frame_relative_path}' at {timestamp}: {e}"
            print(f"BSMVideo Error: {error_msg}")
            pushcall(lambda: s._on_frame_processed(timestamp, None, error_msg), from_other_thread=True)


    def _on_frame_processed(
        s,
        t,
        pa,
        err = None
    ) -> None:
        """Callback executed in the main thread when a single frame processing finishes."""
        s.processed_frames += 1

        if err:
            if s.error is None:
                s.error = err
            print(f"BSMVideo: Frame {t} failed: {err}")

        if pa is not None:
            s.data[t] = pa

        if s.processed_frames >= s.frames_to_process:
            s.processing_complete = True
            print(f"BSMVideo: All {s.frames_to_process} frames processed.")
            s._on_processing_complete()

    def _on_processing_complete(s) -> None:
        """Callback executed in the main thread when all video frames are processed."""
        if s.error:
            print(f"BSMVideo: Video processing finished with errors: {s.error}")
        else:
            print("BSMVideo: Video processing finished successfully.")

        if s.on_data_ready_callback:
            act = getactivity()
            if act and not act.expired:
                try:
                    with act.context:
                        s.on_data_ready_callback(s)
                except Exception as e:
                    print(f"BSMVideo Error in callback: {e}")
                    print_exc()
            else:
                 print("BSMVideo Warning: No valid activity context for callback.")


    def set_on_data_ready_callback(s, callback) -> None:
        """
        Sets a callback function to be called when all video frame data is ready.

        Args:
            callback: A function that takes the Video instance as its argument.
                      Called in the main BombSquad thread within an activity context.
        """
        s.on_data_ready_callback = callback
        if s.processing_complete:
             act = getactivity()
             if act and not act.expired:
                 try:
                    with act.context:
                        s.on_data_ready_callback(s)
                 except Exception as e:
                    print(f"BSMVideo Error in callback: {e}")
                    print_exc()
             else:
                 print("BSMVideo Warning: No valid activity context for immediate callback.")


    def delete(s) -> None:
        """Cleans up the Video instance."""
        print("BSMVideo: Delete called.")
        s.timestamp_map = {}
        s.data = {}
        s.on_data_ready_callback = None


class Screen:
    __doc__ = """
        Manages a grid of Pixel nodes and displays Image or Video media on them.

        The Screen class creates and positions the grid of text nodes that
        act as pixels. It handles loading media onto this grid and managing
        video playback, including speed and looping.

        Attributes:
            pos: The (x, y, z) position of the bottom-left corner of the screen grid.
            res: The resolution (width, height) of the screen grid (number of pixels).
            scale: The scale of individual pixel nodes.
            spacing_val: The spacing between pixel nodes ('auto' or a float value).
            char: The character used for pixel nodes.
            pixels: A list of Pixel instances forming the screen grid.
            media: The currently loaded Image or Video instance.
            video_data: The pixel data for video frames (from the loaded Video instance).
            video_timestamps: Sorted list of timestamps for video frames.
            video_play_timer: The BombSquad timer controlling video frame updates.
            current_video_frame_index: The index of the currently displayed frame in the sorted timestamps.
            video_playback_speed: The current playback speed multiplier.
            video_loop: Whether the currently loaded video should loop.
    """
    def __init__(
        s,
        position: tuple[float, float, float] = (0, 0, 0),
        resolution: tuple[int, int] = (100,50),
        scale: float = 0.01,
        spacing: float | str = 'auto',
        char: str = '\u25A0',
        media: Image | Video = None
    ) -> None:
        """
        Initializes a Screen instance and creates its pixel grid.

        Args:
            position: The (x, y, z) position of the bottom-left corner of the screen.
                      Defaults to (-2, 1, 1).
            resolution: The resolution (width, height) of the screen grid.
                        Defaults to (100, 50).
            scale: The scale of individual pixel nodes. Defaults to 0.01.
            spacing: The spacing between pixel nodes. 'auto' calculates spacing
                     based on scale, otherwise a float value can be provided.
                     Defaults to 'auto'.
            char: The character used for pixel nodes. Defaults to a solid block '\u25A0'.
            media: An optional Image or Video instance to load immediately upon creation.
                   Defaults to None.
        """
        s.pos = position
        s.res = resolution
        s.scale = scale
        s.spacing_val = spacing
        s.char = char
        s.media = None
        s.video_data = None
        s.video_timestamps = None
        s.video_play_timer = None
        s.current_video_frame_index = 0
        s.video_playback_speed = 1.0
        s.video_loop = False

        px,py,pz = position
        rx,rz = resolution
        sc = scale
        sp = s.spacing_val
        if sp == 'auto':
            sp = sc * 13.5


        s.pixels = []
        act = getactivity()
        if act and not act.expired:
             try:
                with act.context:
                    for i in range(rz):
                        for j in range(rx):
                            # Position pixels bottom-left to top-right

                            # EDIT: making screen in x-z plane
                            # NOTE: pos-z is outside the plane.
                            p_pos = (px + j * sp, py, pz - i * sp)
                            p = Pixel(
                                pos=p_pos,
                                color=(0,0,0),
                                scale=sc,
                                dsp=char
                            )
                            if p.node:
                                s.pixels.append(p)
                            else:
                                print(f"BSMScreen Warning: Failed to create pixel node at {p_pos}")
             except Exception as e:
                 print(f"BSMScreen Error creating pixel nodes: {e}")
                 print_exc()
                 s.delete()
        else:
             print("BSMScreen Warning: No active activity when creating screen. Pixel nodes not created.")


        if media: s.load(media)

    def load(s, media: Image | Video, speed: float = 1.0, loop: bool = False) -> None:
        """
        Loads an Image or Video onto the screen.

        If a Video is loaded, playback starts automatically.

        Args:
            media: The Image or Video instance to load.
            speed: Playback speed multiplier for videos (1.0 is normal).
                   Defaults to 1.0. Must be > 0.
            loop: Whether the video should loop when it finishes. Defaults to False.
        """
        s.media = media
        s.video_data = None
        s.video_timestamps = None
        s._stop_video_playback()

        s.video_playback_speed = max(0.01, speed)
        s.video_loop = loop

        if media.processing_complete:
            s._load_data_to_pixels(media)
        else:
            print(f"BSMScreen: Media data not ready, waiting for callback.")
            media.set_on_data_ready_callback(s._on_media_data_ready)

    def _on_media_data_ready(s, media: Image | Video) -> None:
        """Callback executed when the loaded media's data is ready."""
        if media.error:
            print(f"BSMScreen: Media loading failed with error: {media.error}")
            return

        if s.media is not media:
            print("BSMScreen Warning: Received callback for media that is no longer loaded.")
            return

        print(f"BSMScreen: Media data ready, loading onto screen.")
        s._load_data_to_pixels(media)

    def _load_data_to_pixels(s, media: Image | Video) -> None:
        """Loads the processed media data onto the pixel grid."""
        act = getactivity()
        if act is None or act.expired:
            print("BSMScreen Error: Cannot load data. Activity context gone or invalid.")
            return

        try:
            with act.context:
                if isinstance(media, Image):
                    if media.data and len(media.data) == len(s.pixels):
                        for i, color in enumerate(media.data):
                            s.pixels[i].set(color)
                    elif media.data is None:
                         print("BSMScreen Error: Image data is None.")
                    else:
                        print(f"BSMScreen Error: Image data size ({len(media.data)}) mismatch with pixel count ({len(s.pixels)}).")

                elif isinstance(media, Video):
                    s.video_data = media.data
                    if s.video_data:
                        s.video_timestamps = sorted(s.video_data.keys())
                        s.current_video_frame_index = 0
                        s._start_video_playback()
                    else:
                        print("BSMScreen Error: Video data is empty.")

                else:
                    print(f"BSMScreen Error: Cannot load unknown media type {type(media)}")

        except Exception as e:
            print(f"BSMScreen Error loading data: {e}")
            print_exc()


    def _start_video_playback(s) -> None:
        """Starts the video playback timer."""
        s._stop_video_playback()
        if s.video_timestamps and s.pixels:
            s._play_next_video_frame()

    def _stop_video_playback(s) -> None:
        """Stops the video playback timer."""
        if s.video_play_timer:
            s.video_play_timer.cancel()
            s.video_play_timer = None

    def _play_next_video_frame(s) -> None:
        """Displays the next video frame and schedules the subsequent one."""
        if not s.video_timestamps or not s.pixels:
             print("BSMScreen Warning: Playback called with no data or pixels.")
             s._stop_video_playback()
             return

        if s.current_video_frame_index < len(s.video_timestamps):
            ts = s.video_timestamps[s.current_video_frame_index]
            frame_data = s.video_data.get(ts)

            if frame_data and len(frame_data) == len(s.pixels):
                act = getactivity()
                if act and not act.expired:
                     try:
                         with act.context:
                            for i, color in enumerate(frame_data):
                                s.pixels[i].set(color)
                     except Exception as e:
                         print(f"BSMScreen Error updating pixels for frame {ts}: {e}")
                         print_exc()
                         s._stop_video_playback()
                         return
                else:
                    print(f"BSMScreen Error: Activity expired during video playback.")
                    s._stop_video_playback()
                    return

                s.current_video_frame_index += 1

                if s.current_video_frame_index < len(s.video_timestamps):
                    next_ts = s.video_timestamps[s.current_video_frame_index]
                    delay = next_ts - ts
                    if delay < 0:
                         print(f"BSMScreen Warning: Negative video frame delay ({delay}), using 0.")
                         delay = 0

                    actual_delay = delay / s.video_playback_speed
                    if actual_delay < 0: actual_delay = 0

                    s.video_play_timer = tick(actual_delay, Call(s._play_next_video_frame))
                else:
                    print("BSMScreen: Video playback complete.")
                    if s.video_loop:
                        print("BSMScreen: Looping video.")
                        s.current_video_frame_index = 0
                        s._start_video_playback()
                    else:
                        s._stop_video_playback()

            else:
                print(f"BSMScreen Error: Frame data for timestamp {ts} invalid or size mismatch.")
                s._stop_video_playback()
        else:
             print("BSMScreen Warning: _play_next_video_frame called with invalid index.")
             s._stop_video_playback()


    def delete(s) -> None:
        """Cleans up the Screen instance and its pixel nodes."""
        print("BSMScreen: Delete called.")
        s._stop_video_playback()
        if s.pixels:
            for pix in s.pixels:
                if pix: pix.delete()
            s.pixels.clear()
        s.media = None
        s.video_data = None
        s.video_timestamps = None
        s.video_play_timer = None


def calc(p, t_res = None):
    """
    Loads and processes a PPM image file, optionally resizing it.

    Reads a PPM (Portable Pixmap, P6 binary format) file from the specified
    path (relative to ROOT()), extracts pixel data, and optionally resizes
    it to a target resolution using nearest-neighbor sampling.

    Args:
        p: The path to the PPM file (relative to ROOT()).
        t_res: An optional tuple (target_width, target_height) for resizing.
               If None, the original image resolution is used.

    Returns:
        A list of (r, g, b) color tuples representing the pixel data,
        or None if loading or processing failed. The list is ordered
        row by row, from bottom-left to top-right, matching the
        Screen's pixel layout.
    """
    p_full = join(ROOT(), p)
    ow, oh = 0, 0

    try:
        with open(p_full, 'rb') as f:
            magic = f.readline().strip()
            if magic != b'P6':
                print(f"BSMCalc Error: Bad magic {magic}")
                return None

            mv = None
            while ow == 0 or oh == 0 or mv is None:
                line = f.readline().strip()
                if not line or len(line) > 100:
                     print("BSMCalc Error: Bad header.")
                     return None
                if line.startswith(b'#'): continue

                parts = line.split()
                if ow == 0 and len(parts) >= 2:
                    try:
                        ow, oh = int(parts[0].decode('ascii')), int(parts[1].decode('ascii'))
                        if len(parts) >= 3:
                            mv = int(parts[2].decode('ascii'))
                    except ValueError:
                        print("BSMCalc Error: Bad dims/max.")
                        return None
                elif mv is None and len(parts) >= 1:
                     try:
                         mv = int(parts[0].decode('ascii'))
                     except ValueError:
                         print("BSMCalc Error: Bad max val.")
                         return None

            if ow <= 0 or oh <= 0 or mv is None:
                 print(f"BSMCalc Error: No dims/max {ow}x{oh} {mv}.")
                 return None

            if mv <= 0 or mv > 255:
                 print(f"BSMCalc Warning: Max val {mv}, expected 255. Normalizing.")

            exp_size = ow * oh * 3
            r = f.read(exp_size)
            if len(r) != exp_size:
                print(f"BSMCalc Error: Bad data size. Exp {exp_size}, got {len(r)}.")
                return None

    except FileNotFoundError:
        print(f"BSMCalc Error: File not found {p_full}")
        return None
    except Exception as e:
        print(f"BSMCalc Error reading {p_full}: {e}")
        return None

    if t_res is None:
        tw, th = ow, oh
    else:
        tw, th = t_res
        if tw <= 0 or th <= 0:
            print(f"BSMCalc Error: Bad target res {t_res}")
            return None

    pa = [None] * (tw * th)
    xsf = ow / tw
    ysf = oh / th

    for ty in range(th):
        for tx in range(tw):
            ox = min(ow - 1, floor(tx * xsf))
            oy_raw = floor(ty * ysf)
            oy = min(oh - 1, max(0, oh - 1 - oy_raw))

            pix_idx = (oy * ow + ox) * 3
            r_b, g_b, b_b = r[pix_idx], r[pix_idx + 1], r[pix_idx + 2]

            r_n = r_b / mv if mv > 0 else 0.0
            g_n = g_b / mv if mv > 0 else 0.0
            b_n = b_b / mv if mv > 0 else 0.0

            arr_idx = ty * th + tx

            pa[arr_idx] = (r_n, g_n, b_n)

    return pa
