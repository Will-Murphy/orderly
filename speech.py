import subprocess
import pyttsx3
import speech_recognition as sr
from gtts import gTTS
import io




def listen(logger) -> str:
    r = sr.Recognizer()

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        audio_text = r.listen(source)
        # recoginize_() method will throw a request error if the API is unreachable, hence using exception handling

        response = None
        try:
            response = r.recognize_google(audio_text)
            # using google speech recognition
            logger.debug(f"Your input was: {response}")
        except Exception as e:
            logger.debug("Sorry, I did not get that")

    return response

def listen_new(client, logger, prompt=None)-> str:
    r = sr.Recognizer()

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        audio_text = r.listen(source)
        audio_bytes_io = io.BytesIO(audio_text.get_wav_data())
        audio_bytes_io.seek(0)
        
        audio_fname = "microphone_input.wav"
        with open(audio_fname, "wb") as file:
            file.write(audio_bytes_io.read())

        transcript = None
        try:
            audio_file = open(audio_fname, "rb")
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                prompt=prompt,
                response_format="text"
            )
            logger.debug(f"Your input was: {transcript}")
        except Exception as e:
            logger.debug("Listening failed with error: " + str(e))
            logger.info("Sorry, I did not get that")

    return transcript




def speak(text: str, filename: str = 'order_playback.mp3'):
    # Language in which you want to convert
    language = 'en'
    
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
    
    
def speak_new(client, text: str, filename: str = 'order_playback.mp3'):
    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text,
    )
    
    response.stream_to_file(filename)
    
    # Playing the converted file
    subprocess.call(["afplay", filename])

    
