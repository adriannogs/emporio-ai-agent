# Empório da Música — AI Customer Service Agent

Protótipo de agente conversacional em Python para o desafio técnico de AI Engineer da Artefact. O projeto combina roteamento de intenção, ferramentas determinísticas sobre SQLite, recuperação lexical de políticas (RAG leve) e um LLM opcional para naturalizar a resposta.

> **Importante sobre os dados:** os CSVs fornecidos são um snapshot de demonstração, com registros de pedidos entre outubro de 2025 e março de 2026. O agente não está conectado ao ERP/estoque da loja. Portanto, ele informa explicitamente que preço, quantidade, promoções e status refletem os arquivos fornecidos, e não dados em tempo real. Nunca afirma ter consultado um sistema de produção.

## 1. Funcionalidades

- Catálogo: busca por categoria/modelo, preço e disponibilidade.
- Promoções: consulta `is_active=1`, verifica produto ativo e estoque positivo e calcula o preço promocional.
- Pedidos: consulta status e rastreamento mediante número do pedido **e nome do titular**.
- Políticas: recuperação de trechos do manual sobre horário, pagamentos, trocas/devoluções, frete, garantia, escopo e LGPD.
- Escopo: redireciona pedidos de acessórios e perguntas sem relação com a loja.
- Histórico: grava conversas em JSONL por sessão (diretório `history/`, ignorado pelo Git).
- Modo local determinístico: funciona sem chave de API.
- Modo LLM opcional: OpenAI é usado somente para reescrever a resposta validada; não decide preço, estoque, status ou política e não substitui as consultas estruturadas.

## 2. Arquitetura e decisões técnicas

### Abordagem: híbrida (roteamento + tools + RAG)

1. **Roteamento de intenção:** regras explícitas e auditáveis identificam consulta de produto, promoção, pedido, política ou assunto geral. Para o escopo pequeno do desafio, essa solução reduz dependência de classificação probabilística e facilita testes. Em evolução, pode ser substituída/complementada por classificação via LLM.
2. **Tools determinísticas:** `tools.py` consulta SQLite com parâmetros SQL. Dados transacionais não são gerados pelo modelo. O banco é reconstruído a partir dos CSVs.
3. **RAG lexical:** `policies.py` divide o manual em seções e recupera os trechos com maior sobreposição lexical. É intencionalmente leve, sem embeddings ou serviço vetorial externo, suficiente para o corpus curto fornecido. Em produção, eu avaliaria embeddings multilíngues, reranking e avaliação de retrieval.
4. **LLM opcional:** quando `OPENAI_API_KEY` está configurada, o modelo recebe a mensagem, os resultados das ferramentas e uma resposta-base validada. Sua tarefa é somente melhorar a fluidez sem adicionar fatos. Se a API falhar, o agente retorna a resposta determinística.
5. **Persistência:** SQLite simplifica o protótipo reproduzível; JSONL mantém histórico por sessão. Em produção, usaria PostgreSQL, gestão de sessão e retenção configurável.
6. **Interface:** CLI para priorizar execução local no VS Code e reduzir componentes não solicitados pelo desafio.

### Por que não usar um agente autônomo com SQL livre?

O conjunto de operações é conhecido e sensível a precisão. Consultas parametrizadas e funções limitadas são mais previsíveis, seguras e testáveis do que permitir que o LLM gere SQL arbitrário. A seleção da ferramenta é explícita no roteador; o modelo não tem acesso direto ao banco.

## 3. Estrutura do projeto

```text
emporio-ai-agent/
├── data/
│   ├── categories.csv
│   ├── customers.csv
│   ├── order_items.csv
│   ├── orders.csv
│   ├── products.csv
│   ├── promotions.csv
│   └── politicas.md
├── examples/
│   ├── 01_catalogo_violao.md
│   ├── 02_preco_produto.md
│   ├── 03_pedido_rastreamento.md
│   └── 04_devolucao_e_escopo.md
├── src/emporio_agent/
│   ├── agent.py
│   ├── cli.py
│   ├── config.py
│   ├── database.py
│   ├── policies.py
│   └── tools.py
├── tests/
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 4. Executar no VS Code

### Pré-requisitos
- Python 3.10 ou superior (recomendado 3.11/3.12).
- VS Code com extensão Python da Microsoft.
- Git (para publicar o repositório).

### Windows PowerShell

Abra a pasta do projeto no VS Code (`File > Open Folder`) e, no terminal integrado, execute:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
Copy-Item .env.example .env
```

O banco é criado automaticamente ao iniciar o CLI. Para iniciar:

```powershell
python -m emporio_agent
```

Para reconstruir o SQLite do zero a partir dos CSVs:

```powershell
python -m emporio_agent --rebuild-db
```

