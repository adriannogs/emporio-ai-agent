# Aplicação do patch V3.3.4

## Objetivo

Corrigir a prioridade de roteamento quando o cliente inicia uma nova pesquisa de catálogo durante um fluxo de recomendação ainda pendente. A nova pesquisa passa a substituir o contexto ativo de busca/recomendação, sem apagar a identidade do cliente nem o histórico da conversa.

## Arquivos incluídos

- `src/emporio_agent/agent.py` — detecção de pesquisa explícita e reset delimitado do contexto.
- `tests/test_agent.py` — cinco testes de regressão.
- `pyproject.toml` — versão 3.3.4.
- `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `AI_USAGE.md` — documentação técnica atualizada em inglês, mantendo o padrão do projeto.
- `examples/06_nova_pesquisa_durante_recomendacao.md` — novo cenário funcional documentado.
- `evidence/README.md` e `evidence/test_results.txt` — evidência de validação no ambiente isolado.

## Antes de aplicar

1. Abra o PowerShell na raiz do repositório local.
2. Confirme que está na branch de trabalho `feature/v3.3.3-contextual-refinement`.
3. Verifique `git status` e faça backup de qualquer alteração local ainda não commitada.
4. Não substitua nem remova `.git`, `.venv`, `data/emporio.db`, arquivos `.env` ou configurações locais.

## Aplicação

Extraia o conteúdo da pasta `emporio_ai_agent` deste ZIP para a raiz do projeto, permitindo substituir os arquivos correspondentes. Preserve os diretórios e arquivos locais mencionados acima.

## Validação obrigatória no Windows/Python 3.12

Execute na raiz do projeto:

```powershell
python --version
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q src tests
git diff --check
git status --short
git diff --stat
```

Resultado esperado da suíte: `73 passed`. A versão Python local deve ser registrada; o resultado incluído em `evidence/test_results.txt` foi obtido com Python 3.13.5 e não substitui a validação no ambiente Windows/Python 3.12 do mantenedor.

## Teste manual de regressão

Execute:

```powershell
python -m emporio_agent --no-llm
```

Na mesma sessão, envie as mensagens abaixo, uma por vez:

```text
Quais opções de violões até R$ 1000?
Qual você recomenda para começar?
Nylon.
Quais opções de violões até R$ 500?
Qual você recomenda para começar?
Yamaha até R$ 1500.
Outra opção.
```

Comportamento esperado:

- A consulta de até R$ 500 deve listar novamente os produtos, sem responder como se fosse apenas uma preferência.
- A nova consulta deve remover o filtro de nylon herdado da pesquisa anterior, pois o cliente não o repetiu.
- A recomendação seguinte deve usar exclusivamente os resultados da nova pesquisa.
- `Yamaha até R$ 1500` deve continuar funcionando como refinamento da recomendação ativa.
- `Outra opção` deve retornar um Yamaha compatível com o orçamento e não repetir produtos já recomendados no contexto atual.

## Publicação

Não faça commit, merge ou tag antes de confirmar os testes automatizados e o teste manual no ambiente local. Após a validação, envie as saídas de `pytest`, `compileall`, `git diff --check`, `git status --short` e `git diff --stat` para revisão.

Commit sugerido, somente após aprovação:

```text
fix: prioritize explicit catalog searches over pending recommendations
```

A branch e a tag `v3.3.3` devem permanecer preservadas. A V3.3.4 só deve ser publicada depois da validação local e da revisão final do diff.
