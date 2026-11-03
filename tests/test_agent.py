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


def test_generic_catalog_lists_real_categories():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("catálogo", "catalog-test")
    assert "categorias de instrumentos" in answer.lower()
    assert "violões" in answer.lower()

def test_generic_prices_asks_for_clarification():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("preços", "prices-test")
    assert "qual instrumento ou modelo" in answer.lower()
    assert "Shelby" not in answer

def test_generic_availability_asks_for_product():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("disponibilidade", "availability-test")
    assert "qual instrumento ou modelo" in answer.lower()

def test_name_is_remembered_within_session():
    agent = EmporioAgent(use_llm=False)
    first = agent.respond("Adriano", "name-test")
    assert "Prazer, Adriano" in first
    second = agent.respond("preços", "name-test")
    assert "qual instrumento ou modelo" in second.lower()

def test_specific_product_price_still_routes_to_product():
    assert _route("Quanto custa o Takamine GD20?") == "product"


def test_orchestral_strings_are_valid_instrument_category():
    assert _route("Quero conhecer cordas orquestrais") == "product"


def test_greeting_is_not_captured_as_customer_name():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("Oi", "greeting-test")
    assert "bem-vindo" in answer.lower()


def test_orchestral_strings_searches_the_correct_category():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("cordas orquestrais", "orchestral-test")
    assert "cordas orquestrais" in answer.lower()
    assert "não há instrumentos" in answer.lower()
    assert "Shelby SU-21S" not in answer

# V3: roteamento de comparação e memória contextual isolada por sessão.
def test_compare_command_is_not_treated_as_customer_name():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("comparar", "compare-command")
    assert "quais são os dois modelos" in answer.lower()
    assert "Prazer, Comparar" not in answer


def test_comparison_route_is_detected():
    assert _route("Quero comparar") == "comparison"
    assert _route("Compare os modelos") == "comparison"


def test_comparison_uses_previous_catalog_results():
    agent = EmporioAgent(use_llm=False)
    first = agent.respond("Quais opções de violões?", "compare-flow")
    assert "Encontrei estas opções" in first
    answer = agent.respond("comparar", "compare-flow")
    assert "comparação" in answer.lower()
    assert "preço" in answer.lower()
    assert "não vou presumir características técnicas" in answer.lower()


def test_comparison_without_context_asks_for_two_models():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("compare os modelos", "compare-empty")
    assert "quais são os dois modelos" in answer.lower()


def test_session_context_is_isolated():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Adriano", "session-a")
    answer = agent.respond("Oi", "session-b")
    assert "bem-vindo" in answer.lower()
    assert "Adriano" not in answer


def test_session_name_is_preserved_after_intent_commands():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Adriano", "session-name")
    agent.respond("comparar", "session-name")
    answer = agent.respond("Oi", "session-name")
    assert "Adriano" in answer


def test_comparison_does_not_invent_technical_specs():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Quais opções de violões?", "compare-specs")
    answer = agent.respond("comparar", "compare-specs")
    assert "madeira" not in answer.lower()
    assert "captador" not in answer.lower()
    assert "características técnicas" in answer.lower()


def test_reserved_word_comparar_is_not_a_name():
    from emporio_agent.agent import _is_possible_name
    assert not _is_possible_name("Comparar")
    assert not _is_possible_name("Disponibilidade")
    assert _is_possible_name("Adriano")

# V3.1: testes de continuidade conversacional e intenção contextual.
def test_explain_policies_routes_to_policy_not_customer_name():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("explicar politicas", "policy-phrase")
    assert "Prazer, Explicar" not in answer
    assert "manual da empório da música" in answer.lower()
    assert "trocas e devoluções" in answer.lower()
    assert "frete e entrega" in answer.lower()


def test_policy_plural_routes_correctly():
    assert _route("explicar politicas da loja") == "policy"
    assert _route("quais são as políticas da loja?") == "policy"


def test_lowest_price_uses_previous_product_results():
    agent = EmporioAgent(use_llm=False)
    first = agent.respond("guitarras", "sort-flow")
    assert "Fender Telecaster" in first
    answer = agent.respond("menor preço", "sort-flow")
    assert "orden ei" not in answer.lower()
    assert "Ordenei" in answer
    assert answer.index("Fender Telecaster") < answer.index("PRS SE Custom 24")


