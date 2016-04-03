from flask_restler import Api, Resource


api = Api('EXAMPLE REST API', __name__, url_prefix='/api/v1')


@api.connect
class HelloResource(Resource):

    def get(self, resource=None, **kwargs):
        return 'Hello, %s!' % (resource and resource.title() or 'World')
