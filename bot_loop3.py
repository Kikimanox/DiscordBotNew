import os
import datetime
import time

os.system('nohup python3.7 -u main_d3.py >> tmp/output.log &')
while True:
    if os.path.exists('quit.txt'):
        os.remove('quit.txt')
        os.system("kill $(ps aux | grep -w '[m]ain_d3.py' | awk '{print $2}')")
        # os.system('nohup python3.7 -u main_d3.py >> tmp/output.log &')
        print(f'Quitted on: ---{datetime.datetime.now().strftime("%c")}---')
        break
    time.sleep(0.1)
