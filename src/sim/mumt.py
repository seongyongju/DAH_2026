"""
MUM-T 신뢰 전파 시뮬레이션 환경 (Trust Propagation Simulator)
============================================================
유무인 복합체계(MUM-T)의 공유 상황도(COP, Common Operating Picture)를
1D 운동학으로 모사한다. 장악된 무인 노드가 '인증된 거짓 위치 보고'를 COP 에
주입하면(신뢰 전파), 방어자는 그 보고를 내용 타당성으로 검증한다.

핵심 지표
  - 무결성(Integrity) : COP 위치가 실제 위치와 오차 ε 이내인 틱 비율
  - 가용성(Availability): 시스템이 '사용 가능한' COP 를 제공한 틱 비율
                          (차단/블랙아웃/장기 표류 시 하락)

공격(attack)      : none | jump(노골적 장악) | creep(은밀 크립) | spoof(외부 GNSS)
방어(defense)     : none | zero_trust | zt_drift | resilient(팀 오버워치)
모델              : idealized(이상화) | realistic(기동·INS 드리프트·간헐 오버워치)

주의: 물리 파라미터는 '모델링 가정'이며, 이 환경은 방어 메커니즘의 성립 조건을
보이는 용도다(실전 수치 아님). 노드 탐지 성능의 실측 근거는 src/detector 참조.
"""
import numpy as np

# ── 환경 파라미터(모델링 가정) ──────────────────────────────────────────
T = 200                # 틱 수
EPS = 5.0              # 무결성 판정: |COP - truth| < EPS
TAU = 8.0             # 순간 타당성 임계: |report - kinematic_pred|
V = 1.0               # 공칭 속도
ATTACK_START = 50     # 공격 시작 틱
JUMP_BIAS = 22.0      # 노골적 장악 바이어스(> TAU)
CREEP_SLOPE = 0.45    # 은밀 크립 틱당 증분(< TAU, 누적)
CUSUM_LIMIT = 30.0    # 드리프트 가드 누적 편차 임계


def _params(realistic):
    """이상화 vs 현실 모델의 잡음/열화 파라미터."""
    if realistic:
        return dict(sigma_maneuver=1.6,   # UAV 기동(예측 불일치)
                    sigma_ins=0.85,       # 거부 후 INS 추측항법 드리프트/틱
                    sigma_ow=2.2,         # 오버워치 정밀도(coarse)
                    p_overwatch=0.70)     # 오버워치 간헐 가용
    return dict(sigma_maneuver=0.0, sigma_ins=0.0, sigma_ow=0.0, p_overwatch=1.0)


def _attack_report(attack, truth, prev_bias, t, rng, start=ATTACK_START):
    """공격이 만들어내는 노드의 '보고 위치'와 갱신된 누적 바이어스."""
    if t < start or attack == "none":
        return truth, 0.0
    if attack == "jump":
        return truth + JUMP_BIAS, JUMP_BIAS
    if attack == "creep":
        b = prev_bias + CREEP_SLOPE
        return truth + b, b
    if attack == "spoof":           # 외부 GNSS 스푸핑(관성과 불일치 → 계층1 탐지 대상)
        return truth + JUMP_BIAS * 0.9, JUMP_BIAS * 0.9
    return truth, 0.0


def run_episode(attack="creep", defense="resilient", realistic=True, seed=0,
                attack_start=ATTACK_START):
    """단일 에피소드 시뮬레이션. (integrity, availability) 반환."""
    rng = np.random.default_rng(seed)
    p = _params(realistic)

    truth = 0.0
    cop = 0.0                 # 방어자가 신뢰하는 COP 위치
    ins = 0.0                 # 거부 시 사용하는 추측항법 추정
    prev_pred = 0.0
    prev_bias = 0.0
    cusum = 0.0
    usable = np.zeros(T, bool)
    correct = np.zeros(T, bool)

    for t in range(T):
        # 실제 위치 전진(+기동 잡음)
        maneuver = rng.normal(0, p["sigma_maneuver"])
        truth += V + maneuver
        # 방어자의 운동학 예측(공칭 속도만 앎)
        pred = prev_pred + V
        # 공격자의 보고
        report, prev_bias = _attack_report(attack, truth, prev_bias, t, rng,
                                           start=attack_start)
        # 관성 추정 전진(드리프트 누적)
        ins += V + rng.normal(0, p["sigma_ins"])

        resid = report - pred
        suspicious = abs(resid) > TAU
        cusum = max(0.0, cusum + resid) if resid > 0 else max(0.0, cusum + resid)
        cusum = abs(cusum)

        # ── 방어 정책별 COP 결정 ──
        if defense == "none":                       # 노드 무조건 신뢰
            cop, usable[t] = report, True
        elif defense == "zero_trust":               # 순간 타당성만
            if suspicious:
                cop, usable[t] = ins, True          # 거부 → INS(표류)
            else:
                cop, usable[t] = report, True
        elif defense == "zt_drift":                 # + 누적 드리프트 가드
            if suspicious or cusum > CUSUM_LIMIT:
                cop, usable[t] = ins, True
                cusum = 0.0
            else:
                cop, usable[t] = report, True
        elif defense == "resilient":                # + 팀 오버워치 재앵커
            if suspicious or cusum > CUSUM_LIMIT:
                if rng.random() < p["p_overwatch"]:
                    cop = truth + rng.normal(0, p["sigma_ow"])  # 독립 출처 재앵커
                    ins = cop                                   # INS 재보정
                    usable[t] = True
                else:
                    cop, usable[t] = ins, False    # 오버워치 부재 → 순간 블랙아웃
                cusum = 0.0
            else:
                cop, usable[t] = report, True
        else:
            cop, usable[t] = report, True

        correct[t] = abs(cop - truth) < EPS
        prev_pred = cop              # 예측 기준은 '수용된 COP'를 따른다

    integrity = correct.mean()
    availability = usable.mean()
    return integrity, availability


def evaluate(attack, defense, realistic=True, runs=40, attack_start=ATTACK_START):
    """다회 평균 (integrity, availability)."""
    I, A = [], []
    for s in range(runs):
        i, a = run_episode(attack, defense, realistic, seed=s,
                           attack_start=attack_start)
        I.append(i); A.append(a)
    return float(np.mean(I)), float(np.mean(A))


ATTACKS = ["none", "jump", "creep", "spoof"]
DEFENSES = ["none", "zero_trust", "zt_drift", "resilient"]


if __name__ == "__main__":
    print("realistic model — integrity / availability (40-run avg)")
    for atk in ATTACKS:
        row = []
        for dfn in DEFENSES:
            i, a = evaluate(atk, dfn)
            row.append(f"{dfn}:{i*100:.0f}/{a*100:.0f}")
        print(f"  {atk:6s} | " + "  ".join(row))
