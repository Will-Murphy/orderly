from functools import wraps

import simpleaudio as sa
from pydub import AudioSegment

# TODO: fix to add buffer music for better interaction waiting
# Load the audio file
audio = []  # AudioSegment.from_mp3("./assests/catchy_background.mp3")
audio_data = None  # audio.raw_data

# Global variables to keep track of playback
play_obj = None
playback_position = 0
audio_length = len(audio)


def play_music():
    global play_obj, playback_position
    play_obj = sa.play_buffer(
        audio_data[playback_position:],
        num_channels=audio.channels,
        bytes_per_sample=audio.sample_width,
        sample_rate=audio.frame_rate,
    )


def stop_music():
    global play_obj, playback_position
    playback_position += play_obj.frames_played * audio.sample_width * audio.channels
    play_obj.stop()

    # Restart from the beginning if audio has finished
    if playback_position >= audio_length:
        playback_position = 0


def play_music_decorator(func):
    wraps(func)

    def wrapper(*args, **kwargs):
        play_music()
        result = func(*args, **kwargs)
        stop_music()
        return result

    return wrapper
