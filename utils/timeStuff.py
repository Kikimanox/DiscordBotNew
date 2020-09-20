import re

import arrow
import datetime
from dateutil.relativedelta import relativedelta
import discord.utils as dutils


class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'


def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'


def convertTimeToReadable1(time):
    dd = arrow.get(time).datetime
    epoch = (dd.replace(tzinfo=None) - datetime.datetime(1970, 1, 1)).total_seconds()
    return str(datetime.datetime.utcfromtimestamp(int(epoch)).strftime('%d/%m/%Y %H:%M:%S'))


# credit to Danny
def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.datetime.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), 'week'))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        if not brief:
            return human_join(output, final='and') + suffix
        else:
            return ' '.join(output) + suffix


def convert_sec_to_smh(sec):
    if sec < 60:
        tim = f'{int(sec)}s'
    elif 3600 > sec >= 60:
        tim = f'{int(sec // 60)}m'
    else:
        tim = f'{int(sec // 3600)}h {int((sec // 60) % 60)}m'
    return tim


def get_regexed_time_from_str_and_possible_err(string):
    try:
        error = ""
        date = None
        ds = tuple(map(int, re.findall(r'\d+', string)))[:6]
        if ds:
            date = datetime.datetime(*ds)
        else:
            error = "Couldn't find any numbers while parsing date."
    except Exception as e:
        date = None
        ee = str(e).replace('@', '@\u200b')
        error = (f"Something went wrong when parsing time. "
                 f"Please check your "
                 f"syntax and semantics. Exception:\n"
                 f"```\n{ee}```")

    return date, error


