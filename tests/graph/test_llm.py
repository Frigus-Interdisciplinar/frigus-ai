"""
Cobre a tabela de providers de `frigus_ai/models.py` e o contrato de `build_llm`
com provider opcional (sem API key -> None, fora da cadeia de fallback).
"""

import importlib

from langchain_openai import ChatOpenAI

from frigus_ai.graph import llm as llm_mod
from frigus_ai.models import BUILDERS, PROVIDER_MAP, Model


def test_openrouter_resolve_para_chatopenai_com_base_url():
    assert PROVIDER_MAP[Model.GLM_5_2_FREE] == "openrouter"

    modelo = BUILDERS["openrouter"](model=Model.GLM_5_2_FREE, api_key="fake")

    assert isinstance(modelo, ChatOpenAI)
    assert str(modelo.openai_api_base).rstrip("/") == "https://openrouter.ai/api/v1"


def test_build_llm_sem_api_key_devolve_none():
    assert llm_mod.build_llm(model=Model.GLM_5_2_FREE, temperature=0.7) is None
    assert llm_mod.llm_openrouter is None


def test_provider_desconhecido_levanta():
    try:
        llm_mod.build_llm(model="modelo-que-nao-existe", temperature=0.0)
    except ValueError as e:
        assert "desconhecido" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_com_chave_openrouter_entra_no_fallback(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key")

    import frigus_ai.models
    import frigus_ai.settings

    for mod in (frigus_ai.settings, frigus_ai.models):
        importlib.reload(mod)
    recarregado = importlib.reload(llm_mod)

    try:
        assert recarregado.llm_openrouter is not None
        assert len(recarregado.llm_especialista.fallbacks) == 2
    finally:
        # setenv("") em vez de delenv: `OPENROUTER_API_KEY` não tem default no
        # `Settings` (é obrigatória, embora vazia conte como "provider desligado").
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        for mod in (frigus_ai.settings, frigus_ai.models):
            importlib.reload(mod)
        importlib.reload(llm_mod)
