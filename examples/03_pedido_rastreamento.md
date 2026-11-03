# Exemplo 3 — Situação não trivial: consulta de pedido (simulação histórica)

> **Contexto da demonstração:** esta conversa é uma simulação baseada exclusivamente na base fictícia fornecida para o desafio. O registro consultado contém uma previsão de entrega em **28/02/2026**, data passada em relação à elaboração deste exemplo. Portanto, a informação não representa rastreamento atual nem comprova a situação real de uma entrega.

**Cliente:** Onde está meu pedido 8?

**Agente:** Posso consultar o pedido 8. Para localizar o registro correspondente, informe o nome completo utilizado na compra. Não envie dados de pagamento ou documentos pessoais.

**Cliente:** Ana Carolina Ferreira.

**Agente:** Encontrei o pedido **#8**, cadastrado em nome de Ana Carolina Ferreira. Na base demonstrativa, o status consta como **enviado (shipped)**. O código de rastreamento registrado é **BRJL5544332BR** e a previsão de entrega cadastrada era **28/02/2026**.

Lembre-se: esses são dados históricos da base de demonstração, não uma consulta a uma transportadora ou a um sistema de pedidos em tempo real.

**Nota sobre segurança:** neste protótipo, a consulta combina o número do pedido com o nome informado pelo cliente como uma validação mínima de correspondência. Esses dois dados, isoladamente, **não constituem autenticação robusta nem comprovam a titularidade do pedido**. Em um ambiente de produção, a consulta deveria ocorrer por um canal autenticado ou mediante um mecanismo adicional de verificação, como código de uso único (OTP), sem expor informações do pedido antes da validação.
