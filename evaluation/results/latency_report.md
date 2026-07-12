# PHI policy latency benchmark

Iterations per configuration: 3000 (after 200 warmup calls, discarded)

## Per-configuration summary (microseconds)

- baseline: median=5.95us, IQR=[5.72, 6.71], mean=8.14us, stdev=8.50us
- phi_allow: median=6.00us, IQR=[5.91, 6.30], mean=8.11us, stdev=9.92us
- phi_deny: median=4.99us, IQR=[4.80, 7.73], mean=7.54us, stdev=8.87us

## Kruskal-Wallis across all three configurations

H = 1247.7110, p = 1.15611e-271

## Pairwise Mann-Whitney U (Bonferroni-adjusted alpha = 0.05 / 3 = 0.0167)

- baseline vs phi_allow: U = 3776837.5, p = 4.30832e-27 (significant), median delta = +0.05us
- baseline vs phi_deny: U = 6554043.0, p = 7.20109e-206 (significant), median delta = -0.96us
- phi_allow vs phi_deny: U = 6473843.0, p = 2.88489e-190 (significant), median delta = -1.00us

Caveat: single-process microbenchmark, no concurrent load, run on a dev laptop rather than the deployed gateway. Absolute microsecond figures will not transfer to production hardware; the comparison between configurations on the same run is the useful signal.
