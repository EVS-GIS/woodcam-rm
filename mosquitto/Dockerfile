
FROM eclipse-mosquitto:2.0.11

ARG mqtt_username
ARG mqtt_password

COPY . ./mosquitto/config
RUN if [ -f /mosquitto/config/passwordfile ]; \
    then echo "password file found"; \
    else touch /mosquitto/config/passwordfile ;\
    mosquitto_passwd -b /mosquitto/config/passwordfile $mqtt_username $mqtt_password ; \
    fi

EXPOSE 1883
EXPOSE 8883

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/usr/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]