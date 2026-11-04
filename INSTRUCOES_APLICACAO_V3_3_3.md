# Aplicação do patch — Empório AI Agent V3.3.3

Este pacote contém somente os arquivos alterados ou adicionados para a V3.3.3.
Não contém `.git`, ambiente virtual, banco SQLite local, histórico de conversas,
credenciais ou arquivos específicos da máquina.

## Aplicação

1. Confirme que está na branch `feature/v3.3.3-contextual-refinement`.
2. Confirme que não há alterações locais que precisem ser preservadas (`git status`).
3. Extraia o conteúdo deste ZIP na raiz do repositório `emporio_ai_agent`,
   permitindo substituir os arquivos existentes e mantendo a estrutura de pastas.
4. Preserve a pasta `.git`, seu banco local e seus arquivos de ambiente.
5. No PowerShell, com o ambiente virtual ativado, execute:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m compileall -q src tests
git diff --check
git status
git diff --stat
```

A suíte deve apresentar **68 passed**: 54 testes de regressão da V3.3.2
e 14 novos testes da V3.3.3.

## Teste manual recomendado

Execute:

```powershell
python -m emporio_agent --no-llm
```

Conduza a sequência:

```text
Quais opções de violões até R$ 1000?
Qual você recomenda para começar?
Por que você recomenda esse modelo?
Nylon.
Então me indique outra opção.
Me indique mais uma opção.
```

O agente deve recomendar inicialmente o Tagima Memphis AC-39, registrar a preferência
por nylon e sugerir em seguida o Rozini RC-104 e o Yamaha C40, sem repetir os modelos
já indicados.

Teste adicional de marca/orçamento:

```text
Quais opções de violões até R$ 500?
Qual você recomenda para começar?
Yamaha até R$ 1500.
Outra opção.
```

O agente deve atualizar o orçamento e consultar novamente a categoria, retornando uma
opção Yamaha dentro do novo limite.

## Importante

- A V3.3.2 permanece preservada na tag `v3.3.2`.
- Não faça commit nem crie a tag `v3.3.3` antes de validar localmente no Windows.
- O resultado de 68 testes registrado neste pacote foi executado no ambiente de
  validação Python 3.13.5. A execução local no ambiente Windows/Python 3.12 ainda
  deve ser confirmada.
