"""
적응형 공격 오케스트레이터 (관측 → 판단 → 실행 → 피벗)
====================================================
실제 공격자는 고정 각본을 따르지 않는다. 이 오케스트레이터는 킬체인의
여러 벡터를 시도하고, 방어에 막히면(무결성 회복 확인) 다른 벡터로 피벗한다.
모든 경로가 소진되면 종료. §4.6 / §6.2 의 자율 공격 주체.
"""
from src.sim import mumt

# 킬체인 벡터: (이름, 공격유형) — 파괴적→은밀 순으로 시도
VECTORS = [("노골적 장악", "jump"),
           ("외부 GNSS 스푸핑", "spoof"),
           ("은밀 크립", "creep")]
BLOCK_THRESHOLD = 0.80    # 방어 무결성이 이 이상이면 '막혔다'고 판단 → 피벗


def run(defense="resilient", runs=20):
    print(f"적응형 공격 오케스트레이터 vs 방어={defense}")
    log = []
    for name, atk in VECTORS:
        integ, avail = mumt.evaluate(atk, defense, runs=runs)
        blocked = integ >= BLOCK_THRESHOLD
        log.append({"vector": name, "attack": atk,
                    "defender_integrity": round(integ, 3), "blocked": blocked})
        status = "막힘 → 피벗" if blocked else "관통(취약)"
        print(f"  [{name:<14}] 방어무결성 {integ*100:5.1f}% → {status}")
        if not blocked:
            print(f"  → 최적 관통 벡터 발견: '{name}'(방어 무결성 {integ*100:.1f}%). 종료.")
            return {"result": "penetrated", "vector": name, "log": log}
    print("  → 모든 벡터가 막힘. 공격 종료(방어 우세).")
    return {"result": "all_blocked", "log": log}


if __name__ == "__main__":
    run()
