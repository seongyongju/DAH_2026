"""
상태조건부(반응형) 방어 에이전트 — STATE(관측)의 가치
====================================================
방어 에이전트가 매 틱 '관측(monitor)'을 보고 방어 자세를 선택하는
상태조건부 RL. resilient(팀 오버워치)는 희소 자산을 태스킹하므로 평시엔
비용이 든다. 따라서 평시엔 값싼 방어로 자산을 아끼고, 위협 징후 시 escalate.

관측 상태: {조용(quiet), 의심(suspect), 경보(alarm)}
행동:      {zero_trust, resilient}   (평시 절약 vs 위협 대응)
비교:      '항상 resilient'(무상태) 대비 반응형이 태스킹 비용을 아껴 보상 개선.
"""
import numpy as np
from src.sim import mumt
from src.agents.qlearn import QLearner

STATES = ["quiet", "suspect", "alarm"]
ACTIONS = ["zero_trust", "resilient"]
TASKING_COST = 0.12   # resilient(오버워치) 태스킹 비용(평시 자산 소모)


def _observe(atk, t):
    """단순 관측 모델: 공격 유형/시점으로 위협 등급 산출."""
    if atk == "none" or t < mumt.ATTACK_START:
        return 0   # quiet
    if atk == "creep":
        return 1   # suspect (은밀 → 약한 신호)
    return 2       # alarm (jump/spoof → 강한 신호)


def reward(atk, dfn_action, runs=8):
    integ, avail = mumt.evaluate(atk, dfn_action, runs=runs)
    r = integ * avail
    if dfn_action == "resilient":
        r -= TASKING_COST      # 태스킹 비용
    return r


def train(episodes=3000, seed=0):
    ql = QLearner(len(STATES), len(ACTIONS), eps=0.2, seed=seed)
    rng = np.random.default_rng(seed)
    atk_types = ["none", "jump", "creep", "spoof"]
    for ep in range(episodes):
        atk = atk_types[int(rng.integers(len(atk_types)))]
        t = int(rng.integers(mumt.T))
        s = _observe(atk, t)
        a = ql.act(s)
        r = reward(atk, ACTIONS[a])
        ql.update(s, a, r, s)
    return ql


def run():
    ql = train()
    pol = ql.policy()
    print("반응형 방어 에이전트가 학습한 정책(각본 아님):")
    print(f"{'관측 상태':<10} | {'학습된 자세':<12} | 의미")
    meaning = {"quiet": "값싼 감시, 희소 자산 아낌",
               "suspect": "위협 징후 → 오버워치 태스킹",
               "alarm": "위협 확실 → 오버워치 태스킹"}
    for i, s in enumerate(STATES):
        print(f"{s:<10} | {ACTIONS[pol[i]]:<12} | {meaning[s]}")

    # 반응형 이득: 평시 reactive vs 항상 resilient
    r_react = reward("none", ACTIONS[pol[0]], runs=40)
    r_always = reward("none", "resilient", runs=40)
    print(f"\n반응형 이득(평시): reactive={r_react:.2f} vs 항상resilient={r_always:.2f}"
          f"  → {'reactive 우위(자산 절약)' if r_react > r_always else '동등'}")


if __name__ == "__main__":
    run()
