"""
Blue Team Defense Agent (방어 AI 에이전트) — 본 시스템의 핵심
=============================================================
방어 아키텍처의 중심. 4단계 파이프라인으로 동작한다.

    [1] DETECT  탐지 : 통합 감사 로그·텔레메트리에서 침해지표(IoC) 식별
    [2] DECIDE  판단 : 위험도(성공 여부)·미차단 여부로 대응 우선순위 결정(트리아지)
    [3] BLOCK   차단 : 시나리오별 방어 통제(enforce) 적용
    [4] RECOVER 복구 : 훼손 상태 회복(세션무효화·안전복귀·롤백·키회전 등)

'두뇌'는 providers.py 를 통해 자유롭게 교체(Claude API / Claude Code / Gemini /
Codex / offline)한다. LLM 미사용/오류 시 규칙 기반 결정론 로직으로 폴백한다.
"""
import json
import re
import tools
import providers

# ── 탐지 규칙(오프라인/보강용) : 로그 정규식 → (시나리오, 차단통제) ──────────────
DETECTORS = [
    (r"OR '1'='1|--|query error|LOGIN_SQL_ERROR", "S1",
     ["patch_sqli", "rbac_idor", "block_ip"]),
    (r"GEOFENCE_VIOLATION|RTL_OVERRIDE|DISARM|authenticated=FALSE", "S2",
     ["mavlink_signing", "geofence_enforce"]),
    (r"replay=True|SATCMD.*executed", "S3",
     ["enable_satcom_replay_protection"]),
    (r"signature_verified=FALSE|FIRMWARE_UPLOAD", "S4",
     ["verify_firmware_sig"]),
    (r"GPS_SPOOF_SUSPECT|swarm/.*/cmd", "S5",
     ["require_mqtt_auth"]),
]

ALL_CONTROLS = {
    "patch_sqli", "rbac_idor", "block_ip", "mavlink_signing",
    "geofence_enforce", "enable_satcom_replay_protection",
    "verify_firmware_sig", "require_mqtt_auth",
}
CONTROLS_FOR = {s: c for _, s, c in DETECTORS}

SYSTEM = """당신은 방산 지상통제소(UAV/UGV/위성통신/군집)의 Blue Team 방어
오케스트레이터다. 제공된 감사 로그에서 공격 침해지표(IoC)를 탐지하고, 각 위협에
대응하는 '실제 방산 환경에서 구현 가능한' 방어 통제를 선택하라.
반드시 JSON 만 출력하라:
{"detections":[{"scenario":"S?","evidence":"...","severity":"high|medium",
"controls":["..."]}], "summary":"..."}"""


# ───────────────────────────── [1] DETECT ──────────────────────────────
def detect(log_text: str) -> dict:
    """로그에서 위협을 탐지. 우선 LLM(선택된 provider), 실패 시 규칙 기반."""
    res = providers.complete(SYSTEM, "감사 로그:\n" + log_text[:6000])
    if res.ok and res.text:
        try:
            s, e = res.text.find("{"), res.text.rfind("}") + 1
            data = json.loads(res.text[s:e])
            for d in data.get("detections", []):
                d["controls"] = [c for c in d.get("controls", [])
                                 if c in ALL_CONTROLS]
            data["_backend"] = res.backend
            return data
        except Exception:
            pass
    # 규칙 기반 폴백
    dets = []
    for pattern, scen, controls in DETECTORS:
        m = re.search(pattern, log_text)
        if m:
            dets.append({"scenario": scen, "evidence": m.group(0)[:60],
                         "severity": "high", "controls": controls})
    return {"detections": dets, "_backend": "offline",
            "summary": f"{len(dets)}개 위협 탐지(규칙 기반)"}


# ───────────────────────────── [2] DECIDE ──────────────────────────────
def decide(detections: dict, active_defenses, succeeded, max_fixes) -> list:
    """트리아지: 아직 미차단 & 이번 라운드 '성공(고위험)' 위협을 우선 대응 대상으로.
    반환: 이번 라운드에 remediate 할 시나리오 리스트(상한 max_fixes)."""
    active = set(active_defenses)
    open_scen = [d["scenario"] for d in detections.get("detections", [])
                 if not (set(CONTROLS_FOR.get(d["scenario"], [])) & active)]
    # 중복 제거 + 성공(고위험)건 우선
    seen, ordered = set(), []
    for s in sorted(open_scen, key=lambda x: (x not in succeeded, x)):
        if s not in seen:
            seen.add(s)
            ordered.append(s)
    return ordered[:max_fixes]


# ───────────────────────────── [3] BLOCK ───────────────────────────────
def block(scenarios: list) -> list:
    """선정된 시나리오의 방어 통제를 enforce."""
    applied = []
    for s in scenarios:
        for c in CONTROLS_FOR.get(s, []):
            tools.apply_mitigation(c)
            applied.append(c)
    return applied


# ───────────────────────────── [4] RECOVER ─────────────────────────────
def recover(scenarios: list) -> list:
    """차단한 시나리오의 훼손 상태를 복구."""
    return [tools.recover(s) for s in scenarios]


# ───────────────────────── 파이프라인 단일 진입점 ───────────────────────
def defend(log_text, active_defenses, succeeded, max_fixes=2) -> dict:
    det = detect(log_text)
    chosen = decide(det, active_defenses, succeeded, max_fixes)
    applied = block(chosen)
    recovered = recover(chosen)
    return {"detections": det.get("detections", []),
            "backend": det.get("_backend", "offline"),
            "remediated_scenarios": chosen,
            "applied_controls": applied,
            "recovery": recovered}


if __name__ == "__main__":
    logs = tools.read_logs("all", tail=60)
    out = defend(logs, active_defenses=set(), succeeded=set(), max_fixes=2)
    print(json.dumps(out, ensure_ascii=False, indent=2))
