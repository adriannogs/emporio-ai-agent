import json
import re
from datetime import datetime
from pathlib import Path
from .config import OPENAI_API_KEY, MODEL
from .policies import retrieve_policy
from .tools import search_products, product_details, active_promotions, lookup_order, format_product, list_categories

SYSTEM_PROMPT = """Você é o assistente virtual da Empório da Música, loja de instrumentos musicais.
PERSONA: informal, profissional, acolhedor e conhecedor de música; fale em português brasileiro.
REGRAS INEGOCIÁVEIS:
- Responda somente com fatos presentes no CONTEXTO fornecido. Nunca invente preço, estoque, prazo, promoção ou status.
- Preços, estoque, pedidos e promoções só podem ser afirmados se vierem de resultado de ferramenta desta interação.
- Se não houver resultado, diga que não localizou e ofereça encaminhamento humano.
- A loja vende exclusivamente instrumentos musicais, não acessórios.
- Não exponha dados pessoais nem pedidos de outras pessoas.
- Não prometa cancelar, reembolsar, reservar ou alterar pedidos; você não executa essas ações.
- Para assuntos fora do escopo, explique gentilmente o limite e redirecione.
- Seja objetivo, mas útil. Não diga que consultou um sistema em tempo real: os dados são uma base fornecida para o protótipo.
- Quando houver promoção, apresente preço original, percentual e preço calculado, deixando claro que a flag de promoção ativa vem da base de demonstração.
"""

def _extract_price(text):
    m = re.search(r"(?:até|ate|abaixo de|no máximo|max(?:imo)?)\s*R?\$?\s*([\d.,]+)", text, re.I)
    if not m: return None
    raw=m.group(1).replace(".", "").replace(",", ".") if "," in m.group(1) else m.group(1)
    try: return float(raw)
    except ValueError: return None

def _money(v):
    return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _is_beginner_friendly(product):
    description = _normalize(str(product.get("description") or ""))
    # Evita classificar explicitamente estudantes avançados como iniciantes.
    if "avancado" in description or "avancados" in description:
        return False
    return any(term in description for term in (
        "iniciante", "iniciantes", "comecando", "comecar",
        "estudante", "estudantes", "aprendiz"
    ))


def _select_recommended_product(rows):
    """Seleciona uma opção com base na descrição cadastrada e, em empate, no preço."""
    beginner_rows = [p for p in rows if _is_beginner_friendly(p)]
    candidates = beginner_rows or rows
    return min(candidates, key=lambda p: float(p.get("price_brl") or 0)) if candidates else None


def _extract_recommendation_preferences(message):
    """Extrai preferências explícitas sem inferir atributos não informados."""
    normalized = _normalize(message)
    preferences = {}
    if re.search(r"\bnylon\b", normalized):
        preferences["strings"] = "nylon"
    elif re.search(r"\baco\b", normalized):
        preferences["strings"] = "steel"

    brands = ["yamaha", "tagima", "giannini", "rozini", "shelby", "takamine",
              "fender", "gibson", "ibanez", "prs", "martin", "taylor",
              "strinberg", "kala", "kalani", "ohana"]
    brand = next((item for item in brands if re.search(rf"\b{re.escape(item)}\b", normalized)), None)
    if brand:
        preferences["brand"] = brand
    maximum = _extract_price(message)
    if maximum is not None:
        preferences["max_price"] = maximum
    return preferences


def _product_matches_preferences(product, preferences):
    """Aplica filtros apenas sobre campos efetivamente presentes no catálogo."""
    if not preferences:
        return True
    specs = product.get("specs") or {}
    if isinstance(specs, str):
        try:
            specs = json.loads(specs)
        except (TypeError, ValueError):
            specs = {}
    searchable = _normalize(" ".join([
        str(product.get("name") or ""),
        str(product.get("description") or ""),
        " ".join(str(v) for v in specs.values()) if isinstance(specs, dict) else str(specs),
    ]))
    strings = preferences.get("strings")
    if strings:
        spec_strings = _normalize(str(specs.get("strings", ""))) if isinstance(specs, dict) else ""
        if strings not in spec_strings and strings not in searchable:
            return False
    brand = preferences.get("brand")
    if brand and not re.search(rf"\b{re.escape(brand)}\b", _normalize(str(product.get("name") or ""))):
        return False
    maximum = preferences.get("max_price")
    if maximum is not None and float(product.get("price_brl") or 0) > float(maximum):
        return False
    return True


def _is_explicit_catalog_search(message):
    """Identifica uma nova pesquisa explícita, mesmo durante um fluxo pendente.

    A detecção é intencionalmente conservadora: respostas curtas como "Yamaha"
    ou "Nylon" continuam sendo refinamentos quando há uma recomendação pendente.
    """
    normalized = _normalize(message).strip(" ?.!\t")
    search_phrases = (
        "quais opcoes", "quais produtos", "quais instrumentos",
        "me mostre", "mostre os", "mostrar produtos", "ver produtos",
        "liste os", "listar", "buscar produtos", "pesquisar produtos",
        "quero ver", "quero conhecer", "procuro opcoes", "busco opcoes",
    )
    return any(normalized.startswith(phrase) for phrase in search_phrases)


