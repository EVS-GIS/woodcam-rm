import threading
import requests
import urllib.parse
import time
from flask import Flask
from flask_restful import Resource, Api

app = Flask(__name__)
api = Api(app)

uptime_data = {'seconds': 0}
hydrodata = {}
hydrodata_api = "https://hubeau.eaufrance.fr/api/"

def update_uptime():
    while True:
        time.sleep(1)
        vals = {'seconds': uptime_data['seconds'] + 1}
        uptime_data.update(vals)
        
uptime_thread = threading.Thread(name='update_uptime', target=update_uptime)
uptime_thread.setDaemon(True)
uptime_thread.start()

class uptime(Resource):
    def get(self):
        return uptime_data
        
def update_hydrodata():
    while True:
        time.sleep(30)
        obs_url = urllib.parse.urljoin(hydrodata_api, "v1/hydrometrie/observations_tr")
        rep = requests.get(obs_url, data={"code_entite":"V2942010"})
        data = rep.json()['data'][0]
        hydrodata.update(data)
    
hydrodata_thread = threading.Thread(name='update_hydrodata', target=update_hydrodata)
hydrodata_thread.setDaemon(True)
hydrodata_thread.start()

class hydro(Resource):
    def get(self):
        return hydrodata


@app.route("/")
def root_page():
    return hydrodata

api.add_resource(uptime, '/api/uptime')
api.add_resource(hydro, '/api/hydro')

if __name__ == "__main__":
    app.run()