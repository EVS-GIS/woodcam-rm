import os
import requests
import urllib3
import pytz
import simplejson as json

from datetime import datetime, timedelta
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import check_password_hash
from requests.auth import HTTPDigestAuth 
from xml.etree import ElementTree

from flask_restx import Resource, fields, inputs
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

@api.route('/stations')
class StationsEndpoint(Resource):
    decorators = [auth.login_required]
    
    @api.doc(description="List stations")
    def get(self):

        stations = Stations.query.all()
        results = {st.common_name:st.__dict__ for st in stations}
        results = json.dumps(results, use_decimal=True, default=lambda o: 'NA')
        
        return {'data': results}


datarec_ns = api.namespace('datarecovery', description='Data recovery operations') 
api.add_namespace(datarec_ns)

clip_model = api.model('Clip', 
                       {
                        'station': fields.String(required=True, description='Station common name'),
                        'from_date': fields.DateTime(required=True, description='From datetime. Accepted format: YYYY-mm-ddTHH:MM:SS+ZZ:ZZ (example: 2018-12-21T00:00:01+02:00)'),
                        'to_date': fields.DateTime(required=True, description='To datetime. Accepted format: YYYY-mm-ddTHH:MM:SS+ZZ:ZZ (example: 2018-12-21T00:00:01+02:00)')
                        }
                       )

clip_parser = datarec_ns.parser()
clip_parser.add_argument("station", type=str, location="form")
clip_parser.add_argument("from_date", type=inputs.datetime_from_iso8601, location="form")
clip_parser.add_argument("to_date", type=inputs.datetime_from_iso8601, location="form")
    
    
@datarec_ns.route('/download_record')
class DataRecovery(Resource):
    decorators = [auth.login_required]
        
    @datarec_ns.doc(description='Download local camera record on the WoodCam-RM server', 
                    params={
                        'station': 'Station common name', 
                        'from_date': 'Download record from datetime. Accepted format: YYYY-mm-ddTHH:MM:SS+ZZ:ZZ (example: 2018-12-21T00:00:01+02:00)',
                        'to_date': 'Download record to datetime. Accepted format: YYYY-mm-ddTHH:MM:SS+ZZ:ZZ (example: 2018-12-21T00:00:01+02:00)'
                        }
                    )
    @api.expect(clip_parser)
    def post(self) -> None:
        
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        args = clip_parser.parse_args()
        station = args['station']
        from_date = args['from_date']
        to_date = args['to_date']
        
        recovered_duration = 10

        # Check if station exists
        st = Stations.query.filter(Stations.common_name == station).first()
        if not st:
            return {'error': 'station not found'}, 400
        
        # Check if recovery dir exists
        recovery_dir = os.path.join(st.storage_path, 'recovery')
        if not os.path.isdir(recovery_dir):
            os.mkdir(recovery_dir)
            
        # Generate list of 10min video files
        def datetime_range(start, end):
            current = start
            while current < end:
                yield current
                current += timedelta(minutes=recovered_duration)

        starts = [dt for dt in datetime_range(from_date, to_date)]
            
        # Get list of recordings stored on cameras with AXIS API
        rep = requests.get(f"https://{st.ip}:{st.camera_port}/axis-cgi/record/list.cgi?recordingid=all", 
                           auth=HTTPDigestAuth(st.api_user, st.api_password),
                           verify=False)
        
        tree = ElementTree.fromstring(rep.content)
        recordings = [rec.attrib for rec in tree.findall("./recordings/recording")]
        
        # Convert string attributes to datetime
        for record in recordings:
            for timekey in ('starttime', 'starttimelocal', 'stoptime', 'stoptimelocal'):
                if record[timekey]:
                    record[timekey] = datetime.strptime(record[timekey], '%Y-%m-%dT%H:%M:%S.%f%z')
            
        # Start loop for each 10min record output
        recovered_list = []
        for start_time in starts:
            stop_time = start_time + timedelta(minutes=recovered_duration)
            
            record = next(rec for rec in recordings if rec["starttime"].day == start_time.day)
            
            r = requests.get(f"https://{st.ip}:{st.camera_port}/axis-cgi/record/export/exportrecording.cgi",
                            auth=HTTPDigestAuth(st.api_user, st.api_password),
                            verify=False,
                            stream=True,
                            params={
                                'schemaversion': 1,
                                'recordingid': record['recordingid'],
                                'diskid': record['diskid'],
                                'exportformat': 'matroska',
                                'starttime': start_time.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'stoptime': stop_time.astimezone(pytz.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')                             
                            })
            
            if r.status_code == 200:
                recovered_archive_file = os.path.join(recovery_dir, f"recovered_{start_time.strftime('%Y-%m-%d_%H-%M-%S')}.mkv")
                
                with open(recovered_archive_file, 'wb') as output:
                    output.write(r.content)
                    
                r.close()
                
                recovered_list.append(recovered_archive_file)

        return {'recovered_archive_files': recovered_list,
                'retention': 3600}


@datarec_ns.route('/plan_recovery')
class PlanRecovery(Resource):
    decorators = [auth.login_required]

    @datarec_ns.doc(description='Plan data recovery for the next night')
    @api.expect(clip_parser)
    def post(self) -> None:
        return True
    
    
@datarec_ns.route('/list_recovery')
class PlanRecovery(Resource):
    decorators = [auth.login_required]

    @datarec_ns.doc(description='List data recovery planned for the next night')
    def get(self) -> None:
        return True