def try_get_time_from_text(text, timestamp: datetime.datetime, firstPart=""):
    """

    :param text: The text that has time at the end
    :param timestamp: Current timestamp
    :param firstPart: In case the text has some first part that has to be cut out
    :return: mid_part, remind_time, error
    """
    try:
        midPart = ""
        remind_time = timestamp

        idx2 = text.lower().rfind('in')
        idx3 = text.lower().rfind('on')
        idx4 = text.lower().rfind('at')
        idx5 = text.lower().rfind('on')  # on at
        idx6 = text.lower().rfind('at')  # at on
        idx7 = text.lower().rfind('tomorrow')  # tomorrow at
        idx8 = text.lower().rfind('at')  # at.. tomorrow
        #match2 = re.findall(r"(in [0-9]+[smhd][0-9]*[smh]*[0-9]*[sm]*$)", text.lower())
        match2 = re.findall(r"(in .*?$)", text.lower())
        match3 = re.findall(r"(on .*?$)", text.lower())
        match4 = re.findall(r"(at .*?$)", text.lower())
        match5 = re.findall(r"(on .*? at .*?$)", text.lower())
        match6 = re.findall(r"(at .*? on .*?$)", text.lower())
        match7 = re.findall(r"(tomorrow at .*?$)", text.lower())
        match8 = re.findall(r"(at .*?tomorrow$)", text.lower())
        not2 = False
        not3 = False
        not4 = False
        not5 = False
        not6 = False
        not7 = False
        not8 = False
        if idx2 == -1 or not match2: not2 = True
        if idx3 == -1 or not match3: not3 = True
        if idx4 == -1 or not match4: not4 = True
        if idx5 == -1 or not match5: not5 = True
        if idx6 == -1 or not match6: not6 = True
        if idx7 == -1 or not match7: not7 = True
        if idx8 == -1 or not match8: not8 = True
        if not2 and not3 and not4 and not5 and not6 and not7 and not8:
            return None, None, "You forgot the `in../on../at../on..at../at..on../tomorrow at../at.. tomorrow` " \
                               "at the end."

        idx = 0
        if match2: idx = idx2
        if match3: idx = idx3  # on
        if match4: idx = idx4  # at
        if match5: idx = idx5  # on..at..
        if match6: idx = idx6  # at..on..
        if match7: idx = idx7  # tomorrow at..
        if match8: idx = idx8  # at.. tomorrow

        lastPart = text[idx + 3::]
        midPart = text[len(firstPart) + 1:idx - 1]

        if firstPart and not midPart: return None, None, "You forgot the reminders content."
        if not lastPart: return None, None, "You forgot to set when to set of the reminder."

        if idx == idx2:  # in
            replacements = [
                ['s', 'seconds', 'second', 'secs', 'sec'],
                ['m', 'minutes', 'minte', 'mins', 'min'],
                ['h', 'hours', 'hour', 'hrs', 'hr'],
                ['d', 'days', 'day'],
                ['w', 'weeks', 'week'],
            ]
            lastPart = lastPart.replace(' ', '')
            lastPart = lastPart.lower()
            for rr in replacements:
                for r in rr[1:]:
                    if r in lastPart:
                        lastPart = lastPart.replace(r, rr[0])

            unitss = ['w', 'd', 'h', 'm', 's']
            for u in unitss:
                cnt = lastPart.count(u)
                if cnt > 1: return None, None, f"Error, you used **{u}** twice for the timer, don't do that."

            units = {
                "w": 86400 * 7,
                "d": 86400,
                "h": 3600,
                "m": 60,
                "s": 1
            }
            seconds = 0
            match = re.findall("([0-9]+[smhdw])", lastPart)  # Thanks to 3dshax server's former bot
            if not match:
                return None, None, f"Could not parse length. Are you using the right format?"
            try:
                for item in match:
                    seconds += int(item[:-1]) * units[item[-1]]
                # if seconds <= 10:
                #     return await ctx.send("Reminder can't be less than 10 seconds from now!")
                delta = datetime.timedelta(seconds=seconds)
            except OverflowError:
                return None, None, "**Overflow.** Future time too long. Please input a shorter time."
            remind_time = timestamp + delta

        else:
            if idx != idx4 or 'orrow' in lastPart or 'on' in lastPart:
                replacements = [
                    ['1', 'january', 'jan'],
                    ['2', 'february', 'feb'],
                    ['3', 'march', 'mar'],
                    ['4', 'april', 'apr'],
                    ['5', 'may'],
                    ['6', 'june', 'jun'],
                    ['7', 'july', 'jul'],
                    ['8', 'august', 'aug'],
                    ['9', 'september', 'sep'],
                    ['10', 'october', 'oct'],
                    ['11', 'november', 'nov'],
                    ['12', 'december', 'dec'],
                ]
                # lastPart = lastPart.replace(' ', '')
                lastPart = lastPart.lower()
                for rr in replacements:
                    for r in rr[1:]:
                        if r in lastPart:
                            lastPart = lastPart.replace(r, f' {rr[0]} ')

                tomorrow = timestamp + datetime.timedelta(days=1)
                if 'at' in lastPart:
                    lastPart = lastPart.replace('tomorrow', f'{tomorrow.year} {tomorrow.month} {tomorrow.day}')
                    lastPart = lastPart.replace('orrow', f'{tomorrow.year} {tomorrow.month} {tomorrow.day}')
                else:
                    lastPart = lastPart.replace('tomorrow', f'on {tomorrow.year} {tomorrow.month} {tomorrow.day}')
                    lastPart = lastPart.replace('orrow', f'on {tomorrow.year} {tomorrow.month} {tomorrow.day}')

                if lastPart.count('at ') > 1: return None, None, "Don't use more than two `at ` there...."
                if lastPart.count('on ') > 1: return None, None, "Don't use more than two `on ` there...."
                m5 = re.findall(r'(.*?)at (.*?$)', lastPart)
                m6 = re.findall(r'(.*?)on (.*?$)', lastPart)
                m3 = re.findall(r'(.*?$)', lastPart)
                on_part = ""
                at_part = ""

                if m3 and not m5 and not m6:
                    on_part = lastPart
                if m5:
                    on_part = m5[0][0]
                    at_part = m5[0][1]
                if m6:
                    at_part = m6[0][0]
                    on_part = m6[0][1]

                nums = list(map(int, re.findall(r'\d+', on_part)))
                if len(nums) == 1:
                    return None, None, "If you use `on` you have to provide at least a month and a day"
                if len(nums) == 2:
                    on_part = f'{timestamp.year} {on_part}'

                lastPart = f'{on_part} {at_part}'


            # if idx == idx7:
            #    tomorrow = timestamp + datetime.timedelta(days=1)
            #    lastPart = f'{tomorrow.year} {tomorrow.month} {tomorrow.day} {lastPart}'

            else:  # at only
                lastPart = f'{timestamp.year} {timestamp.month} {timestamp.day} {lastPart}'

            remind_time, err = get_regexed_time_from_str_and_possible_err(lastPart)
            if err:
                return None, None, err

        if remind_time < timestamp: return None, None, "Time can not be in the past."
        return midPart, remind_time, None
    except Exception as e:
        ee = str(e).replace('@', '@\u200b')
        error = (f"Something went wrong when parsing time. "
                 f"Please check your "
                 f"syntax and semantics. Exception:\n"
                 f"```\n{ee}```")
        return None, None, error
