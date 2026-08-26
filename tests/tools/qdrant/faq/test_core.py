from frigus_ai.tools.qdrant.faq import core


class _FakePoint:
    def __init__(self, text, file, page, score):
        self.payload = {"text": text, "file": file, "page": page}
        self.score = score


class _FakeQueryResult:
    def __init__(self, points):
        self.points = points


class _FakeQdrantClient:
    def __init__(self, points):
        self._points = points

    def query_points(self, collection_name, query, limit):
        return _FakeQueryResult(self._points)


class _FakeEmbeddings:
    def __init__(self, *args, **kwargs):
        pass

    def embed_query(self, question):
        return [0.1, 0.2, 0.3]


def _monkeypatch_deps(monkeypatch, points):
    monkeypatch.setattr(core, "get_qdrant_client", lambda: _FakeQdrantClient(points))
    monkeypatch.setattr(core, "GoogleGenerativeAIEmbeddings", _FakeEmbeddings)


def test_faq_retriever_retorna_resultados(monkeypatch):
    pontos = [_FakePoint("resposta relevante", "Frigus-Documentacao.pdf", 2, 0.87)]
    _monkeypatch_deps(monkeypatch, pontos)

    resultado = core.faq_retriever.invoke({"question": "como funciona o estoque?"})

    assert resultado["status"] == "ok"
    assert resultado["results"] == [
        {
            "text": "resposta relevante",
            "file": "Frigus-Documentacao.pdf",
            "page": 2,
            "score": 0.87,
        }
    ]


def test_faq_retriever_sem_resultados(monkeypatch):
    _monkeypatch_deps(monkeypatch, [])

    resultado = core.faq_retriever.invoke({"question": "pergunta sem match"})

    assert resultado == {"status": "ok", "results": []}


def test_faq_retriever_erro_vira_response_error(monkeypatch):
    def _quebra():
        raise RuntimeError("qdrant fora do ar")

    monkeypatch.setattr(core, "get_qdrant_client", _quebra)

    resultado = core.faq_retriever.invoke({"question": "qualquer coisa"})

    assert resultado == {"status": "error", "message": "qdrant fora do ar"}