def _is_next_recommendation_request(message):
    normalized = _normalize(message)
    phrases = (
        "outra opcao", "outra alternativa", "me indique outra",
        "me recomenda outra", "mais uma opcao", "proxima opcao",
        "entao me indique", "entao indique outra", "indique outro modelo",
        "quero outra opcao", "tem outro modelo"
    )
    return any(phrase in normalized for phrase in phrases)

def _find_order_id(text):
    m=re.search(r"(?:pedido|ordem)\s*(?:n[ºo.]?\s*)?#?\s*(\d{1,6})", text, re.I)
    return int(m.group(1)) if m else None

def _normalize(text):
    """Normaliza acentos e espaços para roteamento consistente."""
    import unicodedata
    value = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in value if not unicodedata.combining(ch)).strip()

RESERVED_MESSAGES = {
    "comparar", "compare", "comparacao", "comparar modelos", "compare modelos",
    "consultar", "consulta", "disponibilidade", "precos", "preco", "valores",
    "estoque", "catalogo", "ajuda", "opcoes", "opcao", "obrigado", "obrigada",
    "sim", "nao", "talvez", "quero", "procuro", "busco", "mais detalhes",
    "explicar", "explicar politicas", "explicar politica", "politica", "politicas",
    "politicas da loja", "regras da loja", "menor preco", "mais barato", "mais cara",
    "mais caro", "maior estoque", "menor estoque", "ordenar por preco",
    "recomendar", "recomendacao", "qual voce recomenda", "qual voce indica", "nylon", "aco",
    "qual e melhor para comecar", "para iniciante", "para quem esta comecando",
    "por que voce recomenda", "porque voce recomenda", "tem outra opcao mais barata",
    "outra opcao mais barata", "mais barata que essa", "mais barato que esse"
}


POLICY_TOPIC_LABELS = {
    "sobre a loja": "Sobre a loja",
    "dados e contato": "Dados e contato",
    "horario de funcionamento": "Horário de funcionamento",
    "pagamento": "Pagamento",
    "trocas e devolucoes": "Trocas e devoluções",
    "frete e entrega": "Frete e entrega",
    "promocoes": "Promoções",
    "atendimento": "Atendimento",
    "garantia": "Garantia",
    "privacidade e protecao de dados": "Privacidade e proteção de dados",
    "escalonamento de casos": "Escalonamento de casos",
}

POLICY_TOPICS = {
    "sobre a loja": ["sobre a loja", "quem somos", "loja"],
    "dados e contato": ["dados e contato", "contato", "endereco", "telefone"],
    "horario de funcionamento": ["horario", "horario de funcionamento", "funcionamento", "abre", "fecha"],
    "pagamento": ["pagamento", "pagamentos", "pix", "cartao", "boleto", "parcelamento"],
    "trocas e devolucoes": ["troca", "trocas", "devolucao", "devolucoes", "devolver", "arrependimento", "arrependi"],
    "frete e entrega": ["frete", "entrega", "envio", "prazo de entrega"],
    "promocoes": ["promocao", "promocoes", "desconto", "oferta", "black friday"],
    "atendimento": ["atendimento", "atendente", "falar com atendente", "atendimento humano"],
    "garantia": ["garantia", "defeito", "produto com defeito"],
    "privacidade e protecao de dados": ["privacidade", "lgpd", "dados pessoais", "protecao de dados"],
    "escalonamento de casos": ["escalonamento", "reclamacao", "reclamar", "caso excepcional", "gerencia"],
}

def _policy_topic(message):
    text = _normalize(message).strip(" ?.!\t")
    for topic, phrases in POLICY_TOPICS.items():
        if text == topic or text in phrases:
            return topic
    return None


def _is_possible_name(message):
    """Identifica apresentações curtas sem capturar comandos como nomes."""
    clean = message.strip()
    normalized = _normalize(clean)
    if normalized in RESERVED_MESSAGES or _policy_topic(clean) or len(clean.split()) > 3 or len(clean) < 2:
        return False
    if not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]{1,39}", clean):
        return False
    command_prefixes = ("compar", "consult", "dispon", "preç", "prec", "estoqu", "catalog", "opç", "opco")
    return not any(normalized.startswith(word) for word in command_prefixes)


