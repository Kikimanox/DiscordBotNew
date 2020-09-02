#!/bin/bash
out=/home/kiki/botNew/DiscordBot3/tmp/bot_nohup.log
out2=/home/kiki/botNew/DiscordBot3/tmp/loop_log.log
echo "-----Started at: "$(date '+%Y-%m-%d_%H:%M:%S')"-----" >> ${out}
nohup python3.7 -u /home/kiki/botNew/DiscordBot3/main_d3.py >> ${out} &
echo "-----Started at: "$(date '+%Y-%m-%d_%H:%M:%S')"-----" >> ${out2}
nohup python3.7 -u /home/kiki/botNew/DiscordBot3/bot_loop3.py >> ${out2} &