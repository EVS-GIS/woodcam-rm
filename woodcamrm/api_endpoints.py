from flask_restx import Resource
from woodcamrm import api

@api.route('/datarecovery')
@api.doc(params={'station': 'Station ID', 
                 'from_ts': 'From timestamp',
                 'to_ts': 'To timestamp'})
class DataRecovery(Resource):
    
    @api.doc(responses={403: 'Not Authorized'})
    def get(self, station, from_ts, to_ts):
        api.abort(403)
        
    def post(self, station, from_ts, to_ts):
        return {'station': station,
                'from_ts': from_ts,
                'to_ts': to_ts}