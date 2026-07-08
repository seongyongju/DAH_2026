"""
S3 - 위성통신(SATCOM) C2 링크 시뮬레이터 (재전송 공격 취약)
=========================================================
방산 위성통신 업링크는 대역폭·지연 제약으로 인해 경량 프로토콜을
쓰는 경우가 많고, 링크 암호화나 재전송 방지(nonce/타임스탬프)가
누락되면 '명령 재전송(Replay) 공격'에 노출된다.

프레임:  SATCMD|<token>|<action>
  - token 은 세션마다 발급되지만 '재사용 검증'을 하지 않는다(취약점).
  - 공격자는 정상 명령 1개를 캡처(스니핑)한 뒤 그대로 재전송해
    UGV/UAV 를 반복 조종할 수 있다.

취약점:
  - 링크 평문(암호화 없음)
  - nonce/시퀀스/타임스탬프 미검증 → Replay 가능
"""
import socket
import logging
import os

LOG = os.path.join(os.path.dirname(__file__), "satcom_audit.log")
logging.basicConfig(filename=LOG, level=logging.INFO,
                    format="%(asctime)s | %(message)s")
log = logging.getLogger("satcom")

HOST, PORT = "0.0.0.0", 5600
VALID_TOKEN = "SAT-SESS-9F2C"     # 정상 운용 토큰(캡처 대상)
seen_tokens = set()               # (방어 강화 시 여기서 재사용을 막을 수 있음)
REPLAY_PROTECTION = os.environ.get("SATCOM_REPLAY_PROTECT", "0") == "1"


def handle(line: str, addr):
    parts = line.strip().split("|")
    if len(parts) != 3 or parts[0] != "SATCMD":
        return "NACK|malformed"
    _, token, action = parts
    replay = token in seen_tokens
    log.info(f"SATCMD from={addr} token={token} action={action} replay={replay}")

    if token != VALID_TOKEN:
        log.warning(f"BAD_TOKEN from={addr} token={token}")
        return "NACK|bad_token"

    if REPLAY_PROTECTION and replay:
        log.warning(f"REPLAY_BLOCKED from={addr} token={token} action={action}")
        return "NACK|replay_detected"

    seen_tokens.add(token)
    # 취약 모드: 동일 토큰 재전송도 그대로 실행됨
    return f"ACK|{action}|executed"


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(8)
    mode = "REPLAY_PROTECT" if REPLAY_PROTECTION else "VULNERABLE"
    log.info(f"SATCOM_SIM boot on {HOST}:{PORT} mode={mode}")
    print(f"[satcom] listening tcp/{PORT} ({mode})")
    while True:
        conn, addr = s.accept()
        with conn:
            data = conn.recv(1024)
            if not data:
                continue
            resp = handle(data.decode(errors="replace"), addr)
            conn.sendall(resp.encode())


if __name__ == "__main__":
    main()
