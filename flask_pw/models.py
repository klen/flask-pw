import peewee as pw
from flask._compat import with_metaclass, string_types


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
