# Test Evidence

This directory records the automated validation for release 3.3.4.

## Automated tests

- Baseline regression tests retained from V3.3.3: 68
- New V3.3.4 regression tests: 5
- Total passing tests: 73
- Failed tests: 0

The exact pytest summary and validation environment are recorded in `test_results.txt`.

## Coverage added in V3.3.4

- Explicit catalog searches take precedence over pending recommendation states.
- New searches reset the active catalog and recommendation context without deleting customer identity.
- Recommendations after a new search use the new catalog result set and budget.
- Brand and budget refinements remain contextual after a fresh search.
- Short preference replies are not misclassified as new catalog searches.

## Validation boundary

The recorded run is a development validation result. Windows/Python 3.12
validation by the project maintainer remains pending before publishing the
release tag. No production-readiness, performance, or live-inventory claim
is made.
