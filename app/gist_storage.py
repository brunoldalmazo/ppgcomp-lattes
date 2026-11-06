"""
Persistência opcional de JSON em um GitHub Gist secreto.

O módulo é usado por `qualis_overrides` e `publication_flags` para
manter os dados entre deploys do Render, cujo sistema de arquivos é
efêmero.

Regras de segurança:

- Se GITHUB_TOKEN ou GIST_ID não estiverem definidos, as funções
  apenas informam "não configurado" e os chamadores continuam usando
  o arquivo local.
- Nenhuma função levanta exceção. Falhas de rede, autenticação,
  permissão ou formato são registradas em log e tratadas como
  indisponibilidade do Gist, para que o GitHub nunca derrube as
  rotas da API.
- O token nunca é escrito em log.
"""

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)


API_URL = "https://api.github.com/gists/{gist_id}"

# Timeout curto: a rota não deve ficar pendurada esperando o GitHub.
TIMEOUT_SECONDS = float(
    os.getenv("GIST_TIMEOUT_SECONDS", "5")
)

# Os arquivos deste projeto são pequenos; o limite só serve de proteção.
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

USER_AGENT = "ppgcomp-lattes"

# O Gist é lido por muitas publicações durante uma avaliação. Sem cache,
# cada leitura viraria uma chamada HTTP (e um timeout inteiro quando o
# GitHub estiver inacessível).
CACHE_TTL_SECONDS = float(
    os.getenv("GIST_CACHE_TTL_SECONDS", "30")
)

_cache = {}
_cache_lock = threading.Lock()

# Gravações que falharam no Gist. Enquanto existirem, as leituras usam
# esse estado local (mais novo) em vez de reler um Gist desatualizado.
_pending = {}
_pending_lock = threading.Lock()


def _cache_get(filename):
    """Retorna (dado, acertou_cache)."""

    with _cache_lock:
        entry = _cache.get(filename)

    if entry is None:
        return None, False

    stored_at, data = entry

    if time.monotonic() - stored_at > CACHE_TTL_SECONDS:
        return None, False

    return data, True


def _cache_set(filename, data):
    with _cache_lock:
        _cache[filename] = (
            time.monotonic(),
            data,
        )


def clear_cache():
    """Descarta o cache e as gravações pendentes em memória."""

    with _cache_lock:
        _cache.clear()

    with _pending_lock:
        _pending.clear()


def _pending_get(filename):
    with _pending_lock:
        return _pending.get(filename)


def _pending_set(filename, data):
    with _pending_lock:
        _pending[filename] = data


def _pending_clear(filename):
    with _pending_lock:
        _pending.pop(filename, None)


def _config():
    """
    Retorna (token, gist_id) quando a integração está configurada,
    ou None caso contrário.
    """

    token = (os.getenv("GITHUB_TOKEN") or "").strip()
    gist_id = (os.getenv("GIST_ID") or "").strip()

    if not token or not gist_id:
        return None

    return token, gist_id


def is_configured():
    """Indica se as variáveis de ambiente do Gist estão presentes."""
    return _config() is not None


def _log_error(action, filename, exc):
    """
    Loga a falha sem despejar traceback em toda requisição.

    O traceback completo fica disponível em nível DEBUG.
    """

    detail = f"{type(exc).__name__}: {exc}"

    if isinstance(exc, urllib.error.HTTPError):
        detail = f"HTTP {exc.code} ({exc.reason})"

    logger.warning(
        "Gist indisponível ao %s %s (%s). "
        "Usando persistência local como fallback.",
        action,
        filename,
        detail,
    )

    logger.debug(
        "Detalhes da falha no Gist ao %s %s",
        action,
        filename,
        exc_info=True,
    )


def _request(url, token, method="GET", payload=None):
    """
    Executa uma chamada à API do GitHub e devolve o JSON decodificado.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        # A API do GitHub rejeita requisições sem User-Agent.
        "User-Agent": USER_AGENT,
    }

    data = None

    if payload is not None:
        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT_SECONDS,
    ) as response:

        body = response.read(
            MAX_RESPONSE_BYTES + 1
        )

    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(
            "Resposta do Gist maior que o limite permitido."
        )

    return json.loads(
        body.decode("utf-8")
    )


def _download_raw(url, token):
    """Baixa o conteúdo completo quando a API o devolve truncado."""

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": USER_AGENT,
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=TIMEOUT_SECONDS,
    ) as response:

        body = response.read(
            MAX_RESPONSE_BYTES + 1
        )

    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError(
            "Conteúdo do Gist maior que o limite permitido."
        )

    return body.decode("utf-8")


def load_json(filename):
    """
    Lê `filename` do Gist e devolve o objeto JSON.

    Retorna None quando o Gist não está configurado, o arquivo não
    existe ou qualquer etapa falha. Nesse caso o chamador deve usar
    o arquivo local.
    """

    config = _config()

    if config is None:
        return None

    pending = _pending_get(filename)

    if pending is not None:
        # Há alteração local ainda não sincronizada com o Gist.
        return pending

    cached, hit = _cache_get(filename)

    if hit:
        return cached

    token, gist_id = config

    try:
        payload = _request(
            API_URL.format(gist_id=gist_id),
            token,
        )

        files = payload.get("files") or {}

        if not isinstance(files, dict):
            _cache_set(filename, None)
            return None

        file_info = files.get(filename)

        if not isinstance(file_info, dict):
            # Primeira execução: o arquivo ainda não existe no Gist.
            logger.info(
                "Gist não possui %s; usando arquivo local.",
                filename,
            )
            _cache_set(filename, None)
            return None

        content = file_info.get("content")

        if file_info.get("truncated") and file_info.get("raw_url"):
            content = _download_raw(
                file_info["raw_url"],
                token,
            )

        if not isinstance(content, str):
            _cache_set(filename, None)
            return None

        data = json.loads(content)

    except Exception as exc:  # noqa: BLE001 - falha do Gist é fallback
        _log_error(
            "ler",
            filename,
            exc,
        )
        # Cache negativo evita repetir o timeout em cada publicação.
        _cache_set(filename, None)
        return None

    if not isinstance(data, dict):
        _cache_set(filename, None)
        return None

    _cache_set(filename, data)

    return data


def save_json(filename, data):
    """
    Grava `data` em `filename` no Gist.

    Retorna True em caso de sucesso e False quando o Gist não está
    configurado ou a gravação falha. Nunca levanta exceção.
    """

    config = _config()

    if config is None:
        return False

    token, gist_id = config

    try:
        _request(
            API_URL.format(gist_id=gist_id),
            token,
            method="PATCH",
            payload={
                "files": {
                    filename: {
                        "content": json.dumps(
                            data,
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                },
            },
        )

        # A próxima leitura já enxerga o que acabou de ser gravado.
        _cache_set(filename, data)
        _pending_clear(filename)

        return True

    except Exception as exc:  # noqa: BLE001 - falha do Gist é fallback
        _log_error(
            "gravar",
            filename,
            exc,
        )
        # Mantém o estado novo em memória até conseguir sincronizar.
        _pending_set(filename, data)
        _cache_set(filename, data)
        return False
