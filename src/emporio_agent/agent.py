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
    "mais caro", "maior estoque", "menor estoque", "ordenar por preco"
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
            self.sessions[key] = {"name": None, "last_intent": None,
                                  "last_category": None, "last_products": [],
                                  "pending_action": None}
        return self.sessions[key]

    def _tool_context(self, message, intent, session=None):
        data={}
        if intent == "comparison" or intent.startswith("sort_"):
            data["products"] = (session or {}).get("last_products", [])[:8]
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

        # Uma resposta curta pode completar uma pergunta anterior sobre políticas.
        if session.get("pending_action") == "policy_topic":
            topic = _policy_topic(clean)
            if topic:
                intent = "policy_topic"
            else:
                intent = _route(clean)
                if intent not in {"policy", "policy_topic"}:
                    session["pending_action"] = None
        else:
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
        answer = self._deterministic_response(clean, intent, ctx)

        if intent == "product":
            rows = ctx.get("products", [])
            session["last_products"] = rows[:8] if rows else []
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
        elif intent not in {"comparison", "general", "policy", "policy_topic"} and not intent.startswith("sort_"):
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
