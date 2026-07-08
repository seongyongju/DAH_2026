"""
DAH 2026 - Victim Server (취약점 내장 가상 공격 대상)
===================================================
방산 도메인(UAV/UGV/위성통신) 지상통제소(GCS)를 모사한 의도적 취약 서버.

이 서버는 격리된 Docker 네트워크에서만 구동되며, 실제 무기체계가 아닌
'디지털 트윈' 성격의 시뮬레이터다. 다음 5개 시나리오에 대응하는
현실적 취약점을 내장한다.

  S1  GCS 웹 대시보드 : SQL Injection 인증 우회 + IDOR (임무 데이터 무단 열람)
  S4  펌웨어 OTA      : 서명 검증 없는 UGV 펌웨어 업로드 (공급망/지속성)
  (S2 MAVLink, S3 SATCOM, S5 MQTT 는 별도 프로세스/브로커)

경고: 학습·경진대회용. 인터넷에 노출 금지.
"""
import os
import sqlite3
import hashlib
import logging
from datetime import datetime
from flask import Flask, request, jsonify, session, g, render_template, redirect

APP_ROOT = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_ROOT, "gcs.db")
FIRMWARE_DIR = os.path.join(APP_ROOT, "firmware_store")
os.makedirs(FIRMWARE_DIR, exist_ok=True)

# 방어 에이전트가 관찰할 통합 감사 로그(공격/정상 이벤트가 모두 흐른다)
logging.basicConfig(
    filename=os.path.join(APP_ROOT, "gcs_audit.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
audit = logging.getLogger("gcs.audit")

app = Flask(__name__)
app.secret_key = "gcs-dev-key-CHANGE-ME"  # (취약점: 하드코딩 시크릿)


# --------------------------------------------------------------------------
# DB 초기화 : 실제 방산 GCS 를 모사한 자산/임무/사용자 스키마
# --------------------------------------------------------------------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS missions;
        DROP TABLE IF EXISTS assets;

        CREATE TABLE users(
            id INTEGER PRIMARY KEY,
            username TEXT, password TEXT, role TEXT, clearance TEXT);

        CREATE TABLE assets(
            id INTEGER PRIMARY KEY,
            callsign TEXT, kind TEXT, status TEXT, ip TEXT);

        CREATE TABLE missions(
            id INTEGER PRIMARY KEY,
            owner_id INTEGER, title TEXT, classification TEXT,
            waypoints TEXT, payload TEXT);
        """
    )
    # 사용자 (평문/약한 해시 저장 = 취약점)
    users = [
        (1, "operator", "operator123", "operator", "CONFIDENTIAL"),
        (2, "admin", "Adm!n_2026", "admin", "SECRET"),
        (3, "maint", "maint", "maintainer", "CONFIDENTIAL"),
    ]
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?)", users)

    assets = [
        (1, "HAWK-01", "UAV", "AIRBORNE", "10.20.0.31"),
        (2, "MULE-07", "UGV", "STANDBY", "10.20.0.41"),
        (3, "SATLINK-A", "SATCOM", "LINKED", "10.20.0.51"),
    ]
    cur.executemany("INSERT INTO assets VALUES (?,?,?,?,?)", assets)

    missions = [
        (1, 1, "정찰 순찰 A", "CONFIDENTIAL",
         "37.5665,126.9780;37.5700,126.9820", "EO/IR 카메라"),
        (2, 2, "국경 감시 (기밀)", "SECRET",
         "38.0000,127.0000;38.0100,127.0200", "SIGINT 페이로드 좌표"),
    ]
    cur.executemany("INSERT INTO missions VALUES (?,?,?,?,?,?)", missions)
    con.commit()
    con.close()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_):
    d = g.pop("db", None)
    if d is not None:
        d.close()


def client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


# --------------------------------------------------------------------------
# S1-a  로그인 : SQL Injection 취약 (문자열 포매팅으로 쿼리 조립)
# --------------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    u = data.get("username", "")
    p = data.get("password", "")
    # === 취약점: 파라미터 바인딩 없이 사용자 입력을 직접 삽입 ===
    q = ("SELECT id, username, role, clearance FROM users "
         f"WHERE username = '{u}' AND password = '{p}'")
    audit.info(f"LOGIN_ATTEMPT ip={client_ip()} user={u!r} query={q!r}")
    try:
        row = db().execute(q).fetchone()
    except Exception as e:
        audit.warning(f"LOGIN_SQL_ERROR ip={client_ip()} err={e}")
        return jsonify(ok=False, error="query error"), 400
    if row:
        session["uid"] = row["id"]
        session["role"] = row["role"]
        audit.info(f"LOGIN_OK ip={client_ip()} uid={row['id']} role={row['role']}")
        return jsonify(ok=True, role=row["role"], clearance=row["clearance"])
    audit.info(f"LOGIN_FAIL ip={client_ip()} user={u!r}")
    return jsonify(ok=False), 401


# --------------------------------------------------------------------------
# S1-b  임무 조회 : IDOR (본인 소유 여부/인가 검증 없음)
# --------------------------------------------------------------------------
@app.route("/api/mission/<int:mid>")
def get_mission(mid):
    # === 취약점: 세션 소유자·clearance 검증 없이 임의 임무 반환 ===
    row = db().execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
    audit.info(f"MISSION_READ ip={client_ip()} uid={session.get('uid')} mid={mid}")
    if not row:
        return jsonify(ok=False), 404
    return jsonify(ok=True, mission=dict(row))


@app.route("/api/assets")
def assets():
    rows = db().execute("SELECT callsign, kind, status, ip FROM assets").fetchall()
    return jsonify(ok=True, assets=[dict(r) for r in rows])


# --------------------------------------------------------------------------
# S4  펌웨어 OTA 업로드 : 서명 검증 없음 (악성 펌웨어 주입 가능)
# --------------------------------------------------------------------------
@app.route("/api/firmware/upload", methods=["POST"])
def firmware_upload():
    asset = request.form.get("asset", "UNKNOWN")
    sig = request.form.get("signature", "")
    f = request.files.get("firmware")
    if not f:
        return jsonify(ok=False, error="no file"), 400
    raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    # === 취약점: signature 를 '검증하지 않고' 기록만 한다 (항상 수락) ===
    path = os.path.join(FIRMWARE_DIR, f"{asset}_{sha[:12]}.bin")
    with open(path, "wb") as out:
        out.write(raw)
    audit.warning(
        f"FIRMWARE_UPLOAD ip={client_ip()} asset={asset} "
        f"size={len(raw)} sha256={sha} sig={sig!r} signature_verified=FALSE")
    return jsonify(ok=True, asset=asset, sha256=sha, accepted=True)


@app.route("/")
def index():
    return jsonify(
        service="DAH2026 GCS (VULNERABLE TWIN)",
        endpoints=["/api/login", "/api/mission/<id>", "/api/assets",
                   "/api/firmware/upload"],
        note="isolated lab only",
    )


if __name__ == "__main__":
    init_db()
    audit.info("GCS_BOOT " + datetime.utcnow().isoformat())
    app.run(host="0.0.0.0", port=8080)
