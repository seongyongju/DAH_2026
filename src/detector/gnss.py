"""
GNSS 스푸핑 탐지기 — 신호레벨 탐지의 '근본 한계' 실증
====================================================
신호레벨 ML 스푸핑 탐지는 동일분포에서 87~99% 정확도를 보고하지만, 이는
'이미 본 공격'에 대한 것이다. 본 모듈은 leave-one-attack-type-out 검증으로
미학습(처음 보는) 스푸핑 유형에 대한 재현율이 급락함을 보인다 — 이는 특정
모델 결함이 아니라 단일 센서 신호레벨 탐지의 근본 한계다.

데이터: 실제 공개 데이터셋(Mendeley z7dj3yyzt8, UND)을 권장하나, 배포/용량
문제로 기본은 '구조적 합성 데이터(모델링 가정)'를 생성해 현상을 재현한다.
--data <path.csv> 로 실측 데이터셋 경로를 주면 그것을 사용한다.
(합성은 3개 스푸핑 유형이 서로 다른 피처 분포를 갖도록 설계하여, 유형 간
일반화 붕괴라는 '메커니즘'을 재현한다.)
"""
import numpy as np
from sklearn.ensemble import RandomForestClassifier

FEATURES = 6   # 상관기 피처(모사): C/N0, 상관피크, AGC, 도플러잔차 등


def synth(n_per=1500, seed=0):
    """정상 + 3개 스푸핑 유형의 구조적 합성 데이터."""
    rng = np.random.default_rng(seed)
    X, y, atype = [], [], []
    # 정상(clean)
    X.append(rng.normal(0.0, 1.0, (n_per, FEATURES))); y += [0] * n_per; atype += [-1] * n_per
    # 유형별로 '직교하는' 단일 피처 축만 강하게 흔든다 → 각 스푸핑 기법이
    # 서로 다른 고유 시그니처를 갖는 현실을 모사. 한 유형을 학습에서 빼면
    # 분류기는 그 유형의 시그니처 축을 학습하지 못해 미학습 유형을 못 잡는다.
    for k in range(3):
        Xk = rng.normal(0.0, 1.0, (n_per, FEATURES))
        Xk[:, k] += rng.normal(4.0, 0.5, n_per)          # 유형 k 고유 시그니처(직교)
        X.append(Xk); y += [1] * n_per; atype += [k] * n_per
    return np.vstack(X), np.array(y), np.array(atype)


def load_csv(path):
    import csv
    rows = list(csv.reader(open(path)))
    hdr = rows[0]
    data = np.array(rows[1:], float)
    # 관례: 마지막 2열 = label, attack_type
    return data[:, :-2], data[:, -2].astype(int), data[:, -1].astype(int)


def shuffle_eval(X, y, seed=0):
    """낙관적 상한: 모든 유형을 학습에 포함(셔플)."""
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(y))
    cut = int(0.7 * len(y))
    tr, te = idx[:cut], idx[cut:]
    clf = RandomForestClassifier(n_estimators=80, random_state=seed).fit(X[tr], y[tr])
    pred = clf.predict(X[te])
    spoof = y[te] == 1
    recall = (pred[spoof] == 1).mean() if spoof.any() else 0
    return recall


def leave_one_type_out(X, y, atype, seed=0):
    """객관 검증: 한 스푸핑 유형을 학습 제외 → 그 유형만으로 시험."""
    recalls = {}
    for held in sorted(t for t in set(atype) if t >= 0):
        tr = (atype != held)                       # 보류 유형 제외(정상+타 유형 학습)
        te = (atype == held)                       # 미학습 유형만 시험
        clf = RandomForestClassifier(n_estimators=80,
                                     random_state=seed).fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        recalls[held] = (pred == 1).mean()         # 미학습 스푸핑 탐지 재현율
    return recalls


def run(data=None):
    if data:
        X, y, atype = load_csv(data)
        src = f"실측 데이터셋({data})"
    else:
        X, y, atype = synth()
        src = "구조적 합성 데이터(모델링 가정)"
    print(f"GNSS 스푸핑 탐지 일반화 검증 — {src}")
    sh = shuffle_eval(X, y)
    print(f"  셔플(모든 유형 학습, 낙관적 상한) 재현율 : {sh*100:.1f}%")
    lo = leave_one_type_out(X, y, atype)
    for k, r in lo.items():
        print(f"  미학습 유형 {k} 재현율               : {r*100:.1f}%")
    print(f"  미학습 유형 평균 재현율               : {np.mean(list(lo.values()))*100:.1f}%")
    print("\n→ 처음 보는 스푸핑은 '더 나은 분류기'로 풀리지 않는다(신호레벨 탐지의 근본 한계).")
    print("  ⇒ 방어를 공격 시그니처가 아닌 '교차센서 물리일관성 + COP 내용검증'으로 올린다(§5.2).")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="실측 CSV 경로(없으면 합성)")
    a = ap.parse_args()
    run(a.data)
