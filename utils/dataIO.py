import os
import datetime
import json


def appendToFile(fileName, *args):
    """Formats used:
       [guildid]_joinlog: userID, msgID, timestamp
       newUserCounter: userID, guildID, timestamp
       canJoin, canJoinSooner: userID, guildID, timestamp"""
    with open(fileName, 'a+') as f:
        [f.write(str(l) + '\n') for l in args]
        f.write(str(int(datetime.datetime.now().timestamp())) + '\n')


def reverseListby(arr, by):
    ret = []
    for i in range(len(arr)):
        ret.extend(arr[::-1][by * i:by * (i + 1):][::-1])
        if (by * (i + 1)) == len(arr): break
    return ret


def getFileContentReverse(fileName, by=3):
    if os.path.exists(fileName):
        lines = [line.rstrip('\n') for line in open(fileName)]
        a = reverseListby(lines, by)
        return a
    return None


def getFileContent(fileName):
    if os.path.exists(fileName):
        lines = [line.rstrip('\n') for line in open(fileName)]
        return lines
    return None


def writeContentToFile(fileName, arr, reverse=True):
    if reverse: arr = reverseListby(arr, 3)
    with open(fileName, 'w+') as f:
        [f.write(str(l) + '\n') for l in arr]


def writeObjToJsonfile(obj, filePath):
    if not os.path.exists(filePath): open(filePath, 'w').close()
    with open(filePath, 'w') as f:
        json.dump(obj, f, indent=4)


def readJsonFileToObj(filePath):
    with open(filePath) as f:
        return json.load(f)
