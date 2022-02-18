import json

from functools import reduce  # forward compatibility for Python 3
import operator

from woodcamrm.extensions import mqtt

topics = {
        'current_daymode': {
            'path': "/event/tns:onvif/VideoSource/tns:axis/DayNightVision/$source/VideoSourceConfigurationToken/1", 
            'data_map': ['message', 'data', 'day']},
        'temp_alert': {
            'path': "/event/tns:onvif/Device/tns:axis/Status/Temperature/Above_or_below", 
            'data_map': ['message', 'data', 'sensor_level']},
        'sd_alert': {
            'path': "/event/tns:axis/Storage/Alert/$source/disk_id/SD_DISK", 
            'data_map': ['message', 'data', 'alert']},
        'sd_disruption': {
            'path': "/event/tns:axis/Storage/Disruption/$source/disk_id/SD_DISK", 
            'data_map': ['message', 'data', 'disruption']},
        'tampering': {
            'path': "/event/tns:onvif/VideoSource/tns:axis/Tampering/$source/channel/1", 
            'data_map': []}
        }
    
    
def subscribe_topics(stations):    
    for st in stations:
        if st.mqtt_prefix:
            for topic in topics.keys():
                mqtt.subscribe(st.mqtt_prefix+topics[topic]['path'])
                

def to_dict(stations, message):
    data = {}
    for st in stations:
        if st.mqtt_prefix in message.topic:
            data['station'] = st
            break
        else:
            continue
        
    for topic in topics.keys():
        if topics[topic]['path'] in message.topic:
            data["topic"] = topic
            break
        else:
            continue
        
    def getFromDict(dataDict, mapList):
        return reduce(operator.getitem, mapList, dataDict)

    data["data"] = getFromDict(
        json.loads(message.payload.decode()), 
        topics[data["topic"]]["data_map"]
        )
    
    return data
        
