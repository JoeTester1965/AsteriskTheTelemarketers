#!/usr/bin/python3

import configparser
import fileinput
from shutil import copyfile
import os
import sys

config = configparser.ConfigParser()

if len(sys.argv) != 2:
	print("I need config file location as first paramater in command line")
	sys.exit(1)
	
config_file=sys.argv[1]

config.read(config_file)

list = config.items("Asterisk")

files_to_parse = ["extensions.conf", "pjsip.conf", "deploy.sh", "sipmononitor.service", "asteriskthespammers.service"]

try:
	os.mkdir('Asterisk/deploy')
except:
	pass

for filename in files_to_parse:
	source_filename = "Asterisk/" + filename
	dest_filename = "Asterisk/deploy/" + filename
	copyfile(source_filename, dest_filename)
	
	for element in list:
		key = element[0]
		value = element[1]
		with fileinput.FileInput(dest_filename, inplace=True, backup='.bak') as file:
			for line in file:
				print(line.replace(key, value), end='')

	key="my_config_file"
	value=config_file
	
	with fileinput.FileInput(dest_filename, inplace=True) as file:
		for line in file:
			print(line.replace(key, value), end='')

	key="my_external_ip_address"
	command_line = "dig +short myip.opendns.com @resolver1.opendns.com > tmp"
	os.system(command_line)
	value = open('tmp', 'r').read().strip()

	with fileinput.FileInput(dest_filename, inplace=True) as file:
		for line in file:
			print(line.replace(key, value), end='')