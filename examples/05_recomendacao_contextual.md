# Example 5 — Contextual recommendation refinement

> **Demonstration note:** this conversation uses the supplied demonstration catalog. Prices and stock quantities are dataset values, not live inventory.

**Customer:** Quais opções de violões até R$ 1.000?

**Agent:** Encontra e lista os violões disponíveis dentro do orçamento consultado.

**Customer:** Qual você recomenda para começar?

**Agent:** Considerando as descrições cadastradas, apresenta o Tagima Memphis AC-39 Nylon Natural como uma opção para avaliar e explica os dados que fundamentam a indicação.

**Customer:** Por que você recomenda esse modelo?

**Agent:** Explica a indicação usando o preço e a descrição cadastrada, sem afirmar uma avaliação independente de qualidade.

**Customer:** Nylon.

**Agent:** Registra a preferência por cordas de nylon e mantém a categoria e o orçamento da consulta anterior.

**Customer:** Então me indique outra opção.

**Agent:** Apresenta o Rozini RC-104 Nylon Estudante, sem repetir o Tagima Memphis AC-39 e respeitando os filtros ativos.

**Customer:** Me indique mais uma opção.

**Agent:** Apresenta o Yamaha C40 Nylon Natural, sem repetir os dois modelos anteriores.

## Engineering notes

- The short answer "Nylon" is interpreted as a preference because the agent is awaiting recommendation refinement.
- Preference state and recommended product IDs are scoped to the current session.
- The next recommendation is filtered against the catalog's structured `specs` and description.
- The selection is a deterministic catalog heuristic, not an independent quality assessment.
