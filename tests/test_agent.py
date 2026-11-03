from emporio_agent.database import initialize_database
from emporio_agent.agent import EmporioAgent, _route
from emporio_agent.tools import search_products, active_promotions

def setup_module():
    initialize_database(force=True)

def test_product_price_lookup():
    rows=search_products(term="Takamine GD20", available_only=True)
    assert rows and rows[0]["price_brl"] == 2199.0

def test_budget_search_returns_only_available_products():
    rows=search_products(category="Violões", max_price=1000, available_only=True)
    assert rows
    assert all(r["price_brl"] <= 1000 and r["stock_quantity"] > 0 and r["status"]=="active" for r in rows)

def test_promotions_only_active_and_in_stock():
    rows=active_promotions()
    assert rows
    assert all(r["stock_quantity"] > 0 for r in rows)

def test_policy_routing():
    assert _route("Posso devolver uma compra online?") == "policy"

def test_accessory_out_of_scope():
    agent=EmporioAgent(use_llm=False)
    answer=agent.respond("Vocês vendem cordas para violão?", "test")
    assert "não comercializa acessórios" in answer.lower()

def test_order_requires_validation():
    agent=EmporioAgent(use_llm=False)
    answer=agent.respond("Onde está o pedido 8?", "test")
    assert "nome completo" in answer.lower()


def test_plural_category_routing():
    assert _route("Quais opções de violões até R$ 1000?") == "product"

def test_accessory_intent_precedes_instrument_keyword():
    assert _route("Vocês vendem cordas para violão?") == "out_of_scope"

def test_regret_policy_routing():
    assert _route("Me arrependi da minha compra online, posso devolver?") == "policy"
