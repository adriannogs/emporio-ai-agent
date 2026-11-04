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

# V3.3: recomendação contextual baseada exclusivamente nos campos do catálogo.
def test_recommendation_route_is_detected():
    assert _route("Qual você recomenda para começar?") == "recommendation"
    assert _route("Qual violão você indica para iniciante?") == "recommendation"


def test_recommendation_uses_previous_catalog_results():
    agent = EmporioAgent(use_llm=False)
    session = "recommendation-context"
    first = agent.respond("Quais opções de violões até R$ 1000?", session)
    assert "Encontrei estas opções" in first
    answer = agent.respond("Qual você recomenda para começar?", session)
    assert "uma opção para avaliar" in answer.lower()
    assert "Descrição cadastrada" in answer
    assert "base de demonstração" in answer
    assert "nylon ou aço" in answer.lower()


def test_recommendation_without_context_asks_for_instrument():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("Qual você recomenda para começar?", "recommendation-empty")
    assert "qual instrumento" in answer.lower()


def test_recommendation_with_category_queries_catalog():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("Qual violão você recomenda para iniciante?", "recommendation-category")
    assert "uma opção para avaliar" in answer.lower()
    assert "R$" in answer
    assert "base de demonstração" in answer.lower()


def test_recommendation_context_is_isolated_between_sessions():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Quais opções de violões?", "recommendation-session-a")
    answer = agent.respond("Qual você recomenda para começar?", "recommendation-session-b")
    assert "qual instrumento" in answer.lower()
    assert "Tagima Memphis" not in answer


def test_recommendation_does_not_claim_independent_quality_assessment():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Quais opções de violões?", "recommendation-no-invention")
    answer = agent.respond("Qual você recomenda para começar?", "recommendation-no-invention")
    assert "não uma avaliação independente" in answer.lower()
    assert "melhor qualidade" not in answer.lower()


# V3.3.2: continuidade do diálogo de recomendação.
def test_recommendation_reason_route_is_detected():
    assert _route("Por que você recomenda esse modelo?") == "recommendation_reason"


def test_recommendation_reason_uses_saved_recommended_product():
    agent = EmporioAgent(use_llm=False)
    session = "recommendation-reason"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Por que você recomenda esse modelo?", session)
    assert "Tagima Memphis AC-39" in answer
    assert "perfeito para quem está começando" in answer
    assert "não representa uma avaliação independente" in answer


def test_recommendation_reason_without_prior_recommendation_asks_to_recommend():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("Por que você recomenda esse modelo?", "reason-empty")
    assert "ainda não indiquei" in answer.lower()


def test_cheaper_alternative_route_is_detected():
    assert _route("Tem outra opção mais barata?") == "cheaper_alternative"


def test_cheaper_alternative_reports_when_reference_is_already_cheapest():
    agent = EmporioAgent(use_llm=False)
    session = "cheaper-no-result"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Tem outra opção mais barata?", session)
    assert "já é a opção de menor preço" in answer.lower()
    assert "R$ 429,90" in answer


def test_cheaper_alternative_only_returns_products_below_reference():
    agent = EmporioAgent(use_llm=False)
    session = "cheaper-filter"
    rows = search_products(category="Violões", max_price=1000, available_only=True)
    agent._get_session(session)["last_products"] = rows
    agent._get_session(session)["recommended_product"] = next(
        p for p in rows if p["name"] == "Yamaha C40 Nylon Natural"
    )
    answer = agent.respond("Tem outra opção mais barata?", session)

    # O modelo de referência pode aparecer na introdução; ele não pode
    # aparecer entre as alternativas nem ser listado como opção mais barata.
    assert "Yamaha C40" in answer

    alternative_lines = [
        line for line in answer.splitlines()
        if line.lstrip().startswith("- **")
    ]
    assert alternative_lines, f"Nenhuma alternativa foi listada. Resposta recebida:\n{answer}"
    assert all("Yamaha C40" not in line for line in alternative_lines)
    assert "Tagima Memphis AC-39" in answer

    # Confere os preços exibidos: todos devem ser inferiores a R$ 599,90.
    import re
    displayed_prices = []
    for line in alternative_lines:
        match = re.search(r"R\$\s*([\d.]+,[\d]{2})", line)
        assert match, f"Preço não identificado na alternativa: {line}"
        displayed_prices.append(
            float(match.group(1).replace(".", "").replace(",", "."))
        )
    assert all(price < 599.90 for price in displayed_prices)


