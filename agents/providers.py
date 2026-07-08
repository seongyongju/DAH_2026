"""
LLM 백엔드 추상화 계층 (Pluggable Agent Providers)
==================================================
공격/방어 에이전트의 '두뇌'를 자유롭게 교체할 수 있도록, 단일 인터페이스
    complete(system, user) -> str
뒤에 여러 코딩/추론 에이전트를 붙인다. 실험자는 환경변수 하나로 선택한다.

    AGENT_PROVIDER = anthropic | claude-code | gemini | codex | offline

- anthropic   : Anthropic Python SDK (Claude Opus 4.8)
- claude-code : Claude Code CLI  (claude -p, 헤드리스)
- gemini      : Gemini CLI       (gemini -p)
- codex       : Codex CLI        (codex exec)
- offline     : LLM 없이 결정론 정책(재현용 폴백)

CLI 계열은 로컬에 해당 도구가 설치돼 있어야 하며, 미설치/오류 시 자동으로
offline 폴백으로 강등되어 파이프라인이 끊기지 않는다.
"""
import os
import shutil
import subprocess

DEFAULT_MODEL = "claude-opus-4-8"


class ProviderResult:
    def __init__(self, text, backend, ok=True, note=""):
        self.text = text or ""
        self.backend = backend
        self.ok = ok
        self.note = note


# --------------------------------------------------------------------------
def _anthropic(system, user, model=DEFAULT_MODEL):
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model, max_tokens=1400,
        thinking={"type": "adaptive"},        # Opus 4.8 적응형 사고
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "")
    return ProviderResult(text, "anthropic")


def _run_cli(cmd, stdin_text=None, timeout=120):
    return subprocess.run(
        cmd, input=stdin_text, capture_output=True, text=True, timeout=timeout)


def _claude_code(system, user):
    # Claude Code 헤드리스: 시스템 프롬프트는 --append-system-prompt 로 주입
    if not shutil.which("claude"):
        raise FileNotFoundError("claude CLI not found")
    r = _run_cli(["claude", "-p", user, "--append-system-prompt", system,
                  "--output-format", "text"])
    return ProviderResult(r.stdout.strip(), "claude-code", ok=(r.returncode == 0))


def _gemini(system, user):
    if not shutil.which("gemini"):
        raise FileNotFoundError("gemini CLI not found")
    # Gemini CLI: 시스템+사용자 프롬프트를 결합해 -p 로 전달
    prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
    r = _run_cli(["gemini", "-p", prompt])
    return ProviderResult(r.stdout.strip(), "gemini", ok=(r.returncode == 0))


def _codex(system, user):
    if not shutil.which("codex"):
        raise FileNotFoundError("codex CLI not found")
    # Codex CLI 비대화 실행
    prompt = f"[SYSTEM]\n{system}\n\n[USER]\n{user}"
    r = _run_cli(["codex", "exec", prompt])
    return ProviderResult(r.stdout.strip(), "codex", ok=(r.returncode == 0))


_BACKENDS = {
    "anthropic": _anthropic,
    "claude-code": _claude_code,
    "gemini": _gemini,
    "codex": _codex,
}


def selected_provider():
    p = os.environ.get("AGENT_PROVIDER", "").lower().strip()
    if p:
        return p
    # 하위호환: AGENT_MODE=offline 또는 API 키 유무로 자동 판별
    if os.environ.get("AGENT_MODE") == "offline":
        return "offline"
    return "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "offline"


def complete(system: str, user: str) -> ProviderResult:
    """선택된 백엔드로 추론. 실패 시 offline 신호(ok=False) 반환 →
    호출측(red/blue)이 결정론 폴백을 사용."""
    prov = selected_provider()
    if prov == "offline":
        return ProviderResult("", "offline", ok=False, note="offline mode")
    fn = _BACKENDS.get(prov)
    if not fn:
        return ProviderResult("", prov, ok=False, note=f"unknown provider {prov}")
    try:
        return fn(system, user)
    except Exception as e:
        # 미설치/오류 → offline 폴백으로 강등(파이프라인 지속)
        return ProviderResult("", prov, ok=False, note=f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    print("provider =", selected_provider())
    r = complete("You are a test.", "Reply with the word OK.")
    print("backend =", r.backend, "ok =", r.ok, "note =", r.note)
    print("text =", r.text[:200])
