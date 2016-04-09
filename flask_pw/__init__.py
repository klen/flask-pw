import logging
from importlib import import_module

import peewee as pw
from cached_property import cached_property
from flask._compat import string_types
from peewee_migrate.router import Router, LOGGER
from playhouse.db_url import connect

from .models import Model, BaseSignalModel, Choices # noqa


__license__ = "MIT"
__project__ = "Flask-PW"
__version__ = "0.1.2"


class Peewee(object):

    def __init__(self, app=None):
        """Initialize the plugin."""
        self.app = app
        self.database = pw.Proxy()
        if app is not None:
            self.init_app(app)

    def init_app(self, app, database=None):
        """Initialize application."""

        # Register application
        if not app:
            raise RuntimeError('Invalid application.')
        self.app = app
        if not hasattr(app, 'extensions'):
            app.extensions = {}
        app.extensions['peewee'] = self

        app.config.setdefault('PEEWEE_CONNECTION_PARAMS', {})
        app.config.setdefault('PEEWEE_DATABASE_URI', 'sqlite:///peewee.sqlite')
        app.config.setdefault('PEEWEE_MODELS_IGNORE', [])
        app.config.setdefault('PEEWEE_MANUAL', False)
        app.config.setdefault('PEEWEE_MIGRATIONS', 'migrations')
        app.config.setdefault('PEEWEE_MODELS_CLASS', Model)
        app.config.setdefault('PEEWEE_MODELS_MODULE', '')

        # Initialize database
        database = database or app.config.get('PEEWEE_DATABASE_URI')
        if not database:
            raise RuntimeError('Invalid database.')
        if isinstance(database, string_types):
            database = connect(database, **app.config['PEEWEE_CONNECTION_PARAMS'])
        self.database.initialize(database)
        if self.database.database == ':memory:':
            app.config['PEEWEE_MANUAL'] = True
        if not app.config['PEEWEE_MANUAL']:
            app.before_request(self.connect)
            app.after_request(self.close)

    def connect(self):
        """Initialize connection to databse."""
        return self.database.connect()

    def close(self, response):
        """Close connection to database."""
        if not self.database.is_closed():
            self.database.close()
        return response

    @cached_property
    def Model(self):
        """Bind model to self database."""
        Model_ = self.app.config['PEEWEE_MODELS_CLASS']
        Meta = type('Meta', (), {'database': self.database})
        return type('Model', (Model_,), {'Meta': Meta})

    @property
    def models(self):
        """Return self.application models."""
        Model_ = self.app.config['PEEWEE_MODELS_CLASS']
        ignore = self.app.config['PEEWEE_MODELS_IGNORE']

        models = []
        if Model_ is not Model:
            try:
                mod = import_module(self.app.config['PEEWEE_MODELS_MODULE'])
                for model in dir(mod):
                    models = getattr(mod, model)
                    if not isinstance(model, pw.Model):
                        continue
                    models.append(models)
            except ImportError:
                return models
        elif isinstance(Model_, BaseSignalModel):
            models = BaseSignalModel.models

        return [m for m in models if m._meta.name not in ignore]

    @cached_property
    def manager(self):
        """Integrate a Flask-Script."""
        from flask_script import Manager

        manager = Manager(usage="Migrate database.")

        @manager.command
        def create(name, auto=False):
            """Create a new migration."""

            LOGGER.setLevel('INFO')
            LOGGER.propagate = 0

            router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])

            if auto:
                auto = self.models

            router.create(name, auto=auto)

        @manager.command
        def migrate(name=None, fake=False):
            """Run migrations."""
            from peewee_migrate.router import Router, LOGGER

            LOGGER.setLevel('INFO')
            LOGGER.propagate = 0

            router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])
            migrations = router.run(name, fake=fake)
            if migrations:
                logging.warn('Migrations are completed: %s' % ', '.join(migrations))

        @manager.command
        def rollback(name):
            """Rollback migrations."""
            from peewee_migrate.router import Router, LOGGER

            LOGGER.setLevel('INFO')
            LOGGER.propagate = 0

            router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])
            router.rollback(name)

        @manager.command
        def list():
            """List migrations."""
            from peewee_migrate.router import Router, LOGGER

            LOGGER.setLevel('DEBUG')
            LOGGER.propagate = 0

            router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])
            LOGGER.info('Migrations are done:')
            LOGGER.info('\n'.join(router.done))
            LOGGER.info('')
            LOGGER.info('Migrations are undone:')
            LOGGER.info('\n'.join(router.diff))

        return manager
