"""
S2 - MAVLink UAV 시뮬레이터 (무인증 명령 채널)
==============================================
실제 UAV/GCS 는 MAVLink 프로토콜(UDP)로 통신한다. MAVLink v1 과
서명(signing)을 끄고 운용하는 MAVLink v2 는 '명령 출처 인증'이 없어
공격자가 GCS 를 사칭해 명령을 주입할 수 있다.

여기서는 프로토콜 핵심 개념만 남긴 경량 텍스트 프레임으로 모사한다.
  프레임:  MAVLINK|<seq>|<cmd>|<params>
  주요 명령:  HEARTBEAT, SET_MODE, NAV_WAYPOINT, RTL(복귀), DISARM

취약점:
  - 무인증(누구든 UDP 로 명령 주입 가능)
  - 시퀀스/서명 검증 없음
  - 지오펜스(비행금지구역) 검증이 애플리케이션 레벨에 없음
"""
import socket
import logging
import os

LOG = os.path.join(os.path.dirname(__file__), "mavlink_audit.log")
logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s | %(message)s")
log = logging.getLogger("mavlink")

HOST, PORT = "0.0.0.0", 14550
# 안전 비행 범위(지오펜스) — 이 범위를 벗어난 웨이포인트는 '위반'
GEOFENCE = {"lat": (37.4, 37.7), "lon": (126.8, 127.1)}

state = {"mode": "AUTO", "armed": True, "wp": "37.5665,126.9780", "last_seq": 0}


def handle(frame: str, addr):
    parts = frame.strip().split("|")
    if len(parts) < 3 or parts[0] != "MAVLINK":
        log.info(f"MALFORMED from={addr} raw={frame!r}")
        return "NACK|malformed"
    _, seq, cmd = parts[0], parts[1], parts[2]
    params = parts[3] if len(parts) > 3 else ""
    log.info(f"CMD from={addr} seq={seq} cmd={cmd} params={params!r} "
             f"authenticated=FALSE")

    if cmd == "HEARTBEAT":
        return f"HEARTBEAT|mode={state['mode']}|armed={state['armed']}"
    if cmd == "SET_MODE":
        state["mode"] = params or "AUTO"
        return f"ACK|SET_MODE|{state['mode']}"
    if cmd == "NAV_WAYPOINT":
        state["wp"] = params
        # 지오펜스 위반 여부 로깅(탐지용 신호)
        try:
            lat, lon = map(float, params.split(","))
            in_fence = (GEOFENCE["lat"][0] <= lat <= GEOFENCE["lat"][1]
                        and GEOFENCE["lon"][0] <= lon <= GEOFENCE["lon"][1])
        except Exception:
            in_fence = False
        if not in_fence:
            log.warning(f"GEOFENCE_VIOLATION from={addr} wp={params!r}")
        return f"ACK|NAV_WAYPOINT|{params}|geofence_ok={in_fence}"
    if cmd == "RTL":            # Return-To-Launch 무력화 시도
        state["mode"] = "MANUAL"
        log.warning(f"RTL_OVERRIDE from={addr} (복귀 무력화)")
        return "ACK|RTL_DISABLED"
    if cmd == "DISARM":
        state["armed"] = False
        log.warning(f"DISARM from={addr} (비행 중 시동 정지)")
        return "ACK|DISARM"
    return "NACK|unknown_cmd"


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((HOST, PORT))
    log.info(f"MAVLINK_SIM boot on {HOST}:{PORT}")
    print(f"[mavlink] listening udp/{PORT}")
    while True:
        data, addr = s.recvfrom(2048)
        try:
            resp = handle(data.decode(errors="replace"), addr)
            s.sendto(resp.encode(), addr)
        except Exception as e:
            log.info(f"ERROR {e}")


if __name__ == "__main__":
    main()