def test_recommendation_state_is_isolated_between_sessions():
    agent = EmporioAgent(use_llm=False)
    session_a = "recommendation-state-a"
    agent.respond("Quais opções de violões até R$ 1000?", session_a)
    agent.respond("Qual você recomenda para começar?", session_a)
    answer = agent.respond("Por que você recomenda esse modelo?", "recommendation-state-b")
    assert "ainda não indiquei" in answer.lower()


# V3.3.3: refinamento contextual e recomendações sucessivas.
def test_short_nylon_reply_is_saved_as_recommendation_preference():
    agent = EmporioAgent(use_llm=False)
    session = "v333-nylon"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Nylon.", session)
    state = agent._get_session(session)
    assert state["preferred_specs"]["strings"] == "nylon"
    assert state["pending_action"] == "recommendation_alternative"
    assert "cordas de nylon" in answer.lower()


def test_next_recommendation_respects_nylon_and_excludes_previous_product():
    agent = EmporioAgent(use_llm=False)
    session = "v333-next-nylon"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    first = agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Nylon.", session)
    answer = agent.respond("Então me indique outra opção.", session)
    assert "Tagima Memphis AC-39" in first
    assert "Rozini RC-104 Nylon Estudante" in answer
    assert "Tagima Memphis AC-39" not in answer
    assert "Descrição cadastrada" in answer


def test_recommendation_followup_route_is_detected():
    assert _route("Então me indique outra opção.") == "next_recommendation"
    assert _route("Quero outra alternativa") == "next_recommendation"


def test_cheaper_alternative_keeps_priority_over_next_recommendation():
    agent = EmporioAgent(use_llm=False)
    session = "v333-cheaper-priority"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Tem outra opção mais barata?", session)
    assert "já é a opção de menor preço" in answer.lower()


def test_recommendation_excludes_every_previously_recommended_product():
    agent = EmporioAgent(use_llm=False)
    session = "v333-no-repeat"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    first = agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Nylon.", session)
    second = agent.respond("Me indique outra opção.", session)
    state = agent._get_session(session)
    assert len(state["recommended_product_ids"]) == 2
    assert state["recommended_product_ids"][0] != state["recommended_product_ids"][1]
    assert "Tagima Memphis AC-39" in first
    assert "Tagima Memphis AC-39" not in second


def test_brand_preference_is_applied_to_next_recommendation():
    agent = EmporioAgent(use_llm=False)
    session = "v333-brand"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Yamaha.", session)
    answer = agent.respond("Outra opção, por favor.", session)
    assert "Yamaha" in answer
    assert "Tagima" not in answer
    assert agent._get_session(session)["preferred_specs"]["brand"] == "yamaha"


def test_budget_preference_is_applied_to_next_recommendation():
    agent = EmporioAgent(use_llm=False)
    session = "v333-budget"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Até R$ 500.", session)
    answer = agent.respond("Outra opção.", session)
    assert "R$ 459,90" in answer
    assert agent._get_session(session)["preferred_specs"]["max_price"] == 500.0


def test_incompatible_preferences_return_transparent_no_result():
    agent = EmporioAgent(use_llm=False)
    session = "v333-no-match"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Yamaha até R$ 400.", session)
    answer = agent.respond("Outra opção.", session)
    assert "não encontrei outra opção disponível" in answer.lower()


def test_recommendation_preferences_do_not_leak_between_sessions():
    agent = EmporioAgent(use_llm=False)
    agent.respond("Quais opções de violões até R$ 1000?", "v333-session-a")
    agent.respond("Qual você recomenda para começar?", "v333-session-a")
    agent.respond("Nylon.", "v333-session-a")
    state_b = agent._get_session("v333-session-b")
    assert state_b["preferred_specs"] == {}
    assert state_b["recommended_product_ids"] == []
    answer = agent.respond("Então me indique outra opção.", "v333-session-b")
    assert "qual instrumento" in answer.lower()


def test_recommendation_preference_does_not_trigger_without_pending_recommendation():
    agent = EmporioAgent(use_llm=False)
    answer = agent.respond("Nylon.", "v333-no-pending")
    assert "Prazer," not in answer
    assert agent._get_session("v333-no-pending")["preferred_specs"] == {}


def test_recommendation_context_preserves_category_and_budget():
    agent = EmporioAgent(use_llm=False)
    session = "v333-preserve-context"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Nylon.", session)
    agent.respond("Então me indique outra opção.", session)
    state = agent._get_session(session)
    assert state["last_category"] == "Violões"
    assert state["last_budget"] == 1000.0
    assert state["preferred_specs"]["strings"] == "nylon"


