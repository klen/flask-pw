import logging
from importlib import import_module

import peewee as pw
from cached_property import cached_property
from flask._compat import with_metaclass, string_types
from peewee_migrate.router import Router, LOGGER
from playhouse.db_url import connect


__license__ = "MIT"
__project__ = "Flask-PW"
__version__ = "0.0.1"


class Choices:

    """Model's choices helper."""

    def __init__(self, *choices):
        """Parse provided choices."""
        self._choices = []
        self._reversed = {}
        for choice in choices:
            if isinstance(choice, string_types):
                choice = (choice, choice)
            self._choices.append(choice)
            self._reversed[str(choice[1])] = choice[0]

    def __getattr__(self, name, default=None):
        """Get choice value by name."""
        return self._reversed.get(name, default)

    def __iter__(self):
        """Iterate self."""
        return iter(self._choices)

    def __str__(self):
        """String representation."""
        return ", ".join(self._reversed.keys())

    def __repr__(self):
        """Python representation."""
        return "<Choices: %s>" % self

    def __nonzero__(self):
        return True


class Signal:

    """Simplest signals implementation.

    ::
        @Model.post_save
        def example(instance, created=False):
            pass

    """

    __slots__ = 'receivers'

    def __init__(self):
        """Initialize the signal."""
        self.receivers = []

    def connect(self, receiver):
        """Append receiver."""
        if not callable(receiver):
            raise ValueError('Invalid receiver: %s' % receiver)
        self.receivers.append(receiver)

    def __call__(self, receiver):
        """Support decorators.."""
        self.connect(receiver)
        return receiver

    def disconnect(self, receiver):
        """Remove receiver."""
        try:
            self.receivers.remove(receiver)
        except ValueError:
            raise ValueError('Unknown receiver: %s' % receiver)

    def send(self, instance, *args, **kwargs):
        """Send signal."""
        for receiver in self.receivers:
            receiver(instance, *args, **kwargs)


class BaseSignalModel(pw.BaseModel):

    """Create signals."""

    models = []

    def __new__(mcs, name, bases, attrs):
        """Create signals."""
        cls = super(BaseSignalModel, mcs).__new__(mcs, name, bases, attrs)
        cls.pre_save = Signal()
        cls.pre_delete = Signal()
        cls.post_delete = Signal()
        cls.post_save = Signal()

        if cls._meta.db_table and cls._meta.db_table != 'model':
            mcs.models.append(cls)
        return cls


class Model(with_metaclass(BaseSignalModel, pw.Model)):

    @property
    def pk(self):
        """Return primary key value."""
        return self._get_pk_value()

    @classmethod
    def get_or_none(cls, *args, **kwargs):
        try:
            return cls.get(*args, **kwargs)
        except cls.DoesNotExist:
            return None

    def save(self, force_insert=False, **kwargs):
        """Send signals."""
        created = force_insert or not bool(self.pk)
        self.pre_save.send(self, created=created)
        super(Model, self).save(force_insert=force_insert, **kwargs)
        self.post_save.send(self, created=created)

    def delete_instance(self, *args, **kwargs):
        """Send signals."""
        self.pre_delete.send(self)
        super(Model, self).delete_instance(*args, **kwargs)
        self.post_delete.send(self)


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

        return manager
