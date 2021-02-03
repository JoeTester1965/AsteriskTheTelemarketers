#!/bin/sh
if [ "$EUID" -ne 0 ];
  then echo "Please run as root"
  exit
fi
cp extensions.conf my_asterisk_dir
cp pjsip.conf my_asterisk_dir
cp ../../lolz.py my_asterisk_agi_dir
cp ../../AsteriskTheSpammers.py my_asterisk_agi_dir
chmod -R 775 my_asterisk_agi_dir
chmod u+x my_asterisk_agi_dir/*.py
cp -r ../../my_config_file my_asterisk_agi_dir/config.txt
mkdir -p my_audio_out_directory
cp -r ../Media/* my_audio_out_directory
killall python3 2>/dev/null
nohup python3 my_asterisk_agi_dir/AsteriskTheSpammers.py my_asterisk_agi_dir/config.txt &
service asterisk stop
service asterisk start