def _route(message):
    t = _normalize(message)
    if _policy_topic(message):
        return "policy_topic"
    if any(w in t for w in ["comparar", "compare", "comparacao", "diferença entre", "diferenca entre"]):
        return "comparison"
    # Acessórios fora do escopo. "Cordas orquestrais" é uma categoria válida;
    # só tratamos cordas como acessório quando a mensagem indica encordoamento.
    accessory_terms = ["palheta", "cabo", "case", "pedal", "amplificador", "acessorio",
                       "encordoamento", "jogo de cordas", "cordas para", "corda para",
                       "cordas de violao", "cordas de guitarra", "cordas de baixo"]
    if any(w in t for w in accessory_terms):
        return "out_of_scope"
    if any(w in t for w in ["pedido", "rastreamento", "rastrear", "entrega do meu", "onde esta meu"]):
        return "order"
    reason_phrases = [
        "por que voce recomenda", "porque voce recomenda",
        "por que recomenda", "porque recomenda",
        "por que esse modelo", "por que esse", "qual o motivo da indicacao"
    ]
    if any(phrase in t for phrase in reason_phrases):
        return "recommendation_reason"

    cheaper_phrases = [
        "outra opcao mais barata", "tem outra opcao mais barata",
        "alguma opcao mais barata", "mais barata que essa",
        "mais barato que esse", "outra mais barata", "outro mais barato"
    ]
    if any(phrase in t for phrase in cheaper_phrases):
        return "cheaper_alternative"

    recommendation_phrases = [
        "recomenda", "recomendaria", "recomendacao", "qual voce indica",
        "qual voce escolheria", "qual e melhor para comecar",
        "qual seria melhor para comecar", "para iniciante",
        "para iniciantes", "para quem esta comecando", "melhor opcao para mim",
        "vale mais a pena"
    ]
    if any(phrase in t for phrase in recommendation_phrases):
        return "recommendation"
    if _is_next_recommendation_request(message):
        return "next_recommendation"
    if any(w in t for w in ["promocao", "desconto", "oferta", "black friday"]):
        return "promotion"

    policy_terms = ["politica", "politicas", "explicar politica", "explicar politicas",
                    "regras da loja", "horario", "abre", "fecha", "endereco", "pagamento", "pix", "cartao",
                    "boleto", "troca", "devolucao", "devolver", "arrependimento", "arrependi",
                    "garantia", "frete", "envio", "lgpd", "privacidade", "reclamacao"]
    if any(w in t for w in policy_terms):
        return "policy"

    # Intenções genéricas precisam de esclarecimento, não de uma busca arbitrária.
    catalog_terms = ["catalogo", "catalog", "mostrar produtos", "ver produtos",
                     "quais produtos", "quais instrumentos", "o que voces vendem",
                     "instrumentos voces vendem", "lista de instrumentos"]
    if any(w in t for w in catalog_terms):
        return "catalog"

    if any(w in t for w in ["menor preco", "mais barato", "mais barata", "menor valor"]):
        return "sort_lowest_price"
    if any(w in t for w in ["maior preco", "mais caro", "mais cara", "maior valor"]):
        return "sort_highest_price"
    if any(w in t for w in ["maior estoque", "mais unidades", "mais disponivel"]):
        return "sort_highest_stock"

    category_terms = ["violao", "violoes", "guitarra", "guitarras", "baixo", "baixos",
                      "ukulele", "ukuleles", "bateria", "baterias", "percussao",
                      "teclado", "teclados", "piano", "pianos", "saxofone", "flauta",
                      "sopro", "cordas orquestrais", "violino", "violoncelo"]
    product_terms = ["takamine", "yamaha", "martin", "taylor", "tagima", "shelby",
                     "kalani", "kala", "ohana", "fender", "gibson", "ibanez", "prs",
                     "strinberg", "giannini", "rozini", "memphis", "modelo"]
    has_product_reference = any(w in t for w in category_terms + product_terms)
    has_product_question = any(w in t for w in ["preco", "quanto custa", "valor", "disponivel",
                                                 "disponibilidade", "estoque", "tem", "procuro",
                                                 "quero", "busco", "opcoes", "opcao"])
    if has_product_reference:
        return "product"
    if any(w in t for w in ["preco", "precos", "valor", "valores", "quanto custa"]):
        return "price_clarification"
    if any(w in t for w in ["disponibilidade", "disponivel", "estoque", "tem em estoque"]):
        return "availability_clarification"
    if has_product_question:
        return "product_clarification"
    return "general"

