from google.cloud import texttospeech
from google.cloud import speech
from google.oauth2 import service_account
from google.cloud import storage
import grpc
import io
import sys
import platform
import os
import time
import re
from random import randint
import socket
import configparser

file_sequence=1
AUDIO_IN_BYTES_MeStopSpeak=0
incoming_audio_filename=""
my_outgoing_audio_transcription_file=""

if len(sys.argv) != 2:
    print("I need config file location as first paramater in command line")
    sys.exit(1)


on_deployment_platform = platform.system().startswith('Linux')

my_config_label = "AsteriskTheSpammers"

config = configparser.ConfigParser()
config.read(sys.argv[1])

my_incoming_audio_match = config[my_config_label]["my_incoming_audio_match"]
my_credentials_file_path = config[my_config_label]["my_credentials_file_path"]
my_logfile = config[my_config_label]["my_logfile"]
my_outgoing_audio_transcription_file = config[my_config_label]["my_outgoing_audio_transcription_file"]
my_audio_out_directory = config[my_config_label]["my_audio_out_directory"]

my_logfile = open(my_logfile, 'w')

def lock_onto_incoming_audio_file():
    if on_deployment_platform: 
        command_line = "ls -t " + my_incoming_audio_match + " | head -1 > tmp"
        os.system(command_line)
        lockon_filename = open('tmp', 'r').read().strip()
    else:
        lockon_filename = my_incoming_audio_match
    return lockon_filename

def log_message(string):
    string=string+"\n"
    my_logfile.write(string)
    my_logfile.flush()
    print(string)

def transcribe_audio(speech_file): 

    retval = ""
    
    transcription_client = speech.SpeechClient.from_service_account_file(my_credentials_file_path)

    with io.open(speech_file, "rb") as audio_file:
        content = audio_file.read()

    audio = speech.RecognitionAudio(content=content)

    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=8000,
        language_code="en-GB",
    )

    response = transcription_client.recognize(config=config, audio=audio)

    for result in response.results:
        retval = result.alternatives[0].transcript
  
    return retval

def process_NewCall():
    global file_sequence
    file_sequence=1
    global AUDIO_IN_BYTES_MeStopSpeak
    AUDIO_IN_BYTES_MeStopSpeak=0
    log_message("Next file to be played in sequence is " + str(file_sequence))
    return("1") # File "1" is hello


def process_MeStopSpeak():

    incoming_audio_file = lock_onto_incoming_audio_file()
    
    bytes = str(os.stat(incoming_audio_file).st_size)

    global AUDIO_IN_BYTES_MeStopSpeak
    if bytes:
        AUDIO_IN_BYTES_MeStopSpeak = bytes
    else:
        AUDIO_IN_BYTES_MeStopSpeak = 0
        
    return(str(file_sequence)) 

def create_temp_audio_file(bytes_to_process):
    
    if (bytes_to_process % 2) != 0:
        bytes_to_process = bytes_to_process + 1
    
    start_of_header =b"\x52\x49\x46\x46\x00\x00\x00\x00\x57\x41\x56\x45\x66\x6D\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x40\x1F\x00\x00\x80\x3E\x00\x00\x02\x00\x10\x00\x64\x61\x74\x61"
 
    end_of_header = (bytes_to_process).to_bytes(4,'little') 

    wav_header = start_of_header + end_of_header

    incoming_audio_file = lock_onto_incoming_audio_file()

    if not on_deployment_platform: 
        # do not have a growing real time audio file, transcribe it all 
        bytes_to_process = os.stat(incoming_audio_file).st_size

    # could wait to catch up, but
    if bytes_to_process > os.stat(incoming_audio_file).st_size:
        bytes_to_process = os.stat(incoming_audio_file).st_size

    global my_outgoing_audio_transcription_file

    with open(incoming_audio_file,'rb') as f1:
        with open(my_outgoing_audio_transcription_file,'wb') as f2:
            f1.seek(-1 * bytes_to_process, os.SEEK_END) 
            f2.write(wav_header)
            while True:
                buf=f1.read(16*1024)
                if buf: 
                    n=f2.write(buf)
                else:
                    break
    return True

