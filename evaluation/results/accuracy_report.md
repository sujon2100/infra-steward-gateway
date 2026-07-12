# PHI policy accuracy evaluation

Generated: 2026-07-12T19:49:29.512683+00:00
Cases: 48

## Confusion matrix

Positive class: request should be denied (a policy violation).

- TP (violation, correctly denied): 32
- TN (compliant, correctly allowed): 16
- FP (compliant, wrongly denied): 0
- FN (violation, wrongly allowed): 0

Precision: 1.0000
Recall: 1.0000
Accuracy: 1.0000
F1: 1.0000

## By case group

- TN: 8 cases, 0 mismatched
- TP: 26 cases, 0 mismatched
- edge: 7 cases, 0 mismatched
- adversarial: 7 cases, 0 mismatched

Caveat: expected labels were hand-derived from the same specification the implementation follows, by the same person who wrote the implementation. This checks implementation-against-spec conformance across a deliberately constructed case set; it is not independent third-party validation, and a deterministic rule engine scoring 100% here says nothing about how it would generalize to inputs outside this case set.
