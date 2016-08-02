

import os
import logging
import rethinkdb as r

from flask import Flask, jsonify, abort
from flask_rethinkdb import RethinkDB
from flask_restful import Resource, Api, reqparse
from rethinkdb.errors import ReqlOpFailedError
# from eveauth.contrib.flask import authenticate

app = Flask(__name__)
db = RethinkDB(app)
api = Api(app)

# App Settings
app.config['BUNDLE_ERRORS'] = True
app.config['RETHINKDB_HOST'] = os.environ.get('RDB_HOST', '192.168.99.100')
app.config['RETHINKDB_PORT'] = os.environ.get('RDB_PORT', '32197')
app.config['RETHINKDB_DB'] = os.environ.get('RDB_DB', 'test')

RDB_TABLE = os.environ.get('RDB_TABLE', 'slack_webhooks')


class Webhooks(Resource):
    # @authenticate()
    def get(self, character_id):
        # if request.token['character_id'] != character_id:
        #     abort(403)

        results = r.table(RDB_TABLE).filter(lambda row: row['character'].eq(character_id)).run(db.conn)

        return [{'id': x['id'], 'name': x['name']} for x in results]

    # @authenticate()
    def post(self, character_id):
        # if request.token['character_id'] != character_id:
        #     abort(403)

        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, help='Name of the new webhook')
        parser.add_argument('url', type=str, required=True, help='URL for the Slack webhook')
        args = parser.parse_args(strict=True)

        result = r.table(RDB_TABLE).insert({
          'character': character_id,
          'name': args['name'],
          'url': args['url'],
        }).run(db.conn)

        webhook_id = result['generated_keys'][0]

        return {}, 201, {'Location': api.url_for(Webhook, character_id=character_id, webhook_id=webhook_id)}


class Webhook(Resource):
    # @authenticate()
    def get(self, character_id, webhook_id):
        # if request.token['character_id'] != character_id:
        #     abort(403)

        result = r.table(RDB_TABLE).get(webhook_id).run(db.conn)
        if result is None or result['character'] != character_id:
            abort(404)

        return result

    # @authenticate()
    def put(self, character_id, webhook_id):
        # if request.token['character_id'] != character_id:
        #     abort(403)

        result = r.table(RDB_TABLE).get(webhook_id).run(db.conn)
        if result is None or result['character'] != character_id:
            abort(404)

        parser = reqparse.RequestParser()
        parser.add_argument('name', type=str, required=True, help='Name of the new webhook')
        parser.add_argument('url', type=str, required=True, help='URL for the Slack webhook')
        parser.add_argument('value', type=int, help='')
        parser.add_argument('ids', type=int, help='', action='append')
        args = parser.parse_args(strict=True)

        update = {
            'id': webhook_id,
            'character': character_id,
            'name': args['name'],
            'url': args['url'],
        }

        if args['value'] is not None:
            update['value'] = args['value']

        if args['ids'] is not None:
            update['ids'] = args['ids']

        result = r.table(RDB_TABLE).get(webhook_id).replace(update).run(db.conn)

        return update, 200

    # @authenticate()
    def delete(self, character_id, webhook_id):
        # if request.token['character_id'] != character_id:
        #     abort(403)

        result = r.table(RDB_TABLE).get(webhook_id).run(db.conn)
        if result is None or result['character'] != character_id:
            abort(404)

        r.table(RDB_TABLE).get(webhook_id).delete().run(db.conn)

        return {}, 200


class WebhooksLookup(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('value', type=float, required=True, help='Value of the killmail')
        parser.add_argument('ids', type=int, required=True, help='IDs from the attackers', action='append')
        args = parser.parse_args(strict=True)

        results = r.table(RDB_TABLE).filter(
            lambda row: row['ids'].default([]).contains(lambda id: r.expr(args['ids']).contains(id)).or_(row['value'].le(args['value']))
        ).pluck('url').distinct().run(db.conn)

        return [x['url'] for x in results]


api.add_resource(Webhooks, '/api/settings/slack/<int:character_id>/webhooks/')
api.add_resource(Webhook, '/api/settings/slack/<int:character_id>/webhooks/<string:webhook_id>/')
api.add_resource(WebhooksLookup, '/api/settings/slack/webhooks/lookup/')


@app.before_first_request
def setup_logging():
    try:
        r.db_create(app.config['RETHINKDB_DB']).run(db.conn)
    except ReqlOpFailedError:
        pass

    try:
        r.table_create(RDB_TABLE).run(db.conn)
    except ReqlOpFailedError:
        pass

    if not app.debug:
        app.logger.addHandler(logging.StreamHandler())
        app.logger.setLevel(logging.INFO)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)
