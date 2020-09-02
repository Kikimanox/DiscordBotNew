#!/bin/bash
out=/home/kiki/botNew/DiscordBotNew/tmp/bot_loop.log
echo "-----Restarted at: "$(date '+%Y-%m-%d_%H:%M:%S')"-----" >> ${out}
nohup python3.7 -u /home/kiki/botNew/DiscordBotNew/bot_loop3.py >> ${out} &