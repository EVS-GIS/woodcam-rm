import json

from functools import reduce  # forward compatibility for Python 3
import operator

from flask_mail import Message

from woodcamrm.extensions import mqtt, mail
from woodcamrm.db import Users

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


def alerts(stations):
    for station in stations:
        alerts = {
            'tampering': f"!Critical alert! Tampering detected on station {station.common_name}.",
            'sd_alert': f"SD storage alert on station {station.common_name}.",
            'sd_disruption': f"!Critical alert! SD storage disruption on station {station.common_name}.",
            'temp_alert': f"Temperature alert on station {station.common_name}!"
        }

        for alert in alerts.keys():
            if getattr(station, alert) == '1':
                msg = Message(f"[woodcam-rm] Alert on station {station.common_name}",
                            body=alerts[alert])

                for user in Users.query.filter_by(notify=True).all():
                    msg.add_recipient(user.email)

                mail.send(msg)

    return
