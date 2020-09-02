#!/bin/bash
kill -9 $(ps aux | grep -w "[b]ot_loop3.py" | awk '{print $2}')
kill -15 $(ps aux | grep -w "[m]ain_d3.py" | awk '{print $2}')
echo "Stopped"

out=/home/kiki/botNew/DiscordBot3/tmp/bot_loop.log
echo "-----Restarted at: "$(date '+%Y-%m-%d_%H:%M:%S')"-----" >> ${out}
nohup python3.7 -u /home/kiki/botNew/DiscordBot3/bot_loop3.py >> ${out} &