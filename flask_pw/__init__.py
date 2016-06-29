import logging
import os
from importlib import import_module

import peewee as pw
from cached_property import cached_property
from flask._compat import string_types
from peewee_migrate.router import Router
from playhouse.db_url import connect

from .models import Model, BaseSignalModel, Choices # noqa


__license__ = "MIT"
__project__ = "Flask-PW"
__version__ = "0.2.0"

LOGGER = logging.getLogger(__name__)


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
            app.teardown_request(self.close)

    def connect(self):
        """Initialize connection to databse."""
        LOGGER.info('Connecting [%s]', os.getpid())
        return self.database.connect()

    def close(self, response):
        """Close connection to database."""
        LOGGER.info('Closing [%s]', os.getpid())
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

    def cmd_create(self, name, auto=False):
        """Create a new migration."""

        LOGGER.setLevel('INFO')
        LOGGER.propagate = 0

        router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])

        if auto:
            auto = self.models

        router.create(name, auto=auto)

    def cmd_migrate(self, name=None, fake=False):
        """Run migrations."""
        from peewee_migrate.router import Router, LOGGER

        LOGGER.setLevel('INFO')
        LOGGER.propagate = 0

        router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])
        migrations = router.run(name, fake=fake)
        if migrations:
            LOGGER.warn('Migrations are completed: %s' % ', '.join(migrations))

    def cmd_rollback(self, name):
        """Rollback migrations."""
        from peewee_migrate.router import Router, LOGGER

        LOGGER.setLevel('INFO')
        LOGGER.propagate = 0

        router = Router(self.database, self.app.config['PEEWEE_MIGRATIONS'])
        router.rollback(name)

    def cmd_list(self):
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

    @cached_property
    def manager(self):
        """Integrate a Flask-Script."""
        from flask_script import Manager, Command

        manager = Manager(usage="Migrate database.")
        manager.add_command('create', Command(self.cmd_create))
        manager.add_command('migrate', Command(self.cmd_migrate))
        manager.add_command('rollback', Command(self.cmd_rollback))
        manager.add_command('list', Command(self.cmd_list))

        return manager

    @cached_property
    def cli(self):
        import click

        @click.group()
        def cli():
            """Peewee Migrations."""
            pass

        @cli.command()
        @click.argument('name')
        @click.option('--auto', is_flag=True)
        def create(name, auto=False):
            """Create a new migration."""
            return self.cmd_create(name, auto)

        @cli.command()
        @click.argument('name')
        @click.option('--fake', is_flag=True)
        def migrate(name, fake=False):
            """Run migrations."""
            return self.cmd_migrate(name, fake)

        @cli.command()
        @click.argument('name')
        def rollback(name):
            """Rollback migrations."""
            return self.cmd_rollback(name)

        @cli.command()
        def list(name):
            """List migrations."""
            return self.cmd_list()

        return cli
