"""
오케스트레이터 (방어 중심 공방 루프 + 학습)
==========================================
본 시스템의 메인은 '방어(탐지·차단·복구) 아키텍처'다. 공격 에이전트는 방어의
사각지대를 드러내는 보조 역할을 하고, 방어 파이프라인이 라운드를 거치며 커버리지를
넓혀 공격을 무력화하는 과정을 정량 측정한다.

매 라운드:
  1) (보조) Red : 아직 안 막힌 취약점 우선 탐침 → 시나리오 실행
  2) (메인) Blue: DETECT → DECIDE → BLOCK → RECOVER 파이프라인 수행
  3) 적용된 방어가 다음 라운드부터 해당 시나리오를 '차단'으로 전환
  4) 결과·학습을 공유 메모리에 누적

방어 지표:
  - 탐지율(detection rate)           : 실제 공격 대비 탐지 건수
  - 차단 커버리지(defense coverage)   : 적용된 통제 수 / 전체 8
  - 평균 차단 소요 라운드(MTTB)        : 시나리오가 처음 차단되기까지 걸린 라운드
  - 복구 수행(recovery)               : 라운드별 복구 액션 수

사용:  python orchestrator.py --rounds 5 [--max-fixes 2]
       AGENT_PROVIDER=claude-code|gemini|codex|anthropic|offline 로 두뇌 선택
결과:  round_report.json + 콘솔 요약표
"""
import os
import json
import argparse

import tools
import memory as mem_mod
import red_agent
import blue_agent
import providers

# 시나리오 → 이를 무력화하는 방어 통제(하나라도 적용되면 차단)
DEFENSE_FOR = {
    "S1": {"patch_sqli", "rbac_idor"},
    "S2": {"mavlink_signing", "geofence_enforce"},
    "S3": {"enable_satcom_replay_protection"},
    "S4": {"verify_firmware_sig"},
    "S5": {"require_mqtt_auth"},
}


def defense_blocks(scenario_id, active_defenses):
    return bool(DEFENSE_FOR[scenario_id] & set(active_defenses))


def run(rounds=5, offline=False, max_fixes=2):
    """max_fixes: 라운드당 Blue 가 신규 대응(remediate)할 수 있는 시나리오 수 상한.
    현실의 유한한 대응 역량(패치·배포 소요)을 모사한다."""
    if offline:
        os.environ["AGENT_MODE"] = "offline"
    print(f"[orchestrator] agent provider = {providers.selected_provider()}")

    mem = mem_mod.load()
    active_defenses = set(mem.get("defenses_applied", []))
    first_block_round = {}   # 시나리오별 최초 차단 라운드(MTTB 산출)
    history = []

    for r in range(1, rounds + 1):
        mem["rounds"] += 1
        rn = mem["rounds"]
        round_log = {"round": rn, "attacks": [], "defense": {}}

        # 1) (보조) Red 계획 & 실행 — 방어 사각지대 탐침
        p = red_agent.plan(mem)
        round_log["red_plan"] = p
        succeeded = set()
        for scen in p["plan"]:
            outcome = red_agent.execute(scen)
            if defense_blocks(scen, active_defenses):   # 기적용 방어가 차단
                outcome["success"] = False
                outcome["blocked"] = True
                outcome["note"] = "기적용 방어 통제에 의해 차단"
            if outcome["success"]:
                succeeded.add(scen)
            note = outcome["raw"].get("impact", "") if "raw" in outcome else ""
            mem = mem_mod.record_attack(
                mem, scen, outcome["success"], outcome["blocked"], note)
            round_log["attacks"].append(
                {"scenario": scen, "success": outcome["success"],
                 "blocked": outcome["blocked"], "impact": note[:80]})

        # 2) (메인) Blue 방어 파이프라인: DETECT→DECIDE→BLOCK→RECOVER
        logs = tools.read_logs("all", tail=80)
        result = blue_agent.defend(logs, active_defenses, succeeded, max_fixes)
        for c in result["applied_controls"]:
            active_defenses.add(c)
            mem = mem_mod.add_defense(mem, c)
        for s in result["remediated_scenarios"]:
            first_block_round.setdefault(s, rn)
        round_log["defense"] = result

        # 라운드 지표
        n_att = len(round_log["attacks"])
        succ = len(succeeded)
        blk = sum(1 for a in round_log["attacks"] if a["blocked"])
        n_det = len(result["detections"])
        round_log["metrics"] = {
            "attacks": n_att,
            "attack_success": succ,
            "blocked": blk,
            "detected": n_det,
            "detection_rate": f"{n_det}/{n_att}",
            "defense_coverage": f"{len(active_defenses)}/8",
            "recovery_actions": sum(len(x["recovery_actions"])
                                    for x in result["recovery"]),
            "backend": result["backend"],
        }
        mem_mod.add_lesson(
            mem, f"R{rn}: 탐지 {n_det}/{n_att}, 성공 {succ}, 차단 {blk}, "
                 f"방어 {len(active_defenses)}/8")
        history.append(round_log)
        mem_mod.save(mem)

        # 콘솔 출력
        print(f"\n===== Round {rn} (backend={result['backend']}) =====")
        for a in round_log["attacks"]:
            tag = "성공" if a["success"] else ("차단" if a["blocked"] else "실패")
            print(f"  [공격] {a['scenario']} [{tag}] {a['impact']}")
        print(f"  [탐지] {n_det}/{n_att}건")
        if result["remediated_scenarios"]:
            print(f"  [차단] {result['remediated_scenarios']} → "
                  f"통제 {result['applied_controls']}")
            for rec in result["recovery"]:
                print(f"  [복구] {rec['scenario']}: {rec['recovery_actions']}")
        print(f"  [커버리지] 누적 {len(active_defenses)}/8")

    # MTTB 계산
    mttb = {s: first_block_round.get(s) for s in DEFENSE_FOR}
    report = {"provider": providers.selected_provider(),
              "rounds": history, "mttb_round": mttb, "final_memory": mem}
    out = os.path.join(os.path.dirname(__file__), "round_report.json")
    with open(out, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n[+] 리포트 저장: {out}")
    _summary(history, mttb)
    return report


def _summary(history, mttb):
    print("\n라운드별 요약 (탐지 / 공격성공 / 차단 / 방어커버리지)")
    print("Round | 탐지  | 성공 | 차단 | 방어커버리지")
    for h in history:
        m = h["metrics"]
        print(f"  {h['round']:>3} | {m['detection_rate']:>5} | "
              f"{m['attack_success']:>3}  | {m['blocked']:>3}  | "
              f"{m['defense_coverage']}")
    blocked = {s: r for s, r in mttb.items() if r}
    avg = sum(blocked.values()) / len(blocked) if blocked else 0
    print(f"\n평균 차단 소요 라운드(MTTB): {avg:.2f}  세부={mttb}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--offline", action="store_true",
                    help="LLM 없이 결정론 정책으로 실행(AGENT_PROVIDER=offline 과 동일)")
    ap.add_argument("--max-fixes", type=int, default=2,
                    help="라운드당 Blue 신규 대응 시나리오 상한(대응 역량 모사)")
    a = ap.parse_args()
    run(a.rounds, a.offline, a.max_fixes)
