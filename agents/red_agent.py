"""
Red Team Attack Agent (공격 AI 에이전트) — 보조 역할
====================================================
본 시스템에서 공격 에이전트는 '방어 아키텍처를 검증·강화하기 위한 보조 도구'다.
방어 파이프라인(탐지·차단·복구)이 실제로 위협을 막는지 확인할 수 있도록,
방산 5개 시나리오를 실행해 방어의 사각지대를 드러낸다.

동작:
  - 계획(plan)   : 공유 메모리의 성공률을 참고해 '아직 안 막힌' 취약점을 우선 시도
                   → 방어가 넓어질수록 공격은 남은 사각지대로 이동(방어 커버리지 측정)
  - 실행(execute): Kali 시나리오 스크립트로 실제 공격 후 성공/차단 판정

'두뇌'는 providers.py 로 자유 선택(Claude API / Claude Code / Gemini / Codex /
offline). LLM 미사용/오류 시 성공률 기반 결정론 정책으로 폴백한다.
"""
import json
import tools
import providers
import memory as mem_mod

SYSTEM = """당신은 방산 사이버 방어 검증을 돕는 Red Team 보조 에이전트다.
목적은 방어 체계의 사각지대를 드러내는 것이다. 대상은 격리 랩의 가상 방산
지상통제소이며, 5개 시나리오(S1 웹SQLi/IDOR, S2 MAVLink 명령주입,
S3 SATCOM 재전송, S4 펌웨어OTA, S5 MQTT 스웜)를 사용한다.
과거 라운드의 성공률/차단 이력을 참고해, 아직 방어되지 않은 취약점을 우선하는
공격 순서를 정하라. 반드시 JSON 만 출력:
{"plan": ["S?", ...], "rationale": "..."}"""


def plan(mem) -> dict:
    """이번 라운드 공격 순서(=방어 사각지대 탐침 순서)를 결정."""
    context = {
        "round": mem["rounds"],
        "stats": {s: {k: v for k, v in d.items() if k != "notes"}
                  for s, d in mem["scenarios"].items()},
        "defenses_applied": mem["defenses_applied"],
    }
    res = providers.complete(
        SYSTEM, "과거 이력:\n" + json.dumps(context, ensure_ascii=False)
        + "\n\n이번 라운드 공격 계획을 JSON 으로.")
    if res.ok and res.text:
        try:
            s, e = res.text.find("{"), res.text.rfind("}") + 1
            data = json.loads(res.text[s:e])
            data["_backend"] = res.backend
            if data.get("plan"):
                return data
        except Exception:
            pass
    # 결정론 폴백: 성공률↑·미시도 우선 재배치
    return {"plan": mem_mod.attack_priority(mem), "_backend": "offline",
            "rationale": "성공률↑·미시도 우선(방어 사각지대 탐침)"}


def execute(scenario_id: str) -> dict:
    """시나리오 실행 후 성공/차단 판정."""
    res = tools.run_attack(scenario_id)
    success = bool(res.get("success"))
    blocked = (not success) and any(
        k in json.dumps(res, ensure_ascii=False)
        for k in ["차단", "거부", "replay_detected", "인증", "block"])
    return {"scenario": scenario_id, "success": success,
            "blocked": blocked, "raw": res}


if __name__ == "__main__":
    m = mem_mod.load()
    p = plan(m)
    print("PLAN:", json.dumps(p, ensure_ascii=False))
    for s in p["plan"]:
        print(json.dumps(execute(s), ensure_ascii=False)[:300])
