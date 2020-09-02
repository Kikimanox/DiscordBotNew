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
    params = [sys.executable, 'main_d3.py']
    # params.extend(sys.argv[1:])
    # subprocess.call(params,)
    o, e = subprocess.Popen(['python3.7', 'main_d3.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE).communicate()
    print(o)
    print(e)
