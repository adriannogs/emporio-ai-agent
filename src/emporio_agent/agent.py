import json
import re
from datetime import datetime
from pathlib import Path
from .config import OPENAI_API_KEY, MODEL
from .policies import retrieve_policy
from .tools import search_products, product_details, active_promotions, lookup_order, format_product

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

def _route(message):
    t=message.lower()
    if any(w in t for w in ["corda", "palheta", "cabo", "case", "pedal", "amplificador", "acessório", "acessorio"]):
        return "out_of_scope"
    if any(w in t for w in ["pedido", "rastreamento", "rastrear", "entrega do meu", "onde está meu"]):
        return "order"
    if any(w in t for w in ["promoção", "promocao", "desconto", "oferta", "black friday"]):
        return "promotion"
    if any(w in t for w in ["preço", "preco", "quanto custa", "valor do", "disponível", "disponivel", "estoque", "violão", "violao", "guitarra", "baixo", "ukulele", "bateria", "teclado", "saxofone", "instrumento", "violões", "guitarras", "baixos", "ukuleles", "baterias", "teclados"]):
        return "product"
    policy_terms=["horário","horario","abre","fecha","endereço","endereco","pagamento","pix","cartão","cartao","boleto","troca","devolução","devolucao","devolver","arrependimento","arrependi","garantia","frete","envio","entrega","lgpd","privacidade","reclamação","reclamacao"]
    if any(w in t for w in policy_terms):
        return "policy"
    return "general"

class EmporioAgent:
    def __init__(self, use_llm=True, history_dir="history"):
        self.use_llm=use_llm and bool(OPENAI_API_KEY)
        self.history_dir=Path(history_dir)
        self.history_dir.mkdir(exist_ok=True)

    def _tool_context(self, message, intent):
        data={}
        if intent=="product":
            maximum=_extract_price(message)
            # Retira termos de intenção e usa a frase inteira para busca lexical.
            category_map = {
                "violão": "Violões", "violões": "Violões", "violao": "Violões",
                "guitarra": "Guitarras", "guitarras": "Guitarras", "baixo": "Baixos", "baixos": "Baixos",
                "ukulele": "Ukuleles", "ukuleles": "Ukuleles", "bateria": "Baterias", "baterias": "Baterias",
                "teclado": "Teclados", "teclados": "Teclados", "saxofone": "Sopro", "flauta": "Sopro"
            }
            category = next((v for k,v in category_map.items() if k in message.lower()), None)
            known = ["Takamine GD20", "Yamaha C40", "Yamaha C70", "Martin D-28", "Taylor 110e"]
            term = next((name for name in known if name.lower() in message.lower()), None)
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
        if intent=="policy":
            data["policies"]=retrieve_policy(message, top_k=4)
        return data

    def _deterministic_response(self, message, intent, ctx):
        if intent=="out_of_scope":
            return "A Empório da Música trabalha exclusivamente com instrumentos musicais e não comercializa acessórios como cordas, palhetas, cabos, cases, pedais ou amplificadores. Posso ajudar a encontrar um instrumento musical!"
        if intent=="product":
            rows=ctx.get("products",[])
            if not rows:
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
        if intent=="policy":
            chunks=ctx.get("policies",[])
            if not chunks:
                return "Não encontrei uma orientação suficientemente específica no manual fornecido. Para evitar uma informação incorreta, vou recomendar a confirmação com a gerência."
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
        intent=_route(message)
        ctx=self._tool_context(message,intent)
        answer=self._deterministic_response(message,intent,ctx)
        if self.use_llm and intent in {"product","promotion","order","policy","general"}:
            answer=self._llm_rewrite(message,answer,ctx)
        self._save_history(session_id,message,answer,intent)
        return answer

    def _save_history(self, session_id, user_message, assistant_message, intent):
        safe=re.sub(r"[^a-zA-Z0-9_-]","_",session_id)[:64] or "default"
        path=self.history_dir/f"{safe}.jsonl"
        record={"timestamp":datetime.now().isoformat(timespec="seconds"),"intent":intent,
                "user":user_message,"assistant":assistant_message}
        with path.open("a",encoding="utf-8") as f:
            f.write(json.dumps(record,ensure_ascii=False)+"\n")
