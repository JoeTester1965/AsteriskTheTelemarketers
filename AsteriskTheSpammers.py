#!/usr/bin/python3

from google.cloud import texttospeech
from google.cloud import speech
from google.oauth2 import service_account
import grpc
import io
import sys
import numpy
import platform
import os
import time
from datetime import datetime
import re
from random import randint
import socket
import configparser
import subprocess
import logging

file_sequence=1
have_asked_areyoustillthere=False
timer_start=0

if len(sys.argv) != 2:
	print("I need config file location as first paramater in command line")
	sys.exit(1)

test =  platform.system()
on_debug_platform = platform.system().startswith('Windows')

if on_debug_platform:
	import pyaudio
	audio  = pyaudio.PyAudio()

my_config_label = "AsteriskTheSpammers"

config = configparser.ConfigParser()
config.read(sys.argv[1])

my_incoming_audio_match = config[my_config_label]["my_incoming_audio_match"]
my_credentials_file_path = config[my_config_label]["my_credentials_file_path"]
my_logfile = config[my_config_label]["my_logfile"]
my_outgoing_audio_transcription_file = config[my_config_label]["my_outgoing_audio_transcription_file"]
my_audio_out_directory = config[my_config_label]["my_audio_out_directory"]
hello_file = config[my_config_label]["hello_file"]
areyoustillthere_file = config[my_config_label]["areyoustillthere_file"]
audio_average_absolute_power_threshold_int16 = int(config[my_config_label]["audio_average_absolute_power_threshold_int16"])
waittheyspeak_timeout_bytes = int(config[my_config_label]["waittheyspeak_timeout_bytes"])
files_in_file_sequence = int(config[my_config_label]["files_in_file_sequence"]) 
theystopppedspeaking_timeout_bytes = int(config[my_config_label]["theystopppedspeaking_timeout_bytes"])
audio_read_granularity = int(config[my_config_label]["audio_read_granularity"])
available_context_leeway = int(config[my_config_label]["available_context_leeway"])
asynch_sleep_seconds = float(config[my_config_label]["asynch_sleep_seconds"])
timeout_seconds_no_data_read_from_file = float(config[my_config_label]["timeout_seconds_no_data_read_from_file"])
cloud_processing_audio_file_size_limit = int(config[my_config_label]["cloud_processing_audio_file_size_limit"])
host_address = config[my_config_label]["host_address"]
port_number = int(config[my_config_label]["port_number"])

logging.basicConfig(    handlers=[
                                logging.FileHandler(my_logfile),
                                logging.StreamHandler()],
                        format='%(asctime)s,%(msecs)d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                        datefmt='%Y-%m-%d:%H:%M:%S',
                        level=logging.DEBUG)

logger = logging.getLogger(__name__)

def lock_onto_incoming_audio_file():
	if on_debug_platform: 
		lockon_filename = my_incoming_audio_match
	else:
		command_line = "ls -t " + my_incoming_audio_match + " | head -1 > tmp"
		os.system(command_line)
		lockon_filename = open('tmp', 'r').read().strip()
	return lockon_filename

def transcribe_audio(speech_file): 

	retval = ""
	
	try:
		transcription_client = speech.SpeechClient.from_service_account_file(my_credentials_file_path)
	except:
		logger.info("Not using Google speech to text as credz file not at : " + my_credentials_file_path)
		return ""

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

def test_is_audio_activity(buffer, threshold):
   
	retval = False
	
	audio_bytes = numpy.frombuffer(buffer, dtype=numpy.int16)
	average_absolute_power = numpy.sum(numpy.absolute(audio_bytes)) / audio_bytes.size
	logger.debug("average_absolute_power : " + str(average_absolute_power))
	
	if (average_absolute_power > threshold):
		retval = True

	return retval

