import datetime
import time
import subprocess
import os
import sys
from subprocess import PIPE, Popen


while True:
    if os.path.exists('quit.txt'):
        os.remove('quit.txt')
        print(f'Quitted on: ---{datetime.datetime.now().strftime("%c")}---')
        break
    #params = [sys.executable, 'main_d3.py']
    #params.extend(sys.argv[1:])
    #subprocess.call(params)
    if str(os.system("$(ps aux | grep -w '[m]ain_d3.py' | awk '{print $2}') 2> /dev/null")) == "0":
        os.system('nohup python3.7 -u main_d3.py >> tmp/output.log &')
    else:
        time.sleep(0.5)