def do_stuff_based_on_transcription(transcription_text):
    
    global my_audio_out_directory

    retval = ""

    if transcription_text.find("press") > -1:
        if any(re.findall(r'0|1|2|3|4|5|6|7|8|9|zero|one|two|three|four|five|six|seven|eight|nine', transcription_text, re.IGNORECASE)):
            # could evaluate these properly, but 1 will do the job most times when they call you with a menu
            retval = "DTMF/1"
            log_message("Next file to be played overriding sequence is " + retval )

    elif any(re.findall(r'stupid|whatever', transcription_text, re.IGNORECASE)):
        audo_out_file = my_audio_out_directory + "echo.mp3"
        if transcription_text:
            write_transcription_audioFile("Did you really say " + transcription_text + "?", audo_out_file)
            retval = "echo"
            log_message("Next file to be played overriding sequence is " + retval + " at " + audo_out_file)

    elif randint(1,6) == 1: # roll a dice
        audo_out_file = my_audio_out_directory + "echo.mp3"
        if transcription_text:
            write_transcription_audioFile("Did you say " + transcription_text + "?", audo_out_file)
            retval = "echo"
            log_message("Next file to be played overriding sequence is " + retval + " at " + audo_out_file)
    
    return(retval)

def process_TheyStopSpeak():
 
    incoming_audio_file = lock_onto_incoming_audio_file()

    current_audio_in_bytes = os.stat(incoming_audio_file).st_size

    global AUDIO_IN_BYTES_MeStopSpeak
    bytes = current_audio_in_bytes - int(AUDIO_IN_BYTES_MeStopSpeak)

    # GCP limit for local process
    if bytes > 10000000:
       bytes = 10000000

    # Put in sensible limits for cloud processing ~ 30s
    if bytes > 240000:
        bytes = 240000

    global file_sequence
    file_sequence = file_sequence + 1;
    
    if file_sequence > 16:
        file_sequence = 2

    log_message("Next file to be played in sequence is " + str(file_sequence))

    retval=str(file_sequence)

    if incoming_audio_file:
        if create_temp_audio_file(bytes):
            
            transcription_text = transcribe_audio(my_outgoing_audio_transcription_file)     

            if transcription_text:
                log_message("transcription text is : " + transcription_text)
                retval = do_stuff_based_on_transcription(transcription_text)
                if retval:
                    file_sequence = file_sequence - 1; # Put the static script back to where it was
                else:
                    retval=str(file_sequence)

    return(retval)
        

def write_transcription_audioFile(text, filename):

    filename = my_audio_out_directory + filename
    client = texttospeech.TextToSpeechClient.from_service_account_file(my_credentials_file_path)
    synthesis_input = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-IN", name="en-IN-Wavenet-B", ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL)
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3, speaking_rate=0.89)
    response = client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
    with open(filename, "wb") as out:
        out.write(response.audio_content)

def create_static_conversation_files():
    write_transcription_audioFile("Hello!","1.mp3")
    write_transcription_audioFile("Sorry. I cannot hear you. Are you still there?" ,"2.mp3")
    write_transcription_audioFile("Got that.","3.mp3")
    write_transcription_audioFile("Someone did call about the same thing last week, was that you?","4.mp3")
    write_transcription_audioFile("Excuse me but what did you say your name was again?","5.mp3")
    write_transcription_audioFile("It's funny that you should call about this, my neighbour mentioned that yesterday.","6.mp3")
    write_transcription_audioFile("Oh boy! I never knew that was possible." ,"7.mp3")
    write_transcription_audioFile("That does need some consideration." ,"8.mp3")
    write_transcription_audioFile("Could you say that again, please?" ,"9.mp3")
    write_transcription_audioFile("Oh! I see! That sounds fine.","10.mp3")
    write_transcription_audioFile("Sorry which company did you say that you were calling from?","11.mp3")
    write_transcription_audioFile("The last time someone called up and spoke to me about that, something came on the telly and I had to hang up.","12.mp3")
    write_transcription_audioFile("Since you put it that way, please do carry on.", "13.mp3")
    write_transcription_audioFile("Well, what with coronavirus and all that, we all need more patience and understanding.", "14.mp3")
    write_transcription_audioFile("That does sound great, what needs to happen next?" ,"15.mp3")
    write_transcription_audioFile("Sorry I am a bit confused can you say that again?","16.mp3")


#create_static_conversation_files() # remake static files if neccecary

log_message("AsteriskTheSpammers started")

HOST = '127.0.0.1'  
PORT = 65432 

while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
        with conn:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                state = data.decode('ascii')
                if state:
                    log_message("AsteriskTheSpammers called with : " + state)
                    
                    retval = str(file_sequence)
                    
                    if state.find("NewCall") > -1:
                        retval = process_NewCall() 
                    elif state.find("MeStopSpeak") > -1:
                       retval = process_MeStopSpeak()
                    elif state.find("TheyStopSpeak") > -1:
                        retval = process_TheyStopSpeak()
                    
                    conn.sendall(retval.encode('ascii'))































































