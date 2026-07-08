"""
공유 학습 메모리 (Red/Blue 공통 지식 베이스)
=============================================
매 라운드 종료 후 '무엇이 통했고 무엇이 막혔는지'를 시나리오별로
누적한다. 다음 라운드에서 Red 는 성공률 높은 순서로 공격을 재배치하고,
Blue 는 반복 탐지 패턴을 우선 차단한다 → 라운드가 진행될수록
공격·방어 모두 효율과 성공률이 향상되는 피드백 루프.
"""
import os
import json
import threading

MEM_PATH = os.environ.get("AGENT_MEMORY", os.path.join(
    os.path.dirname(__file__), "knowledge_base.json"))
_lock = threading.Lock()

_DEFAULT = {
    "rounds": 0,
    "scenarios": {          # 시나리오별 통계
        s: {"attempts": 0, "success": 0, "blocked": 0,
            "last_result": None, "notes": []}
        for s in ["S1", "S2", "S3", "S4", "S5"]
    },
    "defenses_applied": [],  # 누적 적용 방어 통제
    "lessons": [],           # 자연어 교훈(에이전트가 기록)
}


def load():
    with _lock:
        if os.path.exists(MEM_PATH):
            with open(MEM_PATH) as f:
                return json.load(f)
        return json.loads(json.dumps(_DEFAULT))


def save(mem):
    with _lock:
        with open(MEM_PATH, "w") as f:
            json.dump(mem, f, ensure_ascii=False, indent=2)


def record_attack(mem, scenario_id, success, blocked, note=""):
    sc = mem["scenarios"][scenario_id]
    sc["attempts"] += 1
    if success:
        sc["success"] += 1
    if blocked:
        sc["blocked"] += 1
    sc["last_result"] = "success" if success else ("blocked" if blocked else "fail")
    if note:
        sc["notes"].append(note)
        sc["notes"] = sc["notes"][-5:]
    return mem


def success_rate(mem, scenario_id):
    sc = mem["scenarios"][scenario_id]
    return sc["success"] / sc["attempts"] if sc["attempts"] else 0.5


def attack_priority(mem):
    """성공률(및 미시도 우선) 기준으로 다음 공격 순서를 정한다."""
    order = sorted(
        mem["scenarios"].keys(),
        key=lambda s: (-success_rate(mem, s),
                       mem["scenarios"][s]["attempts"]))
    return order


def add_defense(mem, control):
    if control not in mem["defenses_applied"]:
        mem["defenses_applied"].append(control)
    return mem


def add_lesson(mem, text):
    mem["lessons"].append(text)
    mem["lessons"] = mem["lessons"][-20:]
    return mem


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=2))
