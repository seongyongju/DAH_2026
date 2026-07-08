"""
현실 모델 효능 — 방어 구성 × 공격별 무결성/가용성
=================================================
이상화(100%)는 메커니즘 실증일 뿐이다. 현실 요소(UAV 기동·거부 후 INS
추측항법 드리프트·간헐 오버워치)를 넣어 '정직한 효능'을 재측정한다.
"""
from src.sim import mumt


def run(runs=40):
    print("현실 모델 — 무결성% / 가용성% ({}회 평균)".format(runs))
    header = f"{'공격＼방어':<10} | " + " | ".join(f"{d:>16}" for d in mumt.DEFENSES)
    print(header)
    table = {}
    for atk in mumt.ATTACKS:
        cells = []
        for dfn in mumt.DEFENSES:
            i, a = mumt.evaluate(atk, dfn, runs=runs)
            table[(atk, dfn)] = (i, a)
            cells.append(f"{i*100:>6.1f}/{a*100:<5.1f}   ")
        print(f"{atk:<10} | " + " | ".join(f"{c:>16}" for c in cells))

    print("\n핵심 해석:")
    zt = table[("jump", "zero_trust")][0] * 100
    res = table[("jump", "resilient")][0] * 100
    creep = table[("creep", "resilient")][0] * 100
    print(f"  - 지속 장악(jump) 시 zero_trust 단독 무결성 ≈ {zt:.0f}% → 거부 후 INS 표류로 붕괴")
    print(f"  - +팀 이중화(resilient)는 {res:.0f}% 로 회복 → 팀 이중화는 필수(선택 아님)")
    print(f"  - 가장 약한 지점은 은밀 크립(creep, resilient {creep:.0f}%) — 숨기지 않고 명시")
    return table


if __name__ == "__main__":
    run()
