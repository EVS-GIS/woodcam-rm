import requests
import json
import string

from woodcamrm.db import RecordMode

def update_rtsp_proxies(stations, url, port):
    # Get active proxies
    req = requests.get(f"http://{url}:{port}/v1/paths/list")
    proxies = json.loads(req.text)['items']
    
    for st in stations:
        # Remove whitespaces from common_name
        st_name = st.common_name.lower().translate({ord(c): None for c in string.whitespace})
        
        # Generate payload depending on recording mode
        if st.current_recording == RecordMode.high:
            payload = json.dumps({"source": f"rtsp://{st.ip}/axis-media/media.amp?fps=3&resolution=320x240&videocodec=h264&compression=30", "sourceOnDemand": False})
        else:
            payload = json.dumps({"source": f"rtsp://{st.ip}/axis-media/media.amp?fps=1&resolution=320x240&videocodec=h264&compression=30", "sourceOnDemand": True})
        
        # If the proxy doesn't exists, create it
        if st_name not in proxies.keys():
            try:
                req = requests.post(f"http://{url}:{port}/v1/config/paths/add/{st_name}", data = payload)
                assert req.status_code == 200
            except AssertionError:
                print(f'Warning! RTSP API request failed for station {st.common_name}.')
        
        # Else, update it
        else:
            try:
                req = requests.post(f"http://{url}:{port}/v1/config/paths/edit/{st_name}", data = payload)
                assert req.status_code == 200
            except AssertionError:
                print(f'Warning! RTSP API request failed for station {st.common_name}.')