def test_steel_preference_filters_the_next_recommendation():
    agent = EmporioAgent(use_llm=False)
    session = "v333-steel"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Aço.", session)
    answer = agent.respond("Outra opção.", session)
    assert "cordas de aço" in answer.lower()
    assert "Yamaha F310 Aço Natural" in answer
    assert "Tagima Memphis AC-39" not in answer


def test_expanded_budget_refreshes_the_category_catalog():
    agent = EmporioAgent(use_llm=False)
    session = "v333-expanded-budget"
    agent.respond("Quais opções de violões até R$ 500?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Yamaha até R$ 1500.", session)
    answer = agent.respond("Outra opção.", session)
    assert "Yamaha C40 Nylon Natural" in answer
    assert agent._get_session(session)["last_budget"] == 1500.0


def test_recommendation_rephrasing_does_not_repeat_previous_product():
    agent = EmporioAgent(use_llm=False)
    session = "v333-rephrased-next"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    first = agent.respond("Qual você recomenda para começar?", session)
    second = agent.respond("Qual outro você recomenda?", session)
    assert "Tagima Memphis AC-39" in first
    assert "Tagima Memphis AC-39" not in second
    assert "Rozini RC-104 Nylon Estudante" in second

# V3.3.4: prioridade de novas pesquisas sobre estados pendentes de recomendação.
def test_explicit_catalog_search_preempts_pending_recommendation_and_resets_filters():
    agent = EmporioAgent(use_llm=False)
    session = "v334-new-search-priority"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Nylon.", session)

    answer = agent.respond("Quais opções de violões até R$ 500?", session)
    state = agent._get_session(session)

    assert "Encontrei estas opções" in answer
    assert "R$ 500,00" in answer
    assert "Tagima Memphis AC-39" in answer
    assert state["last_budget"] == 500
    assert state["preferred_specs"].get("max_price") == 500
    assert "strings" not in state["preferred_specs"]
    assert state["recommended_product"] is None
    assert state["recommended_product_ids"] == []
    assert state["pending_action"] is None


def test_recommendation_after_new_budget_search_uses_new_catalog_results():
    agent = EmporioAgent(use_llm=False)
    session = "v334-recommend-after-new-search"
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Quais opções de violões até R$ 500?", session)
    assert "R$  500" not in answer

    recommendation = agent.respond("Qual você recomenda para começar?", session)
    assert "uma opção para avaliar" in recommendation.lower()
    assert "Tagima Memphis AC-39" in recommendation or "Rozini RC-104" in recommendation
    assert "R$ 500" not in recommendation or "R$ 429,90" in recommendation or "R$ 459,90" in recommendation


def test_brand_and_budget_refinement_remains_contextual_after_new_search():
    agent = EmporioAgent(use_llm=False)
    session = "v334-brand-budget-refinement"
    agent.respond("Quais opções de violões até R$ 500?", session)
    agent.respond("Qual você recomenda para começar?", session)
    answer = agent.respond("Yamaha até R$ 1500.", session)
    state = agent._get_session(session)

    assert "marca Yamaha" in answer
    assert state["preferred_specs"]["brand"] == "yamaha"
    assert state["preferred_specs"]["max_price"] == 1500
    assert state["last_budget"] == 1500

    alternative = agent.respond("Outra opção.", session)
    assert "Yamaha" in alternative
    assert "C70" in alternative or "C40" in alternative


def test_explicit_catalog_search_does_not_clear_customer_identity():
    agent = EmporioAgent(use_llm=False)
    session = "v334-preserve-customer-name"
    agent.respond("Adriano", session)
    agent.respond("Quais opções de violões até R$ 1000?", session)
    agent.respond("Qual você recomenda para começar?", session)
    agent.respond("Quais opções de violões até R$ 500?", session)
    answer = agent.respond("Oi", session)
    assert "Adriano" in answer


def test_explicit_catalog_search_detector_is_conservative_for_short_preferences():
    from emporio_agent.agent import _is_explicit_catalog_search
    assert _is_explicit_catalog_search("Quais opções de violões até R$ 500?")
    assert _is_explicit_catalog_search("Me mostre violões")
    assert not _is_explicit_catalog_search("Yamaha até R$ 1500")
    assert not _is_explicit_catalog_search("Nylon")
    assert not _is_explicit_catalog_search("Outra opção")