def process_WaitTheySpeak():

	global audio_average_absolute_power_threshold_int16
	global waittheyspeak_timeout_bytes
	global file_sequence
	global files_in_file_sequence
	global theystopppedspeaking_timeout_bytes
	global audio_read_granularity

	incoming_audio_file = lock_onto_incoming_audio_file()

	total_bytes_processed = 0

	if incoming_audio_file == "microphone":
		mic_stream = audio.open(    
			format =  pyaudio.paInt16,
			rate = 8000,
			channels = 1, 
			input_device_index = 1, 
			input = True, 
			frames_per_buffer=audio_read_granularity)
		microphone_file_handle = open("microphone", 'wb')
	else:
		audio_source = open(incoming_audio_file, 'rb')
		audio_source.seek(0, os.SEEK_END)
		
	activity_heard = False	
	
	audio_first_noisy_marker = -1

	total_bytes_processed = 0;

	global have_asked_areyoustillthere
	global timer_start

	timer_start = time.time()
	logger.debug("timer_start set to %s", repr(timer_start))

	while activity_heard == False:
		time.sleep(asynch_sleep_seconds)
		while True:
			try:
				if incoming_audio_file == "microphone":
					buffer = mic_stream.read(audio_read_granularity)
					microphone_file_handle.write(buffer)
					microphone_file_handle.flush()
				else:
					buffer = audio_source.read(audio_read_granularity)

				if buffer:
					if len(buffer) < 1000: # on Target platform can get false triggers on small initial bytes at start of file
						logger.debug("Ignoring %d bytes returned from file read at %s", len(buffer), repr(timer_start))
					else:
						timer_start = time.time()
						logger.debug("%d bytes returned from file read at %s", len(buffer), repr(timer_start))
						break
				else:
					timer_end = time.time()
					timer_delta =  timer_end - timer_start
					if timer_delta > timeout_seconds_no_data_read_from_file:
						logger.info("Call state transitioned to NewCall : No bytes returned from read within timeout - assume handle dead")
						return("ENDCALL")

			except OSError as error:
				logger.error("Call state transitioned to NewCall : os.read error %d", error)
				return("ENDCALL")

		total_bytes_processed = total_bytes_processed + len(buffer)

		activity_heard = test_is_audio_activity(buffer, audio_average_absolute_power_threshold_int16)
	
		if activity_heard:
			if audio_first_noisy_marker == -1:
				audio_first_noisy_marker = os.stat(incoming_audio_file).st_size
				logger.info("*** You started speaking ***")

		if	total_bytes_processed > waittheyspeak_timeout_bytes:
			if have_asked_areyoustillthere:
				have_asked_areyoustillthere = False
				logger.info("Call state transitioned to NewCall")
				return("ENDCALL")
			else:
				have_asked_areyoustillthere = True
				retval="FILE:" + areyoustillthere_file
				total_bytes_processed = 0
				return(retval) 
	
	logger.info("Call state transitioned to TheyAreSpeaking")
	
	audio_last_noisy_marker = audio_first_noisy_marker

	total_bytes_processed = 0
	bytes_activity_heard = 0
	bytes_activity_not_heard = 0

	timer_start = time.time()
	logger.debug("timer_start set to %s", repr(timer_start))

	while activity_heard == True:
		time.sleep(asynch_sleep_seconds)
		while True:
			try:
				if incoming_audio_file == "microphone":
					buffer = mic_stream.read(audio_read_granularity)
					microphone_file_handle.write(buffer)
					microphone_file_handle.flush()
				else:
					buffer = audio_source.read(audio_read_granularity)

				if buffer:
					timer_start = time.time()
					logger.debug("%d bytes returned from file read at %s", len(buffer), repr(timer_start))
					break

				else:
					timer_end = time.time()
					timer_delta =  timer_end - timer_start
					if timer_delta > timeout_seconds_no_data_read_from_file:
						logger.info("Call state transitioned to NewCall : No bytes returned from read within timeout- assume handle dead")
						return("ENDCALL")

			except OSError as error:
					logger.error("Call state transitioned to NewCall : os.read error %d", error)
					return("ENDCALL")
		
		total_bytes_processed = total_bytes_processed + len(buffer)
			
		activity_heard = test_is_audio_activity(buffer, audio_average_absolute_power_threshold_int16)

		if activity_heard:
			bytes_activity_heard = total_bytes_processed
		else:
			bytes_activity_not_heard = total_bytes_processed
			
		if (bytes_activity_not_heard - bytes_activity_heard) < theystopppedspeaking_timeout_bytes:
			activity_heard = True
		else:
			audio_last_noisy_marker = os.stat(incoming_audio_file).st_size
			logger.info("*** You stopped speaking ***")
			activity_heard = False

	speaking_bytes_to_process =  audio_last_noisy_marker - audio_first_noisy_marker

	# Put in sensible limits for cloud processing ~ 30s
	if speaking_bytes_to_process > cloud_processing_audio_file_size_limit:
		speaking_bytes_to_process = cloud_processing_audio_file_size_limit
	
	bytes_in_file = os.stat(incoming_audio_file).st_size

	available_context_leeway = bytes_in_file - speaking_bytes_to_process;

	if available_context_leeway > 32000:
		available_context_leeway = 32000

	rewind_bytes = bytes_in_file - audio_first_noisy_marker + available_context_leeway;

	speaking_bytes_to_process = speaking_bytes_to_process + available_context_leeway;

	if incoming_audio_file == "microphone":
		microphone_file_handle.close()

	temp_file = create_temp_audio_file(incoming_audio_file, rewind_bytes, speaking_bytes_to_process + audio_read_granularity)
	
	transcription_text = transcribe_audio(temp_file)     

	retval = ""
	logger.info("*** Transcription text is : " + transcription_text + " ***")

	if transcription_text:
		retval = do_stuff_based_on_transcription(transcription_text)
	
	if not retval:
		retval="FILE:" + str(file_sequence)
		file_sequence = file_sequence + 1
		if file_sequence > files_in_file_sequence:
			file_sequence = 1
	
	return(retval)

