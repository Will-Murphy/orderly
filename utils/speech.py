import io
import subprocess

import pyttsx3
import speech_recognition as sr
from gtts import gTTS

from models.api import ApiVoices

recognizer = sr.Recognizer()
microphone = sr.Microphone()


def adjust_for_ambient_noise():
    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)


async def adjust_for_ambient_noise_async():
    adjust_for_ambient_noise()


def listen(logger) -> str:
    with microphone as source:
        logger.debug("Listening for input...")
        audio_text = recognizer.listen(source)
        # recoginize_() method will throw a request error if the API is unreachable, hence using exception handling

        response = None
        try:
            response = recognizer.recognize_google(audio_text)
            # using google speech recognition
            logger.debug(f"Your input was: {response}")
        except Exception as e:
            logger.debug("Sorry, I did not get that")

    return response


def speak(text: str, filename: str = "order_playback.mp3"):
    # Language in which you want to convert
    language = "en"

    # Passing the text and language to the engine,
    # here we have marked slow=False. Which tells
    # the module that the converted audio should
    # have a high speed
    myobj = gTTS(text=text, lang=language, slow=False)

    # Saving the converted audio in a mp3 file named
    # welcome

    myobj.save(filename)

    # Playing the converted file
    subprocess.call(["afplay", filename])


def speak_new(
    client,
    text: str,
    filename: str = "order_playback.mp3",
    voice_selection=ApiVoices.ONYX.value,
    blocking=True,
):
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice_selection,
        input=text,
        speed=1.4
    )

    response.stream_to_file(filename)

    # Playing the converted file
    if blocking:
        play_mp3(filename)
    else:
        play_mp3_non_blocking(filename)


def play_mp3_non_blocking(file_path):
    # Using 'ffplay' as an example. Replace with your preferred player command
    return subprocess.Popen(["afplay", file_path])


def play_mp3(file_path):
    # Using 'ffplay' as an example. Replace with your preferred player command
    return subprocess.call(["afplay", file_path])


def play_background_music():
    return play_mp3_non_blocking("assets/catchy_background.mp3")
