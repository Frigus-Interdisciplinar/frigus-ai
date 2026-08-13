from frigus_ai.tools.response import Response


def test_ok_sem_dados():
    assert Response.ok() == {"status": "ok"}


def test_ok_com_dados():
    assert Response.ok(items=[1, 2], total=2) == {
        "status": "ok",
        "items": [1, 2],
        "total": 2,
    }


def test_error_com_string():
    assert Response.error("deu ruim") == {"status": "error", "message": "deu ruim"}


def test_error_com_excecao():
    """Exception vira str — o LLM recebe a mensagem, não o objeto."""
    assert Response.error(ValueError("id inválido")) == {
        "status": "error",
        "message": "id inválido",
    }
