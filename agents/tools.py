"""
공용 도구 계층 (Kali 실행 표면 + 로그 관찰)
==========================================
Red/Blue 에이전트가 호출하는 액션을 함수로 노출한다. 각 함수는
Docker 네트워크 안의 victim 컨테이너를 대상으로 실제 스크립트를 실행하고
구조화된 결과(JSON) 를 돌려준다. 방어 에이전트는 감사 로그를 읽는다.
"""
import os
import io
import json
import contextlib
import importlib.util

SCEN_DIR = os.path.join(os.path.dirname(__file__), "..", "attacker", "scenarios")
VICTIM_HTTP = os.environ.get("VICTIM_HTTP", "http://victim:8080")
VICTIM_HOST = os.environ.get("VICTIM_HOST", "victim")
MQTT_BROKER = os.environ.get("MQTT_BROKER", "mqtt")

# 방어 에이전트가 읽는 감사 로그(컨테이너 볼륨 공유 경로)
LOG_DIR = os.environ.get("VICTIM_LOG_DIR", "/logs")
LOG_FILES = {
    "web": "gcs_audit.log",
    "mavlink": "mavlink_audit.log",
    "satcom": "satcom_audit.log",
    "swarm": "swarm_audit.log",
}

SCENARIOS = {
    "S1": ("s1_web_sqli", VICTIM_HTTP),
    "S2": ("s2_mavlink_inject", VICTIM_HOST),
    "S3": ("s3_satcom_replay", VICTIM_HOST),
    "S4": ("s4_firmware_ota", VICTIM_HTTP),
    "S5": ("s5_mqtt_swarm", MQTT_BROKER),
}


def _load(mod_name):
    path = os.path.join(SCEN_DIR, mod_name + ".py")
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_attack(scenario_id: str) -> dict:
    """지정 시나리오(S1..S5)를 실행하고 결과 dict 반환."""
    if scenario_id not in SCENARIOS:
        return {"error": f"unknown scenario {scenario_id}"}
    mod_name, target = SCENARIOS[scenario_id]
    try:
        mod = _load(mod_name)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            res = mod.run(target)
        return res
    except Exception as e:
        return {"scenario": scenario_id, "success": False, "error": str(e)}


def read_logs(source: str = "all", tail: int = 40) -> str:
    """감사 로그를 읽어 방어 에이전트에 제공."""
    out = []
    targets = LOG_FILES if source == "all" else {source: LOG_FILES.get(source)}
    for name, fn in targets.items():
        if not fn:
            continue
        p = os.path.join(LOG_DIR, fn)
        if os.path.exists(p):
            with open(p, errors="replace") as f:
                lines = f.readlines()[-tail:]
            out.append(f"### {name} ({fn})\n" + "".join(lines))
    return "\n".join(out) if out else "(로그 없음)"


# 방어 조치(모사): 실제 환경에서는 방화벽/패치/브로커 ACL 적용에 해당
def apply_mitigation(control: str) -> dict:
    """
    [차단(Block) 계층] 방어 통제를 적용(enforce)한다.
    control 예: 'block_ip', 'enable_satcom_replay_protection',
               'require_mqtt_auth', 'patch_sqli', 'verify_firmware_sig',
               'mavlink_signing', 'geofence_enforce', 'rbac_idor'
    적용 사실을 기록/반환한다(오케스트레이터가 다음 라운드에 반영).
    """
    return {"applied": control, "status": "enforced"}


# 시나리오별 복구(Recover) 액션 — 침해 상태를 정상으로 되돌린다
RECOVERY_ACTIONS = {
    "S1": ["invalidate_sessions", "rotate_credentials"],      # 세션 무효화·자격증명 회전
    "S2": ["force_safe_rtl", "renegotiate_link_key"],         # 안전복귀·링크키 재협상
    "S3": ["revoke_satcom_token", "reissue_session_token"],   # 토큰 폐기·재발급
    "S4": ["reflash_golden_firmware", "verify_boot_hash"],    # 정상 펌웨어 재플래싱
    "S5": ["reset_swarm_waypoints", "rotate_broker_creds"],   # 스웜 좌표 리셋·자격증명 회전
}


def recover(scenario_id: str) -> dict:
    """
    [복구(Recover) 계층] 해당 시나리오로 훼손된 상태를 회복한다.
    실제 환경: 세션 강제만료·안전복귀·펌웨어 롤백·좌표 리셋·키 회전 등.
    """
    actions = RECOVERY_ACTIONS.get(scenario_id, [])
    return {"scenario": scenario_id, "recovery_actions": actions,
            "status": "restored" if actions else "noop"}


if __name__ == "__main__":
    import sys
    print(json.dumps(run_attack(sys.argv[1] if len(sys.argv) > 1 else "S1"),
                     ensure_ascii=False, indent=2))