Se o PowerShell bloquear a ativação do ambiente, execute uma vez na sessão:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
cp .env.example .env
python -m emporio_agent
```

### Modo LLM (opcional)

Sem `OPENAI_API_KEY`, o projeto funciona localmente em modo determinístico. Para habilitar a reformulação via OpenAI, preencha `.env`:

```env
OPENAI_API_KEY=sua_chave
OPENAI_MODEL=gpt-4o-mini
```

Reinicie o CLI. A chave nunca deve ser commitada. Para forçar o modo sem LLM mesmo com chave configurada:

```bash
python -m emporio_agent --no-llm
```

### Comandos úteis

- `python -m emporio_agent`: inicia o atendimento.
- `python -m emporio_agent --rebuild-db`: recria o banco SQLite.
- `python -m emporio_agent --no-llm`: modo local sem API.
- `python -m pytest -q`: executa testes automatizados.
- Digite `sair` para encerrar.

## 5. Exemplos de perguntas

- `Quais opções de violões disponíveis custando até R$ 1000?`
- `Quanto custa o Takamine GD20?`
- `Qual é o horário de funcionamento no sábado?`
- `Posso devolver uma compra online?`
- `Onde está meu pedido 8?` (o agente solicita validação do titular)
- `Pedido 8, nome Ana Carolina Ferreira` (consulta demonstração após validação mínima)
- `Vocês vendem cordas para violão?`

As conversas de referência estão em `examples/`.

## 6. Tratamento de dados e segurança

- CSVs são carregados em SQLite por `pandas`; operações usam parâmetros SQL.
- Consulta de pedido exige número + nome do titular; não há listagem de clientes.
- O agente não revela dados de contato de clientes.
- O histórico local pode conter mensagens pessoais: mantenha `history/` fora do Git, restrinja acesso e defina retenção antes de produção.
- `.env`, banco gerado e histórico estão no `.gitignore`.
- Não há execução de SQL arbitrário produzido pelo LLM.
- O protótipo não realiza cancelamentos, reembolsos, alterações ou reservas; casos desse tipo devem ser encaminhados à equipe.

## 7. Premissas e inconsistências encontradas nas fontes

As ambiguidades foram preservadas e documentadas, sem inventar uma resposta:

1. **Contato:** o manual informa `(67) 3341-4444` na seção de dados da empresa (página 2), mas `(67) 3321-4500` na seção de WhatsApp (página 6). O agente não escolhe um número como definitivo; recomenda confirmação humana.
2. **E-mail:** o documento contém grafias com e sem acento no domínio. Não é necessário ao fluxo de demonstração; evitaria automatizar envio até confirmar o endereço oficial.
3. **Parcelamento:** a tabela geral menciona parcela mínima de R$ 100 para crédito até 12x; as regras detalhadas estabelecem mínimos diferentes para 1–3x, 4–6x e 7–12x. O manual estruturado preserva ambas as informações e orienta confirmação para simulações específicas.
4. **Promoções:** `promotions.csv` possui `is_active`, mas não possui data de início/fim. A aplicação usa apenas a flag e alerta que a vigência precisa ser confirmada.
5. **Atualidade:** os pedidos do CSV vão até março de 2026; não representam necessariamente o estado atual em produção. O agente declara que trabalha com snapshot de demonstração.
6. **Dados de clientes:** os arquivos contêm dados pessoais. Foram mantidos apenas para viabilizar a consulta demonstrativa solicitada; o projeto não os expõe em buscas gerais. Para publicação, avaliar se os CSVs originais devem permanecer públicos; em caso de dados reais, remover/anonimizar antes de qualquer push.

## 8. Limitações conhecidas e próximos passos

- Roteador por regras: ampliar sinônimos, cobrir mais categorias e adicionar fallback de classificação semântica avaliado.
- RAG lexical: migrar para embeddings, reranker, citações por seção e conjunto de perguntas de avaliação.
- Dados estáticos: conectar ERP/CRM/estoque com autenticação, atualização incremental e observabilidade.
- Identidade do cliente: autenticação real (OTP ou canal verificado) em vez de validação por nome.
- Histórico: banco com criptografia, política de retenção, consentimento e exclusão conforme LGPD.
- Atendimento humano: integração com CRM/help desk, fila e SLA de 24 horas úteis para reclamações.
- Testes: adicionar avaliação offline de precisão de roteamento, groundedness, retrieval e segurança contra prompt injection.

## 9. Uso de assistente de código

O ChatGPT foi utilizado como assistente de desenvolvimento para apoiar a leitura do enunciado e das fontes, estruturar a arquitetura, implementar o protótipo, escrever documentação e sugerir testes. As decisões e o código devem ser revisados e compreendidos pelo candidato antes da entrega; a validação local e a autoria do histórico Git devem refletir o trabalho efetivamente realizado pelo candidato.

## 10. Checklist de entrega

- [ ] Criar repositório público no GitHub.
- [ ] Revisar se os CSVs podem ser publicados; anonimizar dados pessoais se necessário.
- [ ] Executar `pip install -r requirements.txt`.
- [ ] Executar `python -m emporio_agent --rebuild-db`.
- [ ] Executar `python -m pytest -q`.
- [ ] Testar manualmente os exemplos no CLI.
- [ ] Revisar README e exemplos.
- [ ] Fazer commits progressivos e reais; não concentrar tudo em um commit artificial.
- [ ] Enviar o link do repositório respondendo ao e-mail do processo seletivo.
- [ ] Não alterar o repositório após o prazo/data de entrega informados pela Artefact.
