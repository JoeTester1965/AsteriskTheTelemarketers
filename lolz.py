#!/usr/bin/python3

from asterisk.agi import *
import socket

HOST = '127.0.0.1'  
PORT = 65432        

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

agi.set_variable('FILE', response)
