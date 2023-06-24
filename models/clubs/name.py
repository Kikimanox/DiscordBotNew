import logging

from peewee import (
    CharField,
    IntegerField,
    Model,
    SqliteDatabase,
)

logger = logging.getLogger("info")
error_logger = logging.getLogger("error")

DB = "data/club_name.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})

class BaseModel(Model):
    class Meta:
        database = db


class Club(BaseModel):
    id = IntegerField(primary_key=True)
    club_name = CharField(unique=True)

    @classmethod
    def fetch_or_create(cls, **kwargs):
        return cls.get_or_create(**kwargs)[0]

db.create_tables([Club])