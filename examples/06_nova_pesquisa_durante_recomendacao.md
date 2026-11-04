# Example 06 — Starting a new catalog search during recommendation

**Purpose:** Demonstrate that an explicit new product search supersedes a pending recommendation refinement and starts a fresh catalog context.

```text
Customer: Quais opções de violões até R$ 1000?
Agent: Lists available guitars within the R$ 1,000 demonstration-data budget.

Customer: Qual você recomenda para começar?
Agent: Recommends Tagima Memphis AC-39 Nylon Natural using its catalog description.

Customer: Nylon.
Agent: Records nylon as a preference for the current recommendation flow.

Customer: Quais opções de violões até R$ 500?
Agent: Starts a new catalog search, clears the previous recommendation filters/history, and lists Tagima Memphis AC-39 and Rozini RC-104 within R$ 500.

Customer: Qual você recomenda para começar?
Agent: Recommends from the new result set, rather than reusing the earlier R$ 1,000 search context.

Customer: Yamaha até R$ 1500.
Agent: Applies Yamaha and the new R$ 1,500 maximum as refinements to the active recommendation flow.

Customer: Outra opção.
Agent: Returns another matching Yamaha product, excluding products already recommended in the current search context.
```

**Behavioral note:** The example is a functional scenario, not a claim that the agent uses a general-purpose language model to infer arbitrary preferences. Intent and preference handling are deterministic rules. Product and stock facts come from the supplied demonstration catalog.