class EmporioAgent:
    def __init__(self, use_llm=True, history_dir="history"):
        self.use_llm=use_llm and bool(OPENAI_API_KEY)
        self.history_dir=Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)
        # Memória volátil isolada por sessão; não compartilha contexto entre clientes.
        self.sessions = {}

    def _get_session(self, session_id):
        key = str(session_id or "default")[:128]
        if key not in self.sessions:
            self.sessions[key] = {
                "name": None,
                "last_intent": None,
                "last_category": None,
                "last_products": [],
                "catalog_products": [],
                "last_budget": None,
                "preferred_specs": {},
                "recommended_product": None,
                "recommended_product_ids": [],
                "pending_action": None,
            }
        return self.sessions[key]

    def _tool_context(self, message, intent, session=None):
        data={}
        if intent in {"comparison", "recommendation", "recommendation_reason", "cheaper_alternative", "next_recommendation", "preference_update"} or intent.startswith("sort_"):
            source_products = (session or {}).get("catalog_products") or (session or {}).get("last_products", [])
            data["products"] = source_products[:50]
            data["recommended_product"] = (session or {}).get("recommended_product")
            if intent in {"next_recommendation", "cheaper_alternative"} and (session or {}).get("last_category"):
                budget = (session or {}).get("preferred_specs", {}).get("max_price")
                data["products"] = search_products(
                    category=(session or {}).get("last_category"),
                    max_price=budget,
                    available_only=True,
                    limit=50,
                )
            if intent == "recommendation" and not data["products"]:
                normalized = _normalize(message)
                recommendation_categories = {
                    "violao": "Violões", "violoes": "Violões",
                    "guitarra": "Guitarras", "guitarras": "Guitarras",
                    "baixo": "Baixos", "baixos": "Baixos",
                    "ukulele": "Ukuleles", "ukuleles": "Ukuleles",
                    "bateria": "Baterias e Percussão", "baterias": "Baterias e Percussão",
                    "percussao": "Baterias e Percussão",
                    "teclado": "Teclados e Pianos", "teclados": "Teclados e Pianos",
                    "piano": "Teclados e Pianos", "pianos": "Teclados e Pianos",
                    "saxofone": "Instrumentos de Sopro", "flauta": "Instrumentos de Sopro",
                    "sopro": "Instrumentos de Sopro",
                    "cordas orquestrais": "Cordas Orquestrais",
                    "violino": "Cordas Orquestrais", "violoncelo": "Cordas Orquestrais"
                }
                category = next((v for k, v in recommendation_categories.items() if k in normalized), None)
                if category:
                    data["products"] = search_products(
                        category=category, available_only=True, limit=15
                    )
        if intent == "catalog":
            data["categories"] = list_categories()
        if intent=="product":
            maximum=_extract_price(message)
            # Retira termos de intenção e usa a frase inteira para busca lexical.
            normalized = _normalize(message)
            category_map = {
                "violao": "Violões", "violoes": "Violões",
                "guitarra": "Guitarras", "guitarras": "Guitarras",
                "baixo": "Baixos", "baixos": "Baixos",
                "ukulele": "Ukuleles", "ukuleles": "Ukuleles",
                "bateria": "Baterias e Percussão", "baterias": "Baterias e Percussão",
                "percussao": "Baterias e Percussão",
                "teclado": "Teclados e Pianos", "teclados": "Teclados e Pianos",
                "piano": "Teclados e Pianos", "pianos": "Teclados e Pianos",
                "saxofone": "Instrumentos de Sopro", "flauta": "Instrumentos de Sopro",
                "sopro": "Instrumentos de Sopro",
                "cordas orquestrais": "Cordas Orquestrais",
                "violino": "Cordas Orquestrais", "violoncelo": "Cordas Orquestrais"
            }
            category = next((v for k,v in category_map.items() if k in normalized), None)
            known = ["Takamine GD20", "Yamaha C40", "Yamaha C70", "Martin D-28", "Taylor 110e"]
            term = next((name for name in known if name.lower() in message.lower()), None)
            if not term:
                brands = ["tagima", "yamaha", "fender", "gibson", "ibanez", "prs", "shelby",
                          "kalani", "kala", "ohana", "takamine", "martin", "taylor", "strinberg",
                          "giannini", "rozini", "memphis"]
                term = next((brand for brand in brands if re.search(rf"\b{re.escape(brand)}\b", normalized)), None)
            rows=search_products(term=term, category=category, max_price=maximum, available_only=True, limit=15)
            if not rows and term:
                rows=search_products(term=term, available_only=False, limit=8)
            data["products"]=rows
        elif intent=="promotion":
            data["promotions"]=active_promotions()
        elif intent=="order":
            order_id=_find_order_id(message)
            name_match=re.search(r"(?:nome|sou|cliente)\s*[:é]?\s*([A-Za-zÀ-ÿ ]{5,})", message, re.I)
            name=name_match.group(1).strip() if name_match else None
            # Por privacidade, pedido só é liberado com número + nome para validação.
            data["order_requires_validation"]=not (order_id and name)
            data["orders"]=lookup_order(order_id=order_id, customer_name=name) if order_id and name else []
        if intent in {"policy", "policy_topic"}:
            query = _policy_topic(message) or message
            data["policies"]=retrieve_policy(query, top_k=4)
        return data

    def _deterministic_response(self, message, intent, ctx):
        if intent.startswith("sort_"):
            rows = ctx.get("products", [])
            if not rows:
                return "Posso ordenar os resultados por preço ou estoque. Primeiro, me diga qual instrumento, categoria ou marca você está pesquisando."
            key = {"sort_lowest_price": "price_brl", "sort_highest_price": "price_brl",
                   "sort_highest_stock": "stock_quantity"}[intent]
            reverse = intent != "sort_lowest_price"
            ordered = sorted(rows, key=lambda p: float(p.get(key) or 0), reverse=reverse)
            label = {"sort_lowest_price": "menor preço", "sort_highest_price": "maior preço",
                     "sort_highest_stock": "maior quantidade em estoque"}[intent]
            lines = [f"- **{p['name']}** — {_money(p['price_brl'])}; estoque informado: {p['stock_quantity']} un." for p in ordered[:8]]
            return f"Ordenei os produtos da consulta anterior por {label}:\n" + "\n".join(lines) + "\n\nOs dados refletem os arquivos de demonstração, não uma conexão com estoque em tempo real."
        if intent == "recommendation_reason":
            selected = ctx.get("recommended_product")
            if not selected:
                return "Ainda não indiquei um modelo nesta conversa. Posso primeiro pesquisar as opções disponíveis e, em seguida, explicar os critérios da indicação."
            description = (selected.get("description") or "").strip()
            details = f" A descrição cadastrada informa: {description}" if description else " O catálogo não possui uma descrição detalhada desse modelo."
            return (
                f"Indiquei **{selected['name']}** porque, "
                f"conforme os dados cadastrados, ele custa {_money(selected['price_brl'])}."
                f"{details} "
                "Esse é o motivo da indicação preliminar; não representa uma avaliação independente de qualidade."
            )

        if intent == "cheaper_alternative":
            rows = ctx.get("products", [])
            selected = ctx.get("recommended_product")
            if not selected:
                return "Para procurar uma alternativa mais barata, primeiro preciso saber qual modelo estamos usando como referência. Quer que eu recomende um entre os produtos pesquisados?"
            reference_price = float(selected.get("price_brl") or 0)
            alternatives = [
                p for p in rows
                if p.get("product_id") != selected.get("product_id")
                and p.get("product_id") not in set(ctx.get("recommended_product_ids", []))
                and float(p.get("price_brl") or 0) < reference_price
                and _product_matches_preferences(p, ctx.get("preferred_specs", {}))
            ]
            alternatives.sort(key=lambda p: float(p.get("price_brl") or 0))
            if not alternatives:
                if not _product_matches_preferences(selected, ctx.get("preferred_specs", {})):
                    return (
                        f"Não encontrei uma alternativa abaixo de {_money(reference_price)} que também "
                        "atenda às preferências informadas. Posso ampliar o orçamento ou retirar algum filtro."
                    )
                return (
                    f"Entre os produtos desta consulta, **{selected['name']}** já é a opção de menor preço "
                    f"({_money(reference_price)}). Não encontrei outra opção abaixo desse valor na lista apresentada. "
                    "Posso pesquisar outras opções da categoria ou ampliar a faixa de preço."
                )
            lines = [
                f"- **{p['name']}** — {_money(p['price_brl'])} "
                f"(economia de {_money(reference_price - float(p['price_brl']))} em relação ao modelo indicado)"
                for p in alternatives[:5]
            ]
            return (
                f"Encontrei estas alternativas abaixo do preço de **{selected['name']}** "
                f"({_money(reference_price)}):\n" + "\n".join(lines)
                + "\n\nValores e disponibilidade conforme a base de demonstração."
            )

        if intent == "preference_update":
            preferences = ctx.get("preferred_specs", {})
            labels = []
            if preferences.get("strings"):
                labels.append("cordas de nylon" if preferences["strings"] == "nylon" else "cordas de aço")
            if preferences.get("brand"):
                labels.append(f"marca {preferences['brand'].title()}")
            if preferences.get("max_price") is not None:
                labels.append(f"preço até {_money(preferences['max_price'])}")
            detail = ", ".join(labels) if labels else "as preferências informadas"
            return f"Perfeito! Vou considerar {detail} nas próximas sugestões e manter o instrumento e a faixa de preço da nossa pesquisa. Quer que eu indique outra opção?"
        if intent == "next_recommendation":
            rows = ctx.get("products", [])
            if not rows:
                if ctx.get("last_category"):
                    return "Não encontrei outra opção disponível que atenda à categoria e aos filtros registrados nesta conversa. Posso ampliar o orçamento ou retirar alguma preferência."
                return "Posso indicar outra opção, sim! Qual instrumento ou categoria você procura? Se já tiver uma faixa de preço, pode me informar também."
            preferences = ctx.get("preferred_specs", {})
            excluded = set(ctx.get("recommended_product_ids", []))
            candidates = [
                product for product in rows
                if product.get("product_id") not in excluded
                and _product_matches_preferences(product, preferences)
            ]
            selected = _select_recommended_product(candidates)
            if not selected:
                return "Não encontrei outra opção disponível que atenda a todas as preferências registradas nesta conversa. Posso retirar algum filtro ou pesquisar outra categoria."
            description = (selected.get("description") or "").strip()
            answer = (
                f"Outra opção para avaliar é **{selected['name']}**. "
                f"Preço informado: {_money(selected['price_brl'])}; "
                f"estoque informado: {selected.get('stock_quantity', 'não informado')} unidade(s)."
            )
            if description:
                answer += f"\n\nDescrição cadastrada: {description}"
            if preferences.get("strings"):
                string_label = "nylon" if preferences["strings"] == "nylon" else "aço"
                answer += f"\n\nPreferência aplicada: cordas de {string_label}."
            answer += "\n\nA indicação considera os filtros informados e os dados da base de demonstração; não representa uma avaliação independente de qualidade."
            return answer

        if intent == "recommendation":
            rows = ctx.get("products", [])
            excluded = set(ctx.get("recommended_product_ids", []))
            rows = [product for product in rows if product.get("product_id") not in excluded]
            if not rows:
                return (
                    "Posso ajudar a escolher, sim! Qual instrumento você procura "
                    "(violão, guitarra, teclado etc.)? Se já tiver uma faixa de preço "
                    "em mente, pode me informar também."
                )

            preferences = ctx.get("preferred_specs", {})
            rows = [p for p in rows if _product_matches_preferences(p, preferences)]
            selected = _select_recommended_product(rows)
            candidates = [p for p in rows if _is_beginner_friendly(p)] or rows
            if selected is None:
                return "Não encontrei produtos suficientes no catálogo para formular uma indicação."
            description = (selected.get("description") or "").strip()
            stock = selected.get("stock_quantity", "não informado")
            answer = (
                f"Considerando apenas as informações cadastradas no catálogo, "
                f"uma opção para avaliar é **{selected['name']}**. "
                f"Preço informado: {_money(selected['price_brl'])}; "
                f"estoque informado: {stock} unidade(s)."
            )
            if description:
                answer += f"\n\nDescrição cadastrada: {description}"
            alternatives = [p for p in candidates if p.get("product_id") != selected.get("product_id")]
            if alternatives:
                alternatives = sorted(alternatives, key=lambda p: float(p.get("price_brl") or 0))[:2]
                answer += "\n\nOutras opções da consulta:"
                answer += "\n" + "\n".join(
                    f"- **{p['name']}** — {_money(p['price_brl'])}"
                    for p in alternatives
                )
            answer += (
                "\n\nEsta é uma indicação preliminar baseada na descrição e nos preços "
                "da base de demonstração, não uma avaliação independente de qualidade "
                "ou adequação. Para refinar a escolha, você prefere cordas de nylon ou aço?"
            )
            return answer
        if intent == "comparison":
            rows = ctx.get("products", [])
            if len(rows) < 2:
                if rows:
                    return f"Tenho o modelo **{rows[0]['name']}** como referência. Qual é o segundo modelo que você gostaria de comparar?"
                return "Claro! Quais são os dois modelos que você gostaria de comparar? Posso comparar preço e disponibilidade conforme os dados do catálogo."
            lines = [f"- **{p['name']}** — preço: {_money(p['price_brl'])}; estoque informado: {p['stock_quantity']} un.; categoria: {p.get('category') or 'não informada'}." for p in rows[:8]]
            return "Com base nos dados disponíveis no catálogo de demonstração, veja a comparação:\n" + "\n".join(lines) + "\n\nA comparação se limita aos campos existentes na base; não vou presumir características técnicas que não estejam cadastradas."
        if intent=="out_of_scope":
            return "A Empório da Música trabalha exclusivamente com instrumentos musicais e não comercializa acessórios como cordas, palhetas, cabos, cases, pedais ou amplificadores. Posso ajudar a encontrar um instrumento musical!"
        if intent == "catalog":
            categories = ctx.get("categories", [])
            if not categories:
                return "Não consegui carregar as categorias do catálogo neste momento. Posso encaminhar sua solicitação à equipe."
            lines = [f"- **{c['name']}** — {c['description']}" for c in categories]
            return "Trabalhamos com estas categorias de instrumentos musicais:\n" + "\n".join(lines) + "\n\nQual categoria você gostaria de conhecer melhor?"
        if intent == "price_clarification":
            return "Claro! Você procura o preço de qual instrumento ou modelo? Pode me dizer, por exemplo, violão, guitarra, teclado ou o nome do produto."
        if intent == "availability_clarification":
            return "Posso verificar a disponibilidade na base de demonstração. Qual instrumento ou modelo você procura?"
        if intent == "product_clarification":
            return "Posso pesquisar o catálogo. Qual instrumento, categoria ou modelo você procura? Se quiser, informe também uma faixa de preço."
        if intent=="product":
            rows=ctx.get("products",[])
            if not rows:
                normalized = _normalize(message)
                if "cordas orquestrais" in normalized or "violino" in normalized or "violoncelo" in normalized:
                    return "A categoria Cordas Orquestrais consta no catálogo, mas não há instrumentos dessa categoria disponíveis nos arquivos de demonstração fornecidos. Posso encaminhar a consulta à equipe para verificar outras possibilidades."
                return "Não encontrei uma opção que corresponda exatamente ao que você pediu na base disponível. Posso encaminhar sua busca para nossa equipe confirmar outras possibilidades. 🎵"
            max_price=_extract_price(message)
            intro="Encontrei estas opções disponíveis" + (f" até {_money(max_price)}" if max_price else "") + ":"
            lines=[]
            for p in rows[:8]:
                lines.append(f"- **{p['name']}** — {_money(p['price_brl'])} (estoque informado: {p['stock_quantity']} un.)")
            return intro+"\n"+"\n".join(lines)+"\n\nOs valores e quantidades refletem os arquivos de demonstração fornecidos, não uma conexão com estoque em tempo real. Quer que eu ajude a comparar algum modelo?"
        if intent=="promotion":
            rows=ctx.get("promotions",[])
            if not rows:
                return "Não localizei promoções ativas para produtos disponíveis na base fornecida. Posso pedir à equipe que confirme as campanhas vigentes."
            lines=[]
            for p in rows:
                new=float(p["price_brl"])*(1-float(p["discount_percent"])/100)
                lines.append(f"- **{p['name']}**: de {_money(p['price_brl'])} por **{_money(new)}** ({p['discount_percent']}% de desconto; {p['stock_quantity']} un. informada(s)).")
            return "Estas são as promoções marcadas como ativas na base de demonstração:\n"+"\n".join(lines)+"\n\nA base não informa datas de vigência; confirme a campanha com a equipe antes de fechar a compra. O desconto PIX não é cumulativo com promoção."
        if intent=="order":
            if ctx.get("order_requires_validation"):
                return "Posso ajudar a consultar! Por segurança, envie o número do pedido e o nome completo utilizado na compra. Não compartilhe dados de pagamento."
            rows=ctx.get("orders",[])
            if not rows:
                return "Não consegui validar esse pedido com os dados informados. Confira o número e o nome do titular ou fale com nossa equipe."
            o=rows[0]
            return f"Encontrei o pedido **#{o['order_id']}** em nome de {o['customer_name']}. Status informado: **{o['status']}**. " + (f"Rastreamento: {o['tracking_code']}. " if o['tracking_code'] else "Ainda não há código de rastreamento registrado. ") + (f"Previsão cadastrada: {o['estimated_delivery']}." if o['estimated_delivery'] else "A base não apresenta previsão de entrega.") + "\n\nEsses dados pertencem à base de demonstração e podem não refletir o status atual."
        if intent in {"policy", "policy_topic"}:
            chunks=ctx.get("policies",[])
            topic = _policy_topic(message)
            if topic:
                if not chunks:
                    return f"Não encontrei uma orientação específica sobre {topic} no manual fornecido. Recomendo confirmar esse ponto com a equipe da loja."
                label = POLICY_TOPIC_LABELS.get(topic, topic.capitalize())
                return f"O manual da Empório da Música informa sobre **{label}:**\n\n" + "\n\n".join(chunks[:2]) + "\n\nSe precisar, posso esclarecer outro assunto do manual."
            if not chunks:
                return "Não encontrei uma orientação suficientemente específica no manual fornecido. Para evitar uma informação incorreta, vou recomendar a confirmação com a gerência."
            generic_policy_question = _normalize(message) in {
                "politica", "politicas", "politica da loja", "politicas da loja",
                "explicar politica", "explicar politicas", "explicar politicas da loja",
                "quais sao as politicas", "quais sao as politicas da loja",
                "regras da loja", "me explique as politicas"
            }
            if generic_policy_question:
                topics = ["sobre a loja", "dados e contato", "horário de funcionamento", "pagamento",
                          "trocas e devoluções", "frete e entrega", "promoções", "atendimento",
                          "garantia", "privacidade e proteção de dados", "escalonamento de casos"]
                return "Claro! O manual da Empório da Música reúne orientações sobre:\n" + "\n".join(f"- {topic.capitalize()}" for topic in topics) + "\n\nQual desses assuntos você gostaria que eu explicasse primeiro?"
            # Mostra trecho pertinente sem alucinar resumo.
            return "Pelo manual de atendimento da loja:\n\n" + "\n\n".join(chunks[:2]) + "\n\nSe sua situação tiver algum detalhe específico, posso ajudar a identificar o trecho aplicável; casos excepcionais devem ser confirmados pela equipe."
        if any(w in message.lower() for w in ["corda", "palheta", "cabo", "case", "pedal", "amplificador"]):
            return "A Empório da Música trabalha exclusivamente com instrumentos musicais e não comercializa acessórios como cordas, palhetas, cabos, cases, pedais ou amplificadores. Posso ajudar a encontrar um instrumento musical!"
        return "Sou o assistente virtual da Empório da Música e posso ajudar com instrumentos musicais, catálogo, preços, disponibilidade, pedidos e políticas da loja. O que você gostaria de saber?"

    def _llm_rewrite(self, message, deterministic, ctx):
        try:
            from openai import OpenAI
            client=OpenAI(api_key=OPENAI_API_KEY)
            completion=client.chat.completions.create(
                model=MODEL,
                temperature=0.2,
                messages=[
                    {"role":"system","content":SYSTEM_PROMPT},
                    {"role":"user","content":f"MENSAGEM: {message}\nCONTEXTO (dados consultados): {json.dumps(ctx,ensure_ascii=False,default=str)}\nRESPOSTA BASE VALIDADA: {deterministic}\nReescreva com naturalidade sem adicionar fatos nem remover ressalvas importantes."}
                ]
            )
            return completion.choices[0].message.content or deterministic
        except Exception:
            # Falha do provedor não interrompe o atendimento nem invalida o resultado determinístico.
            return deterministic

    def respond(self, message, session_id="default"):
        clean = message.strip()
        if not clean:
            return "Pode me dizer como posso ajudar?"
        session = self._get_session(session_id)
        normalized = _normalize(clean)
        greetings = {"oi", "ola", "bom dia", "boa tarde", "boa noite", "opa", "e ai"}

        # Uma nova pesquisa explícita prevalece sobre qualquer etapa pendente.
        # Reinicia somente o contexto da pesquisa/recomendação, preservando a
        # identidade da sessão e o histórico de mensagens.
        if _is_explicit_catalog_search(clean):
            session["pending_action"] = None
            session["last_products"] = []
            session["catalog_products"] = []
            session["last_category"] = None
            session["last_budget"] = None
            session["preferred_specs"] = {}
            session["recommended_product"] = None
            session["recommended_product_ids"] = []
            intent = _route(clean)
        else:
            intent = None

        # Respostas curtas completam a etapa de refinamento de recomendação,
        # mas nunca podem interceptar uma nova pesquisa explícita.
        recommendation_pending = session.get("pending_action") in {
            "recommendation_preference", "recommendation_alternative"
        }
        if intent is None and recommendation_pending:
            extracted_preferences = _extract_recommendation_preferences(clean)
            if extracted_preferences:
                session.setdefault("preferred_specs", {}).update(extracted_preferences)
                if extracted_preferences.get("max_price") is not None:
                    session["last_budget"] = extracted_preferences["max_price"]
                session["pending_action"] = "recommendation_alternative"
                intent = "preference_update"
            elif any(term in normalized for term in ["mais barato", "mais barata", "menor preco", "abaixo"]):
                intent = "cheaper_alternative"
            elif _is_next_recommendation_request(clean):
                intent = "next_recommendation"
            else:
                intent = _route(clean)
        # Uma resposta curta pode completar uma pergunta anterior sobre políticas.
        elif intent is None and session.get("pending_action") == "policy_topic":
            topic = _policy_topic(clean)
            if topic:
                intent = "policy_topic"
            else:
                intent = _route(clean)
                if intent not in {"policy", "policy_topic"}:
                    session["pending_action"] = None
        elif intent is None:
            intent = _route(clean)

        # Se o agente pediu uma categoria/modelos para concluir comparação,
        # a próxima consulta de produto mantém a intenção de comparação pendente.
        if session.get("pending_action") == "comparison" and intent == "product":
            comparison_requested = True
        else:
            comparison_requested = False

        if intent == "general" and normalized in greetings:
            known_name = session.get("name")
            answer = f"Olá, {known_name}! Como posso ajudar hoje?" if known_name else "Olá! Seja bem-vindo à Empório da Música. Como posso ajudar?"
            self._save_history(session_id, clean, answer, "greeting")
            return answer

        if intent == "general" and _is_possible_name(clean):
            previous_name = session.get("name")
            if previous_name and _normalize(previous_name) == normalized:
                answer = f"Oi, {previous_name}! Estou por aqui. O que você gostaria de consultar?"
            else:
                session["name"] = clean.title()
                answer = f"Prazer, {session['name']}! 🎵 Como posso ajudar? Posso mostrar nosso catálogo, consultar preços, verificar disponibilidade ou explicar as políticas da loja."
            self._save_history(session_id, clean, answer, "name")
            return answer

        # Tópicos de política: a solicitação geral abre um estado pendente;
        # a resposta curta seguinte é interpretada como tópico, nunca como nome.
        if intent == "policy":
            session["pending_action"] = "policy_topic"
        elif intent == "policy_topic":
            session["pending_action"] = None

        if intent == "comparison":
            rows = session.get("last_products", [])
            if len(rows) < 2:
                session["pending_action"] = "comparison"
            else:
                session["pending_action"] = None

        ctx = self._tool_context(clean, intent, session)
        ctx["preferred_specs"] = dict(session.get("preferred_specs", {}))
        ctx["recommended_product_ids"] = list(session.get("recommended_product_ids", []))
        ctx["last_category"] = session.get("last_category")
        answer = self._deterministic_response(clean, intent, ctx)

        if intent in {"recommendation", "next_recommendation"}:
            available_rows = [
                product for product in ctx.get("products", [])
                if _product_matches_preferences(product, session.get("preferred_specs", {}))
                and product.get("product_id") not in set(session.get("recommended_product_ids", []))
            ]
            selected = _select_recommended_product(available_rows)
            if selected:
                session["recommended_product"] = dict(selected)
                ids = session.setdefault("recommended_product_ids", [])
                if selected.get("product_id") not in ids:
                    ids.append(selected.get("product_id"))
                session["pending_action"] = "recommendation_preference"
            elif intent == "next_recommendation":
                session["pending_action"] = "recommendation_alternative"
        if intent == "product":
            rows = ctx.get("products", [])
            session["last_products"] = rows[:8] if rows else []
            session["catalog_products"] = rows[:50] if rows else []
            maximum = _extract_price(clean)
            if maximum is not None:
                session["last_budget"] = maximum
                session.setdefault("preferred_specs", {})["max_price"] = maximum
            if rows:
                session["last_intent"] = "product"
                session["last_category"] = rows[0].get("category")
                if comparison_requested:
                    session["pending_action"] = "comparison"
                    answer += "\n\nComo você havia pedido uma comparação, posso comparar esses modelos por preço e disponibilidade. Digite **comparar modelos** para continuar."
            elif comparison_requested:
                session["pending_action"] = "comparison"
            elif session.get("pending_action") != "comparison":
                session["last_products"] = []
        elif intent == "catalog":
            # Não apaga uma comparação pendente: o cliente pode consultar o catálogo
            # antes de escolher a categoria que deseja comparar.
            if session.get("pending_action") != "comparison":
                session["last_intent"] = intent
        elif intent not in {"comparison", "recommendation", "general", "policy", "policy_topic"} and not intent.startswith("sort_"):
            session["last_intent"] = intent

        if self.use_llm and intent in {"catalog", "product", "promotion", "order", "policy", "policy_topic", "general"}:
            answer = self._llm_rewrite(clean, answer, ctx)
        self._save_history(session_id, clean, answer, intent)
        return answer

    def _save_history(self, session_id, user_message, assistant_message, intent):
        safe=re.sub(r"[^a-zA-Z0-9_-]","_",session_id)[:64] or "default"
        path=self.history_dir/f"{safe}.jsonl"
        record={"timestamp":datetime.now().isoformat(timespec="seconds"),"intent":intent,
                "user":user_message,"assistant":assistant_message}
        with path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(record,ensure_ascii=False)+"\n")
