"""
가용성은 곱셈 계수다 — 일반 IT식 대응이 방산에서 자멸함을 실증
==============================================================
대회 채점은 총점 = (공격 + 방어) × 가용성 구조로, 가용성이 곱셈 계수다.
따라서 위협 탐지 시 시스템을 꺼버리는 IT식 격리/차단(shutdown)은 가용성을
0으로 만들어 유효 방어가 0이 되는 '자해'가 된다.

유효 방어 = 무결성 × 가용성 (COP 가 정확하면서 '동시에' 가용한 비율).
지속 장악(persistent takeover, t=0부터) 하에서 대응 방식을 비교한다.
"""
from src.sim import mumt


def run(runs=40):
    # 지속 장악 = jump 공격을 t=0 부터
    rows = []

    # IT식: 위협 탐지 시 시스템 차단 → 가용성 0 (무결성은 보존한다 쳐도 유효 0)
    i_it, _ = mumt.evaluate("jump", "zero_trust", runs=runs, attack_start=0)
    rows.append(("IT식: 격리/차단(shutdown)", i_it, 0.0))

    # 완만저하(graceful): 살아있으나 노드 신뢰 → COP 오염
    i_g, a_g = mumt.evaluate("jump", "none", runs=runs, attack_start=0)
    rows.append(("완만저하(graceful)", i_g, a_g))

    # Zero-Trust COP만: 거부 후 표류로 가용성/무결성 붕괴
    i_z, a_z = mumt.evaluate("jump", "zero_trust", runs=runs, attack_start=0)
    rows.append(("Zero-Trust COP만", i_z, a_z))

    # +팀 이중화(resilient): 무결성·가용성 함께 보존
    i_r, a_r = mumt.evaluate("jump", "resilient", runs=runs, attack_start=0)
    rows.append(("+팀 이중화(resilient)", i_r, a_r))

    print("지속 장악 하 대응 비교 (현실 모델, {}회 평균)".format(runs))
    print(f"{'대응 방식':<26} | {'무결성%':>7} | {'가용성%':>7} | {'유효방어%':>8}")
    for name, i, a in rows:
        eff = i * a * 100
        print(f"{name:<26} | {i*100:>7.1f} | {a*100:>7.1f} | {eff:>8.1f}")
    print("\n→ IT식 차단은 유효 방어 0(자해). resilient(팀 이중화)만이 무결성·가용성을 함께 살린다.")
    return rows


if __name__ == "__main__":
    run()
