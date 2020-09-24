from peewee import *
from datetime import datetime

DB = "data/manga.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class Tbd(BaseModel):
    id = IntegerField(primary_key=True)

