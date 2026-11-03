"""Ferramentas determinísticas: nenhuma informação comercial é inventada pelo LLM."""
import re
from .database import query

def _money(value):
    return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def search_products(term=None, category=None, max_price=None, available_only=True, limit=12):
    sql = """SELECT p.product_id, p.name, p.price_brl, p.stock_quantity, p.status,
                    c.name AS category
             FROM products p LEFT JOIN categories c ON c.category_id=p.category_id
             WHERE 1=1"""
    params = []
    if term:
        words = [w for w in re.findall(r"[\wÀ-ÿ]+", term) if len(w) > 2]
        for word in words:
            sql += " AND p.name LIKE ?"
            params.append(f"%{word}%")
    if category:
        sql += " AND c.name LIKE ?"
        params.append(f"%{category}%")
    if max_price is not None:
        sql += " AND p.price_brl <= ?"
        params.append(float(max_price))
    if available_only:
        sql += " AND p.status='active' AND p.stock_quantity > 0"
    sql += " ORDER BY p.price_brl ASC LIMIT ?"
    params.append(int(limit))
    return query(sql, params)

def list_categories():
    """Retorna as categorias existentes no catálogo, sem inventar opções."""
    sql = """SELECT name, description FROM categories ORDER BY name"""
    return query(sql)

def product_details(term):
    rows = search_products(term=term, available_only=False, limit=8)
    if not rows:
        return []
    return rows

def active_promotions(term=None):
    sql = """SELECT p.product_id, p.name, p.price_brl, p.stock_quantity,
                    pr.discount_percent, pr.description AS promotion
             FROM promotions pr JOIN products p ON p.product_id=pr.product_id
             WHERE pr.is_active=1 AND p.status='active' AND p.stock_quantity>0"""
    params=[]
    if term:
        sql += " AND p.name LIKE ?"
        params.append(f"%{term}%")
    sql += " ORDER BY pr.discount_percent DESC"
    return query(sql, params)

def lookup_order(order_id=None, customer_name=None):
    sql = """SELECT o.order_id, o.order_date, o.status, o.total_brl, o.payment_method,
                    o.tracking_code, o.estimated_delivery, o.notes, c.name AS customer_name
             FROM orders o JOIN customers c ON c.customer_id=o.customer_id WHERE 1=1"""
    params=[]
    if order_id is not None and customer_name:
        sql += " AND o.order_id=? AND lower(c.name) LIKE ?"
        params.extend([int(order_id), f"%{customer_name.lower()}%"])
    else:
        return []
    sql += " ORDER BY o.order_date DESC LIMIT 5"
    return query(sql, params)

def lookup_customer_orders(name):
    """Busca por nome completo/parte; agente não deve expor pedidos de terceiros."""
    sql = """SELECT o.order_id, o.status, o.total_brl, o.tracking_code, o.estimated_delivery,
                    c.name AS customer_name
             FROM orders o JOIN customers c ON c.customer_id=o.customer_id
             WHERE lower(c.name) LIKE ? ORDER BY o.order_date DESC LIMIT 5"""
    return query(sql, (f"%{name.lower()}%",))

def format_product(row):
    stock = f"{row['stock_quantity']} unidade(s)" if row['stock_quantity'] else "sem estoque"
    return f"**{row['name']}** — {_money(row['price_brl'])} | Estoque: {stock}"

def list_tools():
    return {
        "buscar_produtos": "Pesquisa catálogo por termo, categoria e preço máximo; retorna apenas itens ativos e em estoque por padrão.",
        "detalhar_produto": "Consulta preço, status e estoque de um produto específico.",
        "consultar_promocoes": "Consulta promoções marcadas como ativas no conjunto de dados.",
        "consultar_pedido": "Consulta pedido por número ou nome informado pelo cliente; não deve revelar dados de terceiros."
    }
