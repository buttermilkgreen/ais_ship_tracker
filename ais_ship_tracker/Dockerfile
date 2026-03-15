FROM python:3.11-alpine

RUN pip install websocket-client paho-mqtt

COPY ais_ship_tracker.py /

CMD ["python", "-u", "/ais_ship_tracker.py"]
