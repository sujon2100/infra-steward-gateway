# DSI transparency policy accuracy evaluation

Generated: 2026-07-12T20:48:20.802237+00:00
Cases: 22

## Confusion matrix

Positive class: output should be blocked (a required HTI-1 category 1-3 attribute missing, or the dsi_id isn't registered at all).

- TP (violation, correctly blocked): 17
- TN (complete registration, correctly allowed): 5
- FP (complete registration, wrongly blocked): 0
- FN (violation, wrongly allowed): 0

Precision: 1.0000
Recall: 1.0000
Accuracy: 1.0000
F1: 1.0000

## By case group

- TN: 4 cases, 0 mismatched
- TP: 12 cases, 0 mismatched
- edge: 3 cases, 0 mismatched
- adversarial: 3 cases, 0 mismatched

Caveat: expected labels were hand-derived from the same specification the implementation follows, by the same person who wrote the implementation. This checks implementation-against-spec conformance across a deliberately constructed case set, not independent third-party validation. It also only checks whether the required transparency attributes are present and recorded - it says nothing about whether the underlying model for a given dsi_id is actually accurate, fair, or clinically safe.
