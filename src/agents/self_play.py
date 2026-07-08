"""
자가대전 공진화 (무상태 self-play, 제로섬)
==========================================
공격·방어 에이전트를 서로 상대로 동시 학습시킨다(둘 다 Q-learning).
보상 = 방어자의 COP 무결성(공격자는 이를 최소화, 제로섬). 각본 없이:
  - 방어자는 none → resilient 로 이동
  - 공격자는 none → jump → creep(은밀 크립) 으로 이동
하며 (creep, resilient) 균형으로 수렴함을 보인다.
"""
import numpy as np
from src.sim import mumt
from src.agents.qlearn import QLearner

ATTACKS = ["none", "jump", "creep", "spoof"]
DEFENSES = ["none", "zero_trust", "zt_drift", "resilient"]


def payoff_matrix(runs=40):
    """공격×방어 별 방어 보상(무결성) 행렬(현실 모델)."""
    M = np.zeros((len(ATTACKS), len(DEFENSES)))
    for i, atk in enumerate(ATTACKS):
        for j, dfn in enumerate(DEFENSES):
            integ, avail = mumt.evaluate(atk, dfn, runs=runs)
            # 방어 보상 = 무결성 × 가용성 (가용성 곱셈 계수 반영)
            M[i, j] = integ * avail
    return M


def train(episodes=4000, runs=8, seed=0):
    M = payoff_matrix(runs=runs)   # 학습 신호로 쓸 게임 행렬
    # 단일 상태(무상태) 밴딧형 self-play
    atk = QLearner(1, len(ATTACKS), eps=0.25, seed=seed)
    dfn = QLearner(1, len(DEFENSES), eps=0.25, seed=seed + 1)
    rng = np.random.default_rng(seed)
    traj = []
    for ep in range(episodes):
        a = atk.act(0); d = dfn.act(0)
        payoff = M[a, d] + rng.normal(0, 0.02)   # 방어 보상
        dfn.update(0, d, payoff, 0)              # 방어자: 최대화
        atk.update(0, a, -payoff, 0)             # 공격자: 최소화(제로섬)
        if ep % 500 == 0:
            traj.append((ep, ATTACKS[int(np.argmax(atk.Q[0]))],
                         DEFENSES[int(np.argmax(dfn.Q[0]))]))
    a_star = ATTACKS[int(np.argmax(atk.Q[0]))]
    d_star = DEFENSES[int(np.argmax(dfn.Q[0]))]
    return M, a_star, d_star, traj


def run():
    M, a_star, d_star, traj = train()
    print("방어 보상 행렬 (무결성×가용성, 현실 모델)")
    print(f"{'공격＼방어':<10} | " + " | ".join(f"{d:>10}" for d in DEFENSES))
    for i, atk in enumerate(ATTACKS):
        print(f"{atk:<10} | " + " | ".join(f"{M[i,j]:>10.2f}" for j in range(len(DEFENSES))))
    print("\n공진화 궤적(에피소드: 공격최적/방어최적):")
    for ep, a, d in traj:
        print(f"  ep{ep:>5}: 공격={a:<6} 방어={d}")
    print(f"\n수렴 균형: 공격={a_star}, 방어={d_star}")
    print("→ 완전 방어 앞에서 최적 공격은 '가장 파괴적'이 아니라 '가장 은밀한'(creep) 것이다.")


if __name__ == "__main__":
    run()
