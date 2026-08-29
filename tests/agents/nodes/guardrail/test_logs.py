"""
Regressão de vazamento em log: o guardrail logava a mensagem **crua** ao bloquear,
justamente o caminho em que ela tem mais chance de conter CPF/e-mail/telefone.
Agora loga o texto já anonimizado.
"""

from frigus_ai.agents.nodes.guardrail import entrada


async def test_bloqueio_nao_loga_pii_da_mensagem_original(monkeypatch, caplog):
    async def _bloqueia(_texto):
        return {"bloqueado": True, "motivo": "teste", "mensagem": "não posso ajudar"}

    monkeypatch.setattr(entrada, "guardrail_entrada", _bloqueia)

    class _Msg:
        id = "1"
        content = "meu cpf é 123.456.789-09 e o email eh fulano@exemplo.com"

    with caplog.at_level("WARNING"):
        await entrada.no_guardrail_entrada({"messages": [_Msg()]})

    logado = caplog.text
    assert "123.456.789-09" not in logado
    assert "fulano@exemplo.com" not in logado
    assert "teste" in logado
