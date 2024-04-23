from discord.ext.commands import errors


class InvalidCommandUsage(errors.CommandError):
    def __init__(self, message: str = None):
        self.message = message