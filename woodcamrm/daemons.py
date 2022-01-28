import threading
import requests
import urllib.parse
import time


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
