"""
Cobre a tabela de providers de `frigus_ai/infra/llm/` e o contrato de `build_llm`
com provider opcional (sem API key -> None, fora da cadeia de fallback).
"""

import importlib

from langchain_openai import ChatOpenAI

from frigus_ai.graph import llm as llm_mod
from frigus_ai.infra.llm import BUILDERS, PROVIDER_MAP, build_llm
from frigus_ai.settings import settings
from frigus_ai.settings.llm import Model


def test_openrouter_resolve_para_chatopenai_com_base_url():
    from pydantic import SecretStr

    assert PROVIDER_MAP[Model.QWEN_3_8_FREE] == "openrouter"

    cfg = settings.llm.model_copy(update={"openrouter": settings.llm.openrouter.model_copy(update={"api_key": SecretStr("fake")})})
    modelo = build_llm(Model.QWEN_3_8_FREE, 0.7, cfg)

    assert isinstance(modelo, ChatOpenAI)
    assert str(modelo.openai_api_base).rstrip("/") == "https://openrouter.ai/api/v1"


def test_build_llm_sem_api_key_devolve_none():
    assert build_llm(Model.QWEN_3_8_FREE, 0.7, settings.llm) is None
    assert llm_mod.llm_openrouter is None


def test_provider_desconhecido_levanta():
    try:
        build_llm("modelo-que-nao-existe", 0.0, settings.llm)
    except ValueError as e:
        assert "desconhecido" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_com_chave_openrouter_entra_no_fallback(monkeypatch):
    monkeypatch.setenv("LLM__OPENROUTER__API_KEY", "fake-key")

    import frigus_ai.settings
    import frigus_ai.settings.base

    for mod in (frigus_ai.settings.base, frigus_ai.settings):
        importlib.reload(mod)
    recarregado = importlib.reload(llm_mod)

    try:
        assert recarregado.llm_openrouter is not None
        assert len(recarregado.llm_especialista.fallbacks) == 2
    finally:
        # setenv("") em vez de delenv: `OPENROUTER_API_KEY` não tem default no
        # `Settings` (é obrigatória, embora vazia conte como "provider desligado").
        monkeypatch.setenv("LLM__OPENROUTER__API_KEY", "")
        for mod in (frigus_ai.settings.base, frigus_ai.settings):
            importlib.reload(mod)
        importlib.reload(llm_mod)


def _kwargs_passados(monkeypatch, modelo, llm_settings, **extra):
    """Chama `build_llm` com um builder falso e devolve o que ele recebeu do provider."""

    recebido = {}
    provider = PROVIDER_MAP[modelo]
    monkeypatch.setitem(BUILDERS, provider, lambda **kw: recebido.update(kw))
    build_llm(modelo, 0.0, llm_settings, **extra)
    return recebido


def test_politica_do_provider_vira_timeout_e_retries(monkeypatch):
    """Gemini conta tentativas TOTAIS (retries=0 -> max_retries=1); Groq conta as EXTRAS."""

    cfg = settings.llm.model_copy(update={
        "gemini": settings.llm.gemini.model_copy(update={"timeout_s": 12.0, "retries": 0}),
        "groq": settings.llm.groq.model_copy(update={"timeout_s": 20.0, "retries": 1}),
    })

    gemini = _kwargs_passados(monkeypatch, Model.GEMINI_FLASH, cfg)
    groq = _kwargs_passados(monkeypatch, Model.GPT_OSS_120B, cfg)

    assert (gemini["timeout"], gemini["max_retries"]) == (12.0, 1)
    assert (groq["timeout"], groq["max_retries"]) == (20.0, 1)


def test_timeout_explicito_sobrepoe_a_politica(monkeypatch):
    recebido = _kwargs_passados(monkeypatch, Model.GEMINI_FLASH, settings.llm, timeout_s=5.0)

    assert recebido["timeout"] == 5.0


def test_papeis_de_saida_curta_usam_timeout_menor():
    """Guardrail, juiz e roteador não esperam o que um especialista espera."""

    assert llm_mod.llm_guardrail.timeout == settings.llm.timeout_curto_s
    assert llm_mod.llm_juiz.timeout == settings.llm.timeout_curto_s
    assert llm_mod.llm_rapido.request_timeout == settings.llm.timeout_curto_s
    assert llm_mod.llm_gemini.timeout == settings.llm.gemini.timeout_s
    assert settings.llm.timeout_curto_s < settings.llm.gemini.timeout_s


class _Elo:
    """Modelo falso: registra com que argumentos `with_structured_output`/`with_fallbacks` foram chamados."""

    def __init__(self, nome):
        self.nome = nome

    def with_structured_output(self, schema, **kw):
        return _Elo(f"{self.nome}:{schema.__name__}:{kw.get('method', 'padrao')}")

    def with_fallbacks(self, reservas):
        return ("cadeia", self.nome, [r.nome for r in reservas])


def test_com_reserva_ignora_provider_sem_chave():
    a, b = _Elo("a"), _Elo("b")

    assert llm_mod.com_reserva(None) is None
    assert llm_mod.com_reserva(None, a) is a
    assert llm_mod.com_reserva(None, a, None, b) == ("cadeia", "a", ["b"])


def test_estruturado_usa_json_schema_so_no_elo_da_groq(monkeypatch):
    from langchain_groq import ChatGroq

    from frigus_ai.domain.models import Fatos

    chamadas = []

    def _espiao(self, schema, **kw):
        chamadas.append(kw)
        return _Elo(f"groq:{kw.get('method')}")

    monkeypatch.setattr(ChatGroq, "with_structured_output", _espiao)
    groq = ChatGroq(model="openai/gpt-oss-120b", api_key="fake")

    cadeia = llm_mod.estruturado(Fatos, groq, _Elo("gemini"))

    assert chamadas == [{"method": "json_schema"}]
    assert cadeia == ("cadeia", "groq:json_schema", ["gemini:Fatos:padrao"])
    assert llm_mod.estruturado(Fatos, None, None) is None


def test_luna_so_entra_com_chave_e_vai_pelo_gateway():
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr

    assert build_llm(Model.GPT_6_LUNA, 0.7, settings.llm) is None

    cfg = settings.llm.model_copy(update={"gateway": settings.llm.gateway.model_copy(update={"api_key": SecretStr("fake"), "timeout_s": 40.0})})
    luna = build_llm(Model.GPT_6_LUNA, 0.7, cfg)

    assert isinstance(luna, ChatOpenAI)
    assert luna.model_name == "openai/gpt-6-luna"
    assert luna.request_timeout == 40.0
    assert luna.max_retries == cfg.gateway.retries
    assert luna.openai_api_base == "https://ai-gateway.vercel.sh/v1"


def test_guardrail_e_juiz_nao_dependem_so_do_gemini():
    """Antes só tinham o Gemini: sem cota ele falhava aberto e aprovava tudo em silêncio."""

    from frigus_ai.graph.guardrail import entrada, saida
    from frigus_ai.graph.nodes import juiz

    for cadeia in (entrada.llm_classificador, juiz.llm_avaliador, saida.llm_revisor):
        assert len(cadeia.fallbacks) >= 1
