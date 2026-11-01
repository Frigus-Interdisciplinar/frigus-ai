from contextlib import contextmanager
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from frigus_ai.domain.recipe_turn import RecipeTurn
from frigus_ai.repositories.receitas_repository import _ReceitasPostgresRepo


@pytest.fixture
def receitas():
    engine = create_engine("sqlite://")
    with engine.begin() as db:
        for ddl in (
            "CREATE TABLE recipes (id INTEGER PRIMARY KEY, name TEXT, active BOOLEAN)",
            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, category TEXT)",
            "CREATE TABLE recipe_ingredients (recipe_id INTEGER, product_id INTEGER)",
            "CREATE TABLE stock_products (product_id INTEGER, stock_id INTEGER, quantity INTEGER, expire_date DATE)",
        ):
            db.execute(text(ddl))
        db.execute(text("INSERT INTO recipes VALUES (:id, :name, 1)"), [
            {"id": i, "name": nome} for i, nome in enumerate(
                ["Arroz", "Frango com arroz", "Arroz com queijo", "Feijão vencido", "Aveia sem saldo", "Milho de outra casa"], 1
            )
        ])
        db.execute(text("INSERT INTO products VALUES (:id, :name, :category)"), [
            {"id": i, "name": nome, "category": categoria} for i, (nome, categoria) in enumerate(
                [("Arroz", "GRAIN"), ("Frango", "MEAT"), ("Queijo", "DAIRY"), ("Feijão", "GRAIN"), ("Aveia", "GRAIN"), ("Milho", "GRAIN")], 1
            )
        ])
        db.execute(text("INSERT INTO recipe_ingredients VALUES (:recipe, :product)"), [
            {"recipe": r, "product": p} for r, p in [(1, 1), (2, 1), (2, 2), (3, 1), (3, 3), (4, 4), (5, 5), (6, 6)]
        ])
        db.execute(text("INSERT INTO stock_products VALUES (:product, :stock, :quantity, :expiry)"), [
            {"product": i, "stock": 99 if i == 6 else 42, "quantity": 0 if i == 5 else 2,
             "expiry": (date.today() + timedelta(days=-1 if i == 4 else 3)).isoformat()}
            for i in range(1, 7)
        ])

    class Conexao:
        @contextmanager
        def session(self):
            with Session(engine) as s:
                yield s

    yield _ReceitasPostgresRepo(conn=Conexao())
    engine.dispose()


def test_estoque_atual_nao_inclui_vencidos_saldo_zero_ou_outra_casa(receitas):
    sugestoes = receitas.match_recipes_to_stock(42, 10, persistir=False)
    assert {s["recipe_id"] for s in sugestoes} == {1, 2, 3}


def test_filtro_vegano_exclui_receita_inteira_mesmo_se_arroz_esta_disponivel(receitas):
    categorias, termos = RecipeTurn(frozenset({"VEGAN"})).exclusoes()
    sugestoes = receitas.match_recipes_to_stock(
        42, 10, persistir=False, categorias_excluidas=categorias, termos_excluidos=termos
    )
    assert [s["recipe_id"] for s in sugestoes] == [1]
