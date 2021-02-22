import socket
import time

HOST = '127.0.0.1'  
PORT = 65432        

def send_message_and_get_response(message):
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
		s.connect((HOST, PORT))
		s.sendall(message)
		data = s.recv(1024)
	decoded_message = data.decode('ascii')
	return(decoded_message)

time.sleep(1)
send_message_and_get_response(b'NewCall')

while True:
	time.sleep(1)
	send_message_and_get_response(b'MeStopSpeak')
