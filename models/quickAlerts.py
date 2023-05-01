import datetime

from peewee import *

DB = "data/quick_alerts.db"
db = SqliteDatabase(DB, pragmas={'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class QuickAlerts(BaseModel):
    id = IntegerField(primary_key=True)
    alerted_message_id = IntegerField()
    alerted_message_ch_id = IntegerField()

    alerted_user_id = IntegerField()
    reportee_user_id = IntegerField()

    target_embed_message_id = IntegerField()
    status = IntegerField()  # 0 = unsolved, 1 = probably resolved
    created_on = DateTimeField(default=datetime.datetime.utcnow)


db.drop_tables([QuickAlerts])
db.create_tables([QuickAlerts])
