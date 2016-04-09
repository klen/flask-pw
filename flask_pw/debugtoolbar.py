import logging
import time

import itsdangerous
from flask import current_app, request, abort, g
from flask_debugtoolbar import module
from flask_debugtoolbar.panels import DebugPanel
from flask_debugtoolbar.utils import format_sql
from peewee import SqliteDatabase


peewee = logging.getLogger('peewee')


def query_signer():
    return itsdangerous.URLSafeSerializer(current_app.config['SECRET_KEY'], salt='fdt-sql-query')


def load_query(data):
    try:
        return query_signer().loads(request.args['query'])
    except (itsdangerous.BadSignature, TypeError):
        abort(406)


def dump_query(query, params):
    try:
        return query_signer().dumps((query, params))
    except TypeError:
        return None


class AmountHandler(logging.Handler):

    def __init__(self, *args):
        super(AmountHandler, self).__init__(*args)
        self.records = []

    def emit(self, record):
        self.records.append((time.time() - self.time, record))
        self.time = time.time()

    @property
    def amount(self):
        return len(self.records)


class PeeweeDebugPanel(DebugPanel):

    name = 'Peewee'
    has_content = True

    def __init__(self, *args, **kwargs):
        self.handler = AmountHandler()
        peewee.setLevel('DEBUG')
        peewee.handlers = []
        peewee.addHandler(self.handler)
        super(PeeweeDebugPanel, self).__init__(*args, **kwargs)

    @property
    def has_content(self):
        return bool(self.handler.amount)

    def url(self):
        return ''

    def title(self):
        return 'Peewee ORM queries'

    def nav_title(self):
        return 'Peewee ORM %s' % self.handler.amount

    def process_request(self, request):
        self.handler.time = time.time()

    def content(self):
        data = []
        for duration, record in self.handler.records:

            sql, params = record.msg

            data.append({
                'signed_query': dump_query(sql, params),
                'sql': sql,
                'duration': duration,
            })

        return self.render('panels/sqlalchemy.html', {'queries': data})


@module.route('/sqlalchemy/sql_select', methods=['GET', 'POST'])
@module.route('/sqlalchemy/sql_explain', methods=['GET', 'POST'], defaults=dict(explain=True))
def sql_select(explain=False):
    statement, params = load_query(request.args['query'])
    database = current_app.extensions.get('peewee').database.obj

    if explain:
        if isinstance(database, SqliteDatabase):
            statement = 'EXPLAIN QUERY PLAN\n%s' % statement
        else:
            statement = 'EXPLAIN\n%s' % statement

    result = database.execute_sql(statement, params)
    headers = []
    data = list(result.fetchall())
    if data:
        headers = ['' for _ in range(len(data[0]))]
    return g.debug_toolbar.render('panels/sqlalchemy_select.html', {
        'result': data,
        'headers': headers,
        'sql': format_sql(statement, params),
        'duration': float(request.args['duration']),
    })
