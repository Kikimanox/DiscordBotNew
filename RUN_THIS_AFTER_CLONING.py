import os
import sys
import shutil
import fileinput
# from utils.dataIOa import dataIOa

for d in ['data', '_scripts', 'tmp', 'logs', 'logs/error', 'logs/info', 'logs/workers']:
    try:
        os.makedirs(d)
    except FileExistsError:
        pass

if not os.path.exists('env.py'):
    print('env.py doesn\'t exist, creating...')
    shutil.copy('env.template', 'env.py')
    print('env.py created, please check the file env.py and '
          'fill in the appropriate fields in!!!!! (DO NOT FORGET TO DO THIS)')

skipRenaming = input('For different bot instances, please rename '
                     'the following files, to skip this write "skip", to continue press enter:')
if not skipRenaming and not str(skipRenaming).lower().strip() == 'skip':
    print('Make sure the file names you will enter will not be '
          '"bot_loop3.py", "main_d3.py" or any other variation you have already used, aka. make them UNIQUE')
    b_l = input('Enter the new name for the bot_loop3.py file (example: "the_loop.py"): ')
    m_d = input('Enter the new name for the main_d3.py file (example: "othermain.py"): ')
    with fileinput.FileInput('scripts/stop.sh', inplace=True, backup='.bak') as file:
        for line in file:
            print(line.replace('[m]ain_d3.py', f'[{m_d[:1]}]{m_d[1:]}'), end='')
    with fileinput.FileInput('scripts/stop.sh', inplace=True, backup='.bak') as file:
        for line in file:
            print(line.replace('[b]ot_loop3.py', f'[{b_l[:1]}]{b_l[1:]}'), end='')
    with fileinput.FileInput('bot_loop3.py', inplace=True, backup='.bak') as file:
        for line in file:
            print(line.replace('main_d3.py', m_d), end='')
    with fileinput.FileInput('bot_loop3.py', inplace=True, backup='.bak') as file:
        for line in file:
            print(line.replace('[m]ain_d3.py', f'[{m_d[:1]}]{m_d[1:]}'), end='')
    with fileinput.FileInput('scripts/start.sh', inplace=True, backup='.bak') as file:
        for line in file:
            print(line.replace('bot_loop3.py', b_l), end='')

    os.rename('main_d3.py', f'{m_d}')
    os.rename('bot_loop3.py', f'{b_l}')

    shutil.copy('env.py', 'env.py.bak')
    remove_lines = ['NEW_MAIN_D', 'NEW_BOT_LOOP']
    with open('env.py.bak') as oldfile, open('env.py', 'w') as newfile:
        for line in oldfile:
            if not any(bad_line in line for bad_line in remove_lines):
                newfile.write(line)
        newfile.write(f"NEW_MAIN_D = '{m_d}'\nNEW_BOT_LOOP = '{b_l}'")

    with open('scripts/start.sh', 'w') as f:
        f.write('#!/bin/bash\n')
        f.write(f'out={os.path.abspath(".")}/tmp/bot_loop.log\n')
        f.write('echo "-----Started at: "$(date \'+%Y-%m-%d_%H:%M:%S\')"-----" >> ${out}\n')
        f.write(f'nohup python3.7 -u {os.path.abspath(b_l)} >> ' + '${out} 2>&1 &\n')
        f.write(f'echo "Bot started"')


# serverDataFile = 'data/servers_data_ids.json'
# if not os.path.exists(serverDataFile):
#     with open(serverDataFile, 'w') as f: pass
#     template_data = {"123412341234": {"guild": "enter the guild name here",
#                                       "welcomeCh": "123412341234",
#                                       "joinLogch": "123412341234",
#                                       "memberRole": "123412341234",
#                                       "gatewayRulesCh": "123412341234",
#                                       "targetChForNewChs": "123412341234",
#                                       "mangaReleaseRole": "123412341234",
#                                       "mangaReleaseUpdatesCh": "123412341234",
#                                       "modLogChannel": "123412341234",
#                                       "mutedRole": "Can be setup later too",
#                                       "modRoles": ["123412341234", "123412341233"]
#                                       }}
#     dataIOa.save_json(serverDataFile, template_data)
#     print('Server data file created in data/servers_data_ids.json. Please edit those appropriately')


print('\nCheck in case you don\'t or can\'t use the "python3.7" command for '
      'running programs, change that in "bot_loop3.py" and "newstart.sh"')
print('\nEverything else seems okay, the setup has been complete')

test = os.listdir('.')
for item in test:
    if item.endswith(".bak"):
        os.remove(item)

