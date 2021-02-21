#!/usr/bin/python3

from asterisk.agi import *
import socket
import platform

HOST = '127.0.0.1'  
PORT = 65432        

linux_platform = platform.system().startswith('Linux')

if linux_platform:
	agi = AGI()

def send_message_and_get_response(message):
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.connect((HOST, PORT))
		s.sendall(message)
		data = s.recv(1024)
	decoded_message = data.decode('ascii')
	return(decoded_message)

request = sys.argv[1].encode('ascii') 
response = send_message_and_get_response(request)

if linux_platform:
	if response.startswith("ENDCALL"):
		agi.hangup()

	if response.startswith("FILE:"):
		filename=response.split(":")[1]
		agi.set_variable('FILE', filename)