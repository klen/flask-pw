import peewee as pw
from flask import Flask

from flask_pw import Peewee


app = Flask(__name__)

app.config['PEEWEE_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['PEEWEE_READ_SLAVES'] = 'sqlite:///:memory:'

db = Peewee(app)


class User(db.Model):

    name = pw.CharField(255)
    title = pw.CharField(127, null=True)
    active = pw.BooleanField(default=True)
    rating = pw.IntegerField(default=0)


@User.post_save.connect
def update(user, created=False):
    if created:
        # Do something
        pass


def test_models():
    assert User._meta.database.database == ':memory:'
    assert db.models == [User]
    assert User._meta.read_slaves

    User.create_table()
    User._meta.read_slaves = [User._meta.database.obj]
    assert not User.select().count()
