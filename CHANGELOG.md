# Changelog

All notable project changes are documented in this file.

The project uses a simple versioning convention. The V3.3.4 release corrects intent priority when a new catalog search arrives during an active recommendation flow.

## [3.3.4] - 2026-11-04

### Fixed
- Explicit catalog searches now take precedence over pending recommendation-refinement states.
- A new catalog search resets only the active search and recommendation context: previous catalog rows, category, budget, preference filters, recommended product, recommendation IDs, and pending recommendation action.
- Customer identity and conversation history remain intact when a new search starts.
- A fresh product query is executed for the new category and budget instead of reusing results from an earlier search.

### Preserved
- Short replies such as "Nylon" and "Yamaha até R$ 1.500" continue to refine an active recommendation flow when they are not phrased as a new catalog search.
- Sequential recommendations continue to exclude products already recommended in the current search context.

### Validation
- Preserved all 68 V3.3.3 regression tests.
- Added 5 tests for new-search priority, context reset, subsequent recommendation, brand/budget refinement, and customer identity preservation.
- 73 automated tests passing in the V3.3.4 validation run.
- Manual end-to-end smoke test passed in the validation environment; Windows/Python 3.12 validation remains pending with the project maintainer.

## [3.3.3] - 2026-11-03

### Added
- Session-scoped recommendation preferences for string type, supported brand, and maximum price.
- Contextual interpretation of short preference replies while recommendation refinement is pending.
- Sequential alternative recommendations that exclude previously recommended product IDs.
- Catalog refresh by the retained category and current budget before selecting another recommendation.
- Transparent no-match handling when no available product satisfies all active filters.

### Improved
- Session state now retains the full catalog result set, category, budget, explicit preferences, and recommendation history.
- Recommendation filtering uses catalog descriptions and structured product specifications.
- Follow-up routing prioritizes explicit cheaper-alternative requests over generic requests for another option.

### Validation
- Preserved all 54 V3.3.2 regression tests.
- Added 14 contextual recommendation tests.
- 68 automated tests passing in the V3.3.3 validation run.

## [3.3.2] - 2026-11-03

### Added
- Contextual explanation of product recommendations.
- Cheaper alternative identification based on the recommended product.
- Session-level tracking of the recommended product.

### Improved
- Product recommendation follow-up handling.
- Price-based alternative filtering.

### Tests
- Expanded automated test coverage.
- 54 automated tests passing.

## [3.3.1] - 2026-11-03

### Added
- Context-aware product recommendations based on the previously retrieved catalog results.
- Product descriptions and specifications included in product search results.

### Improved
- Intent routing for recommendation requests.
- Session context handling for product recommendations.
- Deterministic recommendation responses based on available catalog data.

### Tests
- Added automated tests for recommendation intent detection and contextual behavior.
- Preserved existing regression tests.
- All 47 automated tests passing.

## [3.3.0] - 2026-11-03

### Added
- Dynamic product category listing from the database.
- Improved generic catalog, price and availability interactions.
- Expanded automated tests for customer service scenarios.

### Improved
- Text normalization for accent-insensitive intent recognition.
- Policy retrieval with Unicode normalization.
- Customer message routing and intent handling.

### Tests
- 41 automated tests passing.

## [3.2.1] - 2026-11-03

### Changed
- Reworked the README into an industry-oriented project overview with quick start, architecture summary, examples, evaluation, engineering decisions, security notes, and limitations.
- Added `ARCHITECTURE.md` to describe the request lifecycle, module responsibilities, data boundaries, and design trade-offs.
- Added this changelog to preserve the observed development history and the corrections made across V3.0–V3.2.
- Updated the package version in `pyproject.toml` from `3.2.0` to `3.2.1`.

### Validation
- Re-ran the existing automated test suite against the consolidated release archive: **41 passed**.
- No application source code, test logic, data schema, or conversational behavior was intentionally changed in this release.

## [3.2.0] - 2026-11-03

### Fixed
- Prevented recognized policy topics and common commands from being treated as customer names.
- Added follow-up handling for policy topics such as promotions, customer service, and store information.
- Preserved a pending policy request while the customer selects a topic.
- Preserved pending comparison intent when the customer first selects a product category.
- Improved session-level continuity for catalog lookup, comparison, and sorting.

### Validation
- 41 automated tests passed in the V3.2 validation run.
- Manual conversation checks were performed in Windows PowerShell.

## [3.1.0] - 2026-11-03

### Fixed
- Improved handling of policy questions and short commands.
- Added contextual sorting by lowest price, highest price, and highest recorded stock.
- Improved brand-specific product search to avoid mixing unrelated brands in the observed Tagima test.
- Added and expanded conversation regression tests.

### Validation
- 32 automated tests passed in the V3.1 validation run.
- Manual checks identified remaining policy-topic and pending-intent issues, which were addressed in V3.2.

## [3.0.0] - 2026-11-03

### Added
- Session-aware customer-name handling and conversational context foundations.
- Product lookup, catalog routing, policy routing, promotion lookup, and protected demonstration order lookup.
- Deterministic response path that can run without an LLM.

### Fixed
- Improved routing for generic price and availability questions.
- Improved handling of accessory requests and orchestral string instrument categories.
- Added regression tests for routing and common customer-service flows.

### Validation
- The V3.0 development line retained the original automated tests and was subsequently expanded in V3.1 and V3.2.

---

Dates identify the release-consolidation work in the project history; they are not a claim that every earlier implementation change occurred on that exact date.
