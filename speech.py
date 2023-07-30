import subprocess
import pyttsx3
import speech_recognition as sr
from gtts import gTTS




def listen(logger) -> str:
    r = sr.Recognizer()

    with sr.Microphone() as source:
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
        
        

    
