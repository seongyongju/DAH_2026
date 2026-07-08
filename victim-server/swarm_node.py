"""
S5 - 드론 스웜 노드 (MQTT 무인증 브로커 구독자)
==============================================
군집(스웜) 드론은 경량 pub/sub(MQTT)로 좌표·대형·명령을 공유한다.
브로커에 인증/ACL/TLS 가 없으면, 공격자가 스웜 토픽에 GPS 스푸핑
좌표나 명령을 브로드캐스트해 군집 전체를 유도할 수 있다.

이 노드는 브로커(mosquitto)의 swarm/+/cmd 를 구독하며 수신 명령을
로깅한다. 방어 에이전트는 이 로그와 브로커 로그로 이상 발행을 탐지한다.
"""
import os
import logging
import paho.mqtt.client as mqtt

LOG = os.path.join(os.path.dirname(__file__), "swarm_audit.log")
logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s | %(message)s")
log = logging.getLogger("swarm")

BROKER = os.environ.get("MQTT_BROKER", "mqtt")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
HOME = {"lat": 37.5665, "lon": 126.9780}


def on_connect(client, userdata, flags, rc):
    log.info(f"SWARM_NODE connected rc={rc}")
    client.subscribe("swarm/+/cmd")


def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="replace")
    log.info(f"RECV topic={msg.topic} payload={payload!r}")
    # GPS 스푸핑 탐지 신호: 홈 좌표에서 비정상적으로 먼 좌표
    if "goto" in payload.lower():
        try:
            coord = payload.split("goto:")[1]
            lat, lon = map(float, coord.split(","))
            dist = abs(lat - HOME["lat"]) + abs(lon - HOME["lon"])
            if dist > 1.0:
                log.warning(f"GPS_SPOOF_SUSPECT topic={msg.topic} coord={coord}")
        except Exception:
            pass


def main():
    import time
    c = mqtt.Client(client_id="swarm-node-01")
    c.on_connect = on_connect
    c.on_message = on_message
    log.info(f"SWARM_NODE boot broker={BROKER}:{PORT}")
    print(f"[swarm] connecting {BROKER}:{PORT}")
    # 브로커 기동 대기(도커 startup 순서·브로커 준비 지연 대비): 재시도
    for attempt in range(30):
        try:
            c.connect(BROKER, PORT, 60)
            break
        except Exception as e:
            log.info(f"SWARM_NODE connect retry {attempt} err={e}")
            time.sleep(2)
    else:
        log.warning("SWARM_NODE broker unreachable, giving up")
        return
    c.loop_forever()


if __name__ == "__main__":
    main()
