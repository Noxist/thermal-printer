import ssl, json, uuid, time
import paho.mqtt.client as mqtt
from .config import MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, MQTT_TLS, TOPIC, PUBLISH_QOS

_client: mqtt.Client | None = None

def mqtt_start():
    global _client
    _client = mqtt.Client()
    if MQTT_TLS:
        _client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
    if MQTT_USER or MQTT_PASS:
        _client.username_pw_set(MQTT_USER, MQTT_PASS)
    _client.connect(MQTT_HOST, MQTT_PORT, 60)
    _client.loop_start()

def mqtt_stop():
    global _client
    try:
        if _client:
            _client.loop_stop()
            _client.disconnect()
    finally:
        _client = None

def mqtt_publish_image_base64(b64_png: str, cut_paper: int = 1,
                              paper_width_mm: int = 0, paper_height_mm: int = 0):
    payload = {
        "ticket_id": f"web-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
        "data_type": "png", "data_base64": b64_png,
        "paper_type": 0, "paper_width_mm": paper_width_mm, "paper_height_mm": paper_height_mm,
        "cut_paper": cut_paper
    }
    if not _client:
        raise RuntimeError("MQTT client not started")
    _client.publish(TOPIC, json.dumps(payload), qos=PUBLISH_QOS, retain=False)
