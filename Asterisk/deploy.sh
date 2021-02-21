#!/bin/bash
if [ "$EUID" -ne 0 ];
  then echo "Please run as root"
  exit
fi
service asterisk stop
killall python3 2>/dev/null
killall tshark 2>/dev/null
cp extensions.conf my_asterisk_dir
cp pjsip.conf my_asterisk_dir
cp ../../agi-gateway.py my_asterisk_agi_dir
cp ../../AsteriskTheSpammers.py my_asterisk_agi_dir
chmod -R 775 my_asterisk_agi_dir
chmod u+x my_asterisk_agi_dir/*.py
cp -r ../../my_config_file my_asterisk_agi_dir/config.txt
mkdir -p my_audio_out_directory
cp -r ../Media/* my_audio_out_directory
nohup python3 my_asterisk_agi_dir/AsteriskTheSpammers.py my_asterisk_agi_dir/config.txt &
touch my_pcapfile
nohup tshark -l -i my_ethernet_interface -f "udp port 5060" -w my_pcapfile &
usermod -a -G asterisk root
chmod -R ug+rw /var/spool/asterisk
service asterisk start

