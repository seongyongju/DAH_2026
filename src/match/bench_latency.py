"""
RL 판단 지연 벤치마크 — 실시간성 근거
=====================================
자립형 RL 방어 에이전트의 판단(관측→학습정책 조회) 지연을 측정한다.
10 Hz 방어 루프(100 ms/틱) 대비 여유를 계산하고, LLM API 호출(수 초)과 대비한다.
"""
import time
import numpy as np
from src.agents.qlearn import QLearner


def run(iters=2_000_000):
    ql = QLearner(3, 4, seed=0)
    ql.Q = np.random.default_rng(0).random((3, 4))
    states = np.random.default_rng(1).integers(0, 3, size=iters)
    t0 = time.perf_counter()
    acc = 0
    for i in range(iters):
        acc += ql.act(int(states[i]), explore=False)
    dt = time.perf_counter() - t0
    per = dt / iters
    print(f"RL 판단 {iters:,}회: 총 {dt:.2f}s → 판단당 {per*1e6:.3f} µs "
          f"(초당 {1/per:,.0f}회)")
    budget = 0.100    # 10 Hz 방어 루프 = 100 ms/틱
    print(f"10 Hz 방어 루프(100ms) 대비 여유: 약 {budget/per:,.0f}배")
    print(f"참고: LLM API 호출 1~3초 → 매 틱 판단에 약 {1.0/per:,.0f}~{3.0/per:,.0f}배 느림")
    print("⇒ 저지연·반복 판단은 로컬 RL, 고수준 추론은 LLM 상위 계층(하이브리드).")


if __name__ == "__main__":
    run()