def create_temp_audio_file(incoming_audio_file, offset_from_eof, bytes_to_process):

	if (bytes_to_process % 2) != 0:
		bytes_to_process = bytes_to_process + 1
	
	start_of_header =b"\x52\x49\x46\x46\x00\x00\x00\x00\x57\x41\x56\x45\x66\x6D\x74\x20\x10\x00\x00\x00\x01\x00\x01\x00\x40\x1F\x00\x00\x80\x3E\x00\x00\x02\x00\x10\x00\x64\x61\x74\x61"
	end_of_header = (bytes_to_process).to_bytes(4,'little')
	wav_header = start_of_header + end_of_header	

	global my_outgoing_audio_transcription_file

	f1 = open(incoming_audio_file,'rb')
	f2 = open(my_outgoing_audio_transcription_file,'wb')
	f1.seek(-1 * offset_from_eof, os.SEEK_END) 
	f2.write(wav_header)
	buf=f1.read(bytes_to_process)
	f2.write(buf)
	f1.close()
	f2.flush()
	f2.close()

	return my_outgoing_audio_transcription_file


def do_stuff_based_on_transcription(transcription_text):
	
	DTMFFiles = {	
				"zero" : "FILE:DTMF/0",
				"one" : "FILE:DTMF/1",
				"two" : "FILE:DTMF/2",
				"three" : "FILE:DTMF/3",
				"four" : "FILE:DTMF/4",
				"five" : "FILE:DTMF/5",
				"six" : "FILE:DTMF/6",
				"seven" : "FILE:DTMF/7",
				"eight" : "FILE:DTMF/8",
				"nine" : "FILE:DTMF/9",
				"star" : "FILE:DTMF/10",
				"hash" : "FILE:DTMF/11",
				"pound" : "FILE:DTMF/11"
			}

	if transcription_text.find("press") > -1:
		for key, value in DTMFFiles.items(): 
			if transcription_text.find(key) > -1:
				retval = value
				return(retval)

	elif any(re.findall(r'stupid|whatever', transcription_text, re.IGNORECASE)):
		audo_out_file = "echo.mp3"
		if transcription_text:
			write_transcription_audioFile("Did you really say " + transcription_text + "?", audo_out_file)
			retval = "FILE:echo"
			return(retval)

	elif randint(1,6) == 1: # roll a dice
		audo_out_file = "echo.mp3"
		if transcription_text:
			write_transcription_audioFile("Did you say " + transcription_text + "?", audo_out_file)
			retval = "FILE:echo"
			return(retval)
	
	return

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
	write_transcription_audioFile("Hello!","hello.mp3")
	write_transcription_audioFile("Sorry. I cannot hear you. Are you still there?" ,"areyoustillthere.mp3")
	write_transcription_audioFile("My, that sounds most interesting.","1.mp3")
	write_transcription_audioFile("Someone did call about the same thing last week, was that you?","2.mp3")
	write_transcription_audioFile("Excuse me but what did you say your name was again?","3.mp3")
	write_transcription_audioFile("It's funny that you should call about this, my neighbour mentioned that yesterday.","4.mp3")
	write_transcription_audioFile("Oh boy! I never knew that was possible." ,"5.mp3")
	write_transcription_audioFile("That does need some consideration." ,"6.mp3")
	write_transcription_audioFile("Could you say that again, please?" ,"7.mp3")
	write_transcription_audioFile("Oh! I see! That sounds fine.","8.mp3")
	write_transcription_audioFile("Sorry which company did you say that you were calling from?","9.mp3")
	write_transcription_audioFile("The last time someone called up and spoke to me about that, something came on the telly and I had to hang up.","10.mp3")
	write_transcription_audioFile("Since you put it that way, please do carry on.", "11.mp3")
	write_transcription_audioFile("Well, what with coronavirus and all that, we all need more patience and understanding.", "12.mp3")
	write_transcription_audioFile("That does sound great, what needs to happen next?" ,"13.mp3")
	write_transcription_audioFile("Sorry I am a bit confused can you say that again?","14.mp3")

#create_static_conversation_files() # remake static files if neccecary

logger.info("AsteriskTheSpammers started")

HOST = host_address  
PORT = port_number 

if on_debug_platform:
	subprocess.Popen('"C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python37_86\python.exe" stub-client.py')

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
				agi_message = data.decode('ascii')

				if agi_message:
					logger.info("AsteriskTheSpammers called with : " + agi_message)
					
					if agi_message.find("NewCall") > -1:
			
						file_sequence=1
						retval = "FILE:" + hello_file
						logger.info("Message for AGI is: " + retval)
						conn.sendall(retval.encode('ascii'))

					if agi_message.find("MeStopSpeak") > -1:
						
						retval = process_WaitTheySpeak()			
						logger.info("Message for AGI is: " + retval)
						conn.sendall(retval.encode('ascii'))
					
