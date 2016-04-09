The Flask-PW
############

.. _badges:

.. .. image:: http://img.shields.io/travis/klen/falsk-pw.svg?style=flat-square
    .. :target: http://travis-ci.org/klen/falsk-pw
    .. :alt: Build Status

.. .. image:: http://img.shields.io/pypi/v/flask-pw.svg?style=flat-square
    .. :target: https://pypi.python.org/pypi/flask-pw
    .. :alt: Version

.. .. image:: http://img.shields.io/pypi/dm/flask-pw.svg?style=flat-square
    .. :target: https://pypi.python.org/pypi/flask-pw
    .. :alt: Downloads

.. _description:

The Flask-PW -- Peewee_ ORM intergration for Flask_ framework.

The plugin configures DB connection and provides some tools such as migrations
and signals. It also provides Peewee_ ORM support for Flask-Debugtoolbar_

.. _contents:

.. contents::

Requirements
=============

- python 2.7+,3.4+

.. _installation:

Installation
=============

**Flask-PW** should be installed using pip: ::

    pip install flask-pw

.. _usage:

Usage
=====

Settings
--------

Flask-PW settings (default values): ::

    # Connection URI
    PEEWEE_DATABASE_URI = 'sqlite:///peewee.sqlite'

    # Connection params (for example for pgsql: { encoding: 'utf-8' })
    PEEWEE_CONNECTION_PARAMS = {}

    # Path to directory which contains migrations
    PEEWEE_MIGRATIONS = 'migrations'

    # Path to module which contains you applications' Models
    # Needed by automatic migrations
    PEEWEE_MODELS_MODULE = ''

    # Models which should be ignored in migrations
    PEEWEE_MODELS_IGNORE = []

    # Base models class
    # Use `db.Model` as your models' base class for automatically DB binding 
    PEEWEE_MODELS_CLASS = <flask_pw.Model>

    # Don't connect to db when request starts and close when it ends automatically
    PEEWEE_MANUAL = False


Example
-------

::

    import peewee as pw
    from flask import Flask

    from flask_pw import Peewee


    app = Flask(__name__)

    app.config['PEEWEE_DATABASE_URI'] = 'sqlite:///:memory:'

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


Migrations
----------

If you use `Flask-Script` just add 'db' command to your manager: ::

    manager = Manager(create_app)
    manager.add_command('db', db.manager)

And use `db create`, `db migrate` and `db rollback` commands.


Flask-Debugtoolbar
------------------

Just add `flask_pw.debugtoolbar.PeeweeDebugPanel` to Flask-Debugtoolbar_ panels in your
application's configuration: ::

    DEBUG_TB_PANELS = [
        'flask_debugtoolbar.panels.versions.VersionDebugPanel',
        'flask_debugtoolbar.panels.timer.TimerDebugPanel',
        'flask_debugtoolbar.panels.headers.HeaderDebugPanel',
        'flask_debugtoolbar.panels.request_vars.RequestVarsDebugPanel',
        'flask_debugtoolbar.panels.template.TemplateDebugPanel',
        'flask_debugtoolbar.panels.sqlalchemy.SQLAlchemyDebugPanel',
        'flask_debugtoolbar.panels.logger.LoggingPanel',
        'flask_debugtoolbar.panels.profiler.ProfilerDebugPanel',

        # Add the Peewee panel
        'flask_pw.flask_debugtoolbar.PeeweeDebugPanel',
    ]

Enjoy!


.. _bugtracker:

Bug tracker
===========

If you have any suggestions, bug reports or
annoyances please report them to the issue tracker
at https://github.com/klen/flask-pw/issues

.. _contributing:

Contributing
============

Development of The Flask-pw happens at: https://github.com/klen/flask-pw


Contributors
=============

* `Kirill Klenov <https://github.com/klen>`_

.. _license:

License
========

Licensed under a MIT license (See LICENSE)

If you wish to express your appreciation for the project, you are welcome to
send a postcard to: ::

    Kirill Klenov
    pos. Severny 8-3
    MO, Istra, 143500
    Russia

.. _links:

.. _klen: https://github.com/klen
.. _Flask: http://flask.pocoo.org/
.. _Peewee: http://docs.peewee-orm.com/en/latest/
.. _Flask-Debugtoolbar: https://flask-debugtoolbar.readthedocs.org/en/latest/
