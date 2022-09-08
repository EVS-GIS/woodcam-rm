import sys
import simplejson as json
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash

from flask_restx import Resource
from woodcamrm import api
from woodcamrm.db import Stations, Users


auth = HTTPBasicAuth()

@auth.verify_password
def authenticate(username, password):
    if username and password:
        
        user = Users.query.filter_by(username=username).first()
        
        error = None
        
        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user.password, password):
            error = 'Incorrect password.'

        if error is None:
            return True
        else:
            return False

        

@api.route('/datarecovery')
@api.doc(params={'station': 'Station ID', 
                 'from_ts': 'From timestamp',
                 'to_ts': 'To timestamp'})
class DataRecovery(Resource):
    decorators = [auth.login_required]
        
    def post(self, station, from_ts, to_ts):
        return {'station': station,
                'from_ts': from_ts,
                'to_ts': to_ts}


@api.route('/stations')
class StationsEndpoint(Resource):
    decorators = [auth.login_required]
    
    def get(self):

        stations = Stations.query.all()
        results = {st.common_name:st.__dict__ for st in stations}
        results = json.dumps(results, use_decimal=True, default=lambda o: 'NA')
        
        return {'data': results}