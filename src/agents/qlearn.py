"""
경량 표기반 Q-learning (순수 numpy, 외부 의존 0)
================================================
자립형(self-contained) RL: 외부 LLM·API·클라우드 의존 없이 로컬에서
보상으로부터 정책을 학습한다 — DDIL/에어갭 전술 엣지 적합.
"""
import numpy as np


class QLearner:
    def __init__(self, n_states, n_actions, alpha=0.2, gamma=0.9,
                 eps=0.2, seed=0):
        self.Q = np.zeros((n_states, n_actions))
        self.alpha, self.gamma, self.eps = alpha, gamma, eps
        self.rng = np.random.default_rng(seed)
        self.n_actions = n_actions

    def act(self, s, explore=True):
        if explore and self.rng.random() < self.eps:
            return int(self.rng.integers(self.n_actions))
        return int(np.argmax(self.Q[s]))

    def update(self, s, a, r, s2):
        best = np.max(self.Q[s2])
        self.Q[s, a] += self.alpha * (r + self.gamma * best - self.Q[s, a])

    def policy(self):
        return np.argmax(self.Q, axis=1)
