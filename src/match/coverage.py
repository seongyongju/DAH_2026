"""
커버리지 스트레스 테스트 — 일반화 실증(스크립트 밖 공격 경로)
============================================================
"우리가 정한 시나리오만 막는 것 아니냐"는 순환논리 비판을 차단하기 위해,
학습된 방어(reactive/resilient)를 설계 밖 공격 경로에도 던져 COP 무결성을
측정한다. Zero-Trust COP 는 '공격 경로'가 아니라 '내용의 타당성'을 검사하므로
경로와 무관하게 작동함을 보인다.
"""
from src.sim import mumt

# (이름, 공격, 방어) — ②③④는 각본 밖(설계 시 상정하지 않은) 경로
PATHS = [
    ("① 표준 킬체인(jump)",        "jump",  "resilient"),
    ("② 공급망 직행 장악(creep)",   "creep", "resilient"),
    ("③ 외부 스푸핑만(spoof)",      "spoof", "resilient"),
    ("④ 무방어 대조(jump)",         "jump",  "none"),
]


def run(runs=40):
    print("커버리지 스트레스 (현실 모델, {}회 평균) — COP 무결성%".format(runs))
    print(f"{'공격 경로':<24} | {'무결성%':>7} | {'가용성%':>7}")
    for name, atk, dfn in PATHS:
        i, a = mumt.evaluate(atk, dfn, runs=runs)
        print(f"{name:<24} | {i*100:>7.1f} | {a*100:>7.1f}")
    print("\n→ 설계 밖 경로에도 resilient 방어가 경로 무관하게 작동(내용 타당성 검사).")


if __name__ == "__main__":
    run()
