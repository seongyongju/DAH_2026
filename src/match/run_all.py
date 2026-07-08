"""
전체 실험 재현 러너 — 보고서 §5·§6 의 모든 수치를 한 번에 재생산
================================================================
    python3 -m src.match.run_all
"""
from src.match import it_vs_defense, realistic_eval, coverage, bench_latency
from src.agents import self_play, adaptive_self_play, orchestrator
from src.detector import gnss


def main():
    sep = lambda t: print("\n" + "=" * 64 + f"\n[{t}]\n" + "=" * 64)
    sep("가용성 곱셈 계수 — IT식 대응의 자멸 (src.match.it_vs_defense)")
    it_vs_defense.run()
    sep("현실 모델 효능 (src.match.realistic_eval)")
    realistic_eval.run()
    sep("커버리지 스트레스 — 일반화 (src.match.coverage)")
    coverage.run()
    sep("자가대전 공진화 (src.agents.self_play)")
    self_play.run()
    sep("반응형 방어 정책 학습 (src.agents.adaptive_self_play)")
    adaptive_self_play.run()
    sep("적응형 공격 오케스트레이터 (src.agents.orchestrator)")
    orchestrator.run()
    sep("신호레벨 탐지의 근본 한계 (src.detector.gnss)")
    gnss.run()
    sep("RL 판단 지연 벤치마크 (src.match.bench_latency)")
    bench_latency.run()


if __name__ == "__main__":
    main()
