#!/bin/bash
out=/home/kiki/botNew/DiscordBot3/tmp/bot_loop.log
echo "-----Restarted at: "$(date '+%Y-%m-%d_%H:%M:%S')"-----" >> ${out}
nohup python3.7 -u /home/kiki/botNew/DiscordBot3/bot_loop3.py >> ${out} &