def test_sort_without_previous_context_asks_for_category():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("menor preço", "sort-empty")
    assert "primeiro" in answer.lower()
    assert "categoria" in answer.lower()


def test_brand_search_tagima_does_not_mix_other_brands():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("tagima", "brand-tagima")
    assert "Tagima" in answer
    assert "Shelby" not in answer
    assert "Yamaha" not in answer


def test_sort_highest_stock_uses_session_results():
    agent = EmporioAgent(use_llm=False)
    agent.respond("violão", "sort-stock")
    answer = agent.respond("maior estoque", "sort-stock")
    assert "maior quantidade em estoque" in answer
    assert "estoque informado" in answer


def test_policy_phrase_is_not_a_possible_customer_name():
    from emporio_agent.agent import _is_possible_name
    assert not _is_possible_name("explicar politicas")
    assert not _is_possible_name("politicas da loja")

# V3.2: estados pendentes, tópicos do manual e diálogos completos.
def test_policy_topic_followup_promotions_is_not_customer_name():
    agent = EmporioAgent(use_llm=False)
    agent.respond("explicar políticas da loja", "policy-followup-promotions")
    answer = agent.respond("promoções", "policy-followup-promotions")
    assert "Prazer, Promoções" not in answer
    assert "campanhas" in answer.lower() or "promoções" in answer.lower()
    assert "manual" in answer.lower()


def test_policy_topic_followup_attendance_is_not_customer_name():
    agent = EmporioAgent(use_llm=False)
    agent.respond("explicar políticas da loja", "policy-followup-attendance")
    answer = agent.respond("atendimento", "policy-followup-attendance")
    assert "Prazer, Atendimento" not in answer
    assert "horário" in answer.lower() or "atendimento" in answer.lower()


def test_policy_topic_followup_about_store_returns_manual_section():
    agent = EmporioAgent(use_llm=False)
    agent.respond("explicar políticas da loja", "policy-followup-store")
    answer = agent.respond("sobre a loja", "policy-followup-store")
    assert "fundada em 2008" in answer.lower()
    assert "campo grande" in answer.lower()


def test_policy_topics_are_not_possible_names():
    from emporio_agent.agent import _is_possible_name
    for phrase in ["promoções", "atendimento", "sobre a loja", "pagamento", "garantia"]:
        assert not _is_possible_name(phrase)


def test_comparison_pending_survives_catalog_then_category():
    agent = EmporioAgent(use_llm=False)
    session = "comparison-pending-full"
    first = agent.respond("comparar modelos", session)
    assert "quais são os dois modelos" in first.lower()
    agent.respond("catálogo", session)
    second = agent.respond("comparar modelos", session)
    assert "quais são os dois modelos" in second.lower()
    category = agent.respond("guitarras", session)
    assert "Fender Telecaster" in category
    assert "havia pedido uma comparação" in category.lower()
    comparison = agent.respond("comparar modelos", session)
    assert "PRS SE Custom 24" in comparison
    assert "Gibson Les Paul" in comparison


def test_comparison_pending_does_not_leak_between_sessions():
    agent = EmporioAgent(use_llm=False)
    agent.respond("comparar modelos", "pending-session-a")
    answer = agent.respond("guitarras", "pending-session-b")
    assert "havia pedido uma comparação" not in answer.lower()


def test_policy_topic_retrieval_is_accent_insensitive():
    agent = EmporioAgent(use_llm=False)
    agent.respond("explicar políticas da loja", "policy-accent")
    answer = agent.respond("promoções", "policy-accent")
    assert "não encontrei uma orientação específica" not in answer.lower()
    assert "black friday" in answer.lower()


def test_generic_policy_question_sets_pending_policy_topic():
    agent = EmporioAgent(use_llm=False)
    agent.respond("explicar políticas", "policy-pending-state")
    assert agent._get_session("policy-pending-state")["pending_action"] == "policy_topic"
    agent.respond("pagamento", "policy-pending-state")
    assert agent._get_session("policy-pending-state")["pending_action"] is None


def test_topic_word_without_prior_policy_is_not_mistaken_for_name():
    agent = EmporioAgent(use_llm=False)
    for topic in ["promoções", "atendimento", "sobre a loja"]:
        answer = agent.respond(topic, f"topic-alone-{topic}")
        assert "Prazer," not in answer
