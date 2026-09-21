from frigus_ai.infra.redis import ranking


class _FakeRedis:
    """Stub mínimo do client redis-py — só o subset usado por infra/redis/ranking.py."""

    def __init__(self):
        self._sorted_sets: dict[str, dict[str, float]] = {}

    def zincrby(self, key, amount, value):
        zset = self._sorted_sets.setdefault(key, {})
        zset[value] = zset.get(value, 0) + amount
        return zset[value]

    def zrevrange(self, key, start, end, withscores=False):
        zset = self._sorted_sets.get(key, {})
        ordenado = sorted(zset.items(), key=lambda item: item[1], reverse=True)
        fatia = ordenado[start : end + 1] if end != -1 else ordenado[start:]
        return fatia if withscores else [nome for nome, _ in fatia]


def _usar_fake_client(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(ranking, "get_client", lambda: fake)
    return fake


def test_registrar_descarte_acumula_por_produto(monkeypatch):
    _usar_fake_client(monkeypatch)

    ranking.registrar_descarte(stock_id=1, product_name="Leite", quantidade=2)
    ranking.registrar_descarte(stock_id=1, product_name="Leite", quantidade=3)

    assert ranking.top_desperdicio(stock_id=1) == [("Leite", 5.0)]


def test_top_desperdicio_ordena_do_maior_pro_menor(monkeypatch):
    _usar_fake_client(monkeypatch)

    ranking.registrar_descarte(stock_id=1, product_name="Leite", quantidade=2)
    ranking.registrar_descarte(stock_id=1, product_name="Pão", quantidade=8)
    ranking.registrar_descarte(stock_id=1, product_name="Ovo", quantidade=5)

    assert ranking.top_desperdicio(stock_id=1) == [("Pão", 8.0), ("Ovo", 5.0), ("Leite", 2.0)]


def test_top_desperdicio_respeita_o_limit(monkeypatch):
    _usar_fake_client(monkeypatch)

    ranking.registrar_descarte(stock_id=1, product_name="Leite", quantidade=2)
    ranking.registrar_descarte(stock_id=1, product_name="Pão", quantidade=8)

    assert ranking.top_desperdicio(stock_id=1, limit=1) == [("Pão", 8.0)]


def test_ranking_e_isolado_por_estoque(monkeypatch):
    _usar_fake_client(monkeypatch)

    ranking.registrar_descarte(stock_id=1, product_name="Leite", quantidade=2)
    ranking.registrar_descarte(stock_id=2, product_name="Pão", quantidade=8)

    assert ranking.top_desperdicio(stock_id=1) == [("Leite", 2.0)]
    assert ranking.top_desperdicio(stock_id=2) == [("Pão", 8.0)]
