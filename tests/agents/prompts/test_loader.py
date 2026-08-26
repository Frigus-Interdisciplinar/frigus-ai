from pathlib import Path

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
