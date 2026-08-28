"""
Cobre a tabela de providers de `config/models.py` e o contrato de `build_llm`
com provider opcional (sem API key -> None, fora da cadeia de fallback).
"""

import importlib

from langchain_openai import ChatOpenAI

from config.models import BUILDERS, PROVIDER_MAP, Model
from frigus_ai.graph import llm as llm_mod


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

    import config.models
    import config.settings

    for mod in (config.settings, config.models):
        importlib.reload(mod)
    recarregado = importlib.reload(llm_mod)

    try:
        assert recarregado.llm_openrouter is not None
        assert len(recarregado.llm_especialista.fallbacks) == 2
    finally:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        for mod in (config.settings, config.models):
            importlib.reload(mod)
        importlib.reload(llm_mod)
