"""Cliente minimo da API do GitHub para disparar e ler o workflow."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

API = "https://api.github.com"

DICAS = {
    401: "Token inválido, expirado ou revogado. Gere outro e atualize os Secrets.",
    403: "O token não tem permissão. Em Personal access tokens → Actions, marque 'Read and write' "
         "no repositório.",
    404: "Repositório ou workflow não encontrado. Confira owner, repo, workflow e o branch "
         "(o arquivo precisa existir nesse branch).",
    422: "O workflow não aceita estes campos. Provavelmente a versão no GitHub ainda é a antiga, "
         "sem os inputs, ou não tem o gatilho workflow_dispatch.",
}


class ErroGitHub(RuntimeError):
    def __init__(self, status: int, mensagem: str):
        self.status = status
        self.mensagem = mensagem
        dica = DICAS.get(status, "")
        super().__init__(f"GitHub respondeu {status}: {mensagem}" + (f" — {dica}" if dica else ""))


@dataclass(frozen=True)
class RepoConfig:
    token: str
    owner: str
    repo: str
    workflow: str
    ref: str

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"


def repo_de_secrets(segredo) -> RepoConfig | None:
    """Converte st.secrets['github'] em RepoConfig; None se o token nao existe."""
    try:
        token = str(segredo.get("token", "")).strip()
    except Exception:
        return None
    if not token or "COLE" in token.upper():
        return None
    return RepoConfig(
        token=token,
        owner=str(segredo.get("owner", "eralcw")).strip(),
        repo=str(segredo.get("repo", "akad_trainee")).strip(),
        workflow=str(segredo.get("workflow", "update.yml")).strip(),
        ref=str(segredo.get("ref", "main")).strip(),
    )


def _chamar(repo: RepoConfig, caminho: str, metodo: str = "GET", corpo: dict | None = None):
    dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
    req = urllib.request.Request(
        API + caminho,
        data=dados,
        method=metodo,
        headers={
            "Authorization": f"Bearer {repo.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "akad-ses-dashboard",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            texto = r.read().decode("utf-8")
            return r.status, (json.loads(texto) if texto else {})
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", errors="replace")
        try:
            mensagem = json.loads(bruto).get("message", bruto)
        except Exception:
            mensagem = bruto
        raise ErroGitHub(e.code, str(mensagem)[:300]) from e
    except urllib.error.URLError as e:
        raise ErroGitHub(0, f"falha de rede ao falar com o GitHub: {e.reason}") from e


def disparar(repo: RepoConfig, inputs: dict) -> bool:
    corpo = {
        "ref": repo.ref,
        "inputs": {k: str(v) for k, v in inputs.items() if v is not None},
    }
    status, _ = _chamar(
        repo,
        f"/repos/{repo.slug}/actions/workflows/{repo.workflow}/dispatches",
        metodo="POST",
        corpo=corpo,
    )
    return status in (201, 204)


def execucoes(repo: RepoConfig, limite: int = 6) -> list[dict]:
    _, dados = _chamar(
        repo,
        f"/repos/{repo.slug}/actions/workflows/{repo.workflow}/runs?per_page={limite}",
    )
    return dados.get("workflow_runs", [])


def url_actions(repo: RepoConfig) -> str:
    return f"https://github.com/{repo.slug}/actions/workflows/{repo.workflow}"


def em_andamento(execucoes_: list[dict]) -> bool:
    return any(r.get("status") in {"queued", "in_progress", "requested", "waiting"} for r in execucoes_)


def diagnostico(repo: RepoConfig) -> list[dict]:
    """Testa token, repositorio e workflow, na ordem, sem disparar nada."""
    etapas: list[dict] = []

    def registrar(nome: str, ok: bool, detalhe: str):
        etapas.append({"etapa": nome, "ok": ok, "detalhe": detalhe})

    try:
        _, usuario = _chamar(repo, "/user")
        registrar("Token válido", True, f"autenticado como {usuario.get('login', '?')}")
    except ErroGitHub as e:
        registrar("Token válido", False, str(e))
        return etapas

    try:
        _, dados = _chamar(repo, f"/repos/{repo.slug}")
        registrar("Repositório acessível", True, f"{repo.slug} (branch padrão: {dados.get('default_branch', '?')})")
    except ErroGitHub as e:
        registrar("Repositório acessível", False, str(e))
        return etapas

    try:
        _, wf = _chamar(repo, f"/repos/{repo.slug}/actions/workflows/{repo.workflow}")
        estado = wf.get("state", "?")
        registrar(
            "Workflow encontrado",
            estado == "active",
            f"{wf.get('path', repo.workflow)} · estado: {estado}",
        )
    except ErroGitHub as e:
        registrar("Workflow encontrado", False, str(e))
        return etapas

    try:
        _, arq = _chamar(repo, f"/repos/{repo.slug}/contents/.github/workflows/{repo.workflow}?ref={repo.ref}")
        registrar("Arquivo no branch", True, f"{arq.get('path')} em {repo.ref}")
    except ErroGitHub as e:
        registrar("Arquivo no branch", False, str(e))

    return etapas
