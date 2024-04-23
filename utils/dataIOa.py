import logging
import os
from json import decoder, dump, load
from os import replace
from os.path import splitext
from random import randint

logger = logging.getLogger('info')
error_logger = logging.getLogger('error')


class DataIOa:

    def init_json(self, filename):
        """Verifies that a JSON file exists and is valid; if not, create one."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                load(f)
        except (FileNotFoundError, decoder.JSONDecodeError):
            with open(filename, 'w', encoding='utf-8') as f:
                dump({}, f, indent=4,sort_keys=True,separators=(',',' : '))

    @staticmethod
    def save_json(filename, data):
        """Atomically save a JSON file given a filename and a dictionary."""
        path, _ = splitext(filename)
        tmp_file = "{}.{}.tmp".format(path, randint(1000, 9999))
        with open(tmp_file, 'w', encoding='utf-8') as f:
            dump(data, f, indent=4, sort_keys=True, separators=(',', ' : '))
        try:
            with open(tmp_file, 'r', encoding='utf-8') as f:
                data = load(f)
        except decoder.JSONDecodeError:
            error_logger.error("Attempted to write file {} but JSON "
                               "integrity check on tmp file has failed. "
                               "The original file is unaltered."
                               "".format(filename))
            return False
        except Exception as e:
            error_logger.error('A issue has occured saving ' + filename + '.\n'
                                                                          'Traceback:\n'
                                                                          '{0} {1}'.format(str(e), e.args))
            return False

        replace(tmp_file, filename)
        return True

    @staticmethod
    def load_json(filename):
        """Load a JSON file and return a dictionary."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = load(f)
            return data
        except Exception as e:
            error_logger.error('A issue has occured loading ' + filename + '.\n'
                                                                           'Traceback:\n'
                                                                           '{0} {1}'.format(str(e), e.args))
            return {}

    @staticmethod
    def append_json(filename, data):
        """Append a value to a JSON file."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                file = load(f)
        except Exception as e:
            error_logger.error('A issue has occured loading ' + filename + '.\n'
                                                                           'Traceback:\n'
                                                                           '{0} {1}'.format(str(e), e.args))
            return False
        try:
            file.append(data)
        except Exception as e:
            error_logger.error('A issue has occured updating ' + filename + '.\n'
                                                                            'Traceback:\n'
                                                                            '{0} {1}'.format(str(e), e.args))
            return False
        path, _ = splitext(filename)
        tmp_file = "{}.{}.tmp".format(path, randint(1000, 9999))
        with open(tmp_file, 'w', encoding='utf-8') as f:
            dump(file, f, indent=4, sort_keys=True, separators=(',', ' : '))
        try:
            with open(tmp_file, 'r', encoding='utf-8') as f:
                data = load(f)
        except decoder.JSONDecodeError:
            error_logger.error("Attempted to write file {} but JSON "
                               "integrity check on tmp file has failed. "
                               "The original file is unaltered."
                               "".format(filename))
            return False
        except Exception as e:
            print('A issue has occured saving ' + filename + '.\n'
                                                             'Traceback:\n'
                                                             '{0} {1}'.format(str(e), e.args))
            return False

        replace(tmp_file, filename)
        return True

    @staticmethod
    def is_valid_json(filename):
        """Verify that a JSON file exists and is readable. Take in a filename and return a boolean."""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                load(f)
            return True
        except (FileNotFoundError, decoder.JSONDecodeError):
            error_logger.error(f"FileNotFoundError {filename}")
            return False
        except Exception as e:
            error_logger.error('A issue has occured validating ' + filename + '.\n'
                                                                              'Traceback:\n'
                                                                              '{0} {1}'.format(str(e), e.args))
            return False

    @staticmethod
    def create_file_if_doesnt_exist(filename, whatToWriteIntoIt):
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                f.write(whatToWriteIntoIt)


dataIOa = DataIOa()
