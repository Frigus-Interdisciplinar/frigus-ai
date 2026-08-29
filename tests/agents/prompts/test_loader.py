from datetime import UTC, datetime
from pathlib import Path

from frigus_ai.agents.prompts import loader
from frigus_ai.agents.prompts.loader import load_sections


def _escrever_md(tmp_path: Path, conteudo: str) -> Path:
    caminho = tmp_path / "teste.md"
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_load_sections_duas_secoes(tmp_path):
    md = _escrever_md(
        tmp_path,
        """## PAPEL

Texto do papel.
Segunda linha.

## SHOTS

Exemplo 1.
""",
    )

    secoes = load_sections(md)

    assert secoes == {
        "papel": "Texto do papel.\nSegunda linha.",
        "shots": "Exemplo 1.",
    }


def test_load_sections_ignora_texto_antes_do_primeiro_header(tmp_path):
    md = _escrever_md(tmp_path, "texto solto\n\n## PAPEL\n\nconteudo\n")

    secoes = load_sections(md)

    assert secoes == {"papel": "conteudo"}


def test_load_sections_nao_quebra_com_sub_headers_dentro_da_secao(tmp_path):
    md = _escrever_md(
        tmp_path,
        """## PAPEL

### SUBSEÇÃO
texto dentro da subseção, não vira uma seção nova.
""",
    )

    secoes = load_sections(md)

    assert secoes == {"papel": "### SUBSEÇÃO\ntexto dentro da subseção, não vira uma seção nova."}


def test_load_sections_arquivo_vazio(tmp_path):
    md = _escrever_md(tmp_path, "")

    assert load_sections(md) == {}


def test_contexto_temporal_nao_congela_entre_chamadas(monkeypatch):
    """
    Regressão: a data era constante de módulo, montada no import — uma API viva
    respondia "hoje" com a data em que o processo subiu, e "o que vence hoje" é o
    core do domínio.
    """

    class _FakeDatetime:
        agora = datetime(2026, 8, 28, 12, 0, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.agora

    monkeypatch.setattr(loader, "datetime", _FakeDatetime)

    primeiro = loader.contexto_temporal()

    _FakeDatetime.agora = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
    segundo = loader.contexto_temporal()

    assert primeiro != segundo
    assert "28" in primeiro
    assert "29" in segundo


def test_load_prompt_carrega_a_data_do_momento_da_chamada():
    prompt = loader.load_prompt("estoque")

    assert datetime.now(UTC).astimezone().strftime("%d de") in prompt
