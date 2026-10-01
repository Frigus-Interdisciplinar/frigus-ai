import sys

from frigus_ai import main as mod


def test_interface_desconhecida_avisa_e_nao_sobe_nada(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["frigus-ai", "nao-existe"])

    mod.main()

    assert "nao-existe" in capsys.readouterr().out
