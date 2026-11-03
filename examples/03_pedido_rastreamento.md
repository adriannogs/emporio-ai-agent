# Exemplo 3 — Situação não trivial: consulta de pedido com validação mínima

**Cliente:** Onde está meu pedido 8?

**Agente:** Posso ajudar a consultar! Por segurança, envie o número do pedido e o nome completo utilizado na compra. Não compartilhe dados de pagamento.

**Cliente:** Pedido 8, nome Ana Carolina Ferreira.

**Agente:** Encontrei o pedido **#8** em nome de Ana Carolina Ferreira. Status informado: **shipped**. Rastreamento: **BRJL5544332BR**. Previsão cadastrada: **2026-02-28**.

Esses dados pertencem à base de demonstração e podem não refletir o status atual.

**Nota:** a base de pedidos fornecida contém registros até março de 2026. A consulta exige número e nome, mas isso não equivale a autenticação robusta de titularidade. Em produção, substituir por OTP ou canal autenticado.
