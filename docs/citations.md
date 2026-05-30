# References & Citations

This document lists the peer-reviewed sources behind every ecological index, statistical test,
and ordination method implemented in coralX.

---

## Coverage & Confidence Intervals

**Wilson Score Interval** — used for per-code 95% confidence intervals on proportions

> Wilson, E. B. (1927). Probable inference, the law of succession, and statistical inference.
> *Journal of the American Statistical Association*, 22(158), 209–212.
> https://doi.org/10.1080/01621459.1927.10502953

---

## Reef Health Classification

**Gomez & Yap (1988)** — live coral cover thresholds (Poor / Fair / Good / Excellent)
also codified in Indonesia as *KepMen LH No. 4 Tahun 2001*

> Gomez, E. D., & Yap, H. T. (1988). Monitoring reef condition.
> In R. A. Kenchington & B. E. T. Hudson (Eds.),
> *Coral Reef Management Handbook* (pp. 187–195). UNESCO Regional Office, Jakarta.

---

## Diversity Indices

**Shannon–Weaver Diversity Index (H′)** — H′ = −Σ pᵢ ln pᵢ

> Shannon, C. E., & Weaver, W. (1949).
> *The Mathematical Theory of Communication*.
> University of Illinois Press, Urbana.

**Simpson's Diversity Index (1 − D)** — D = Σ pᵢ²

> Simpson, E. H. (1949). Measurement of diversity.
> *Nature*, 163, 688.
> https://doi.org/10.1038/163688a0

**Pielou's Evenness (J′)** — J′ = H′ / ln(S)

> Pielou, E. C. (1966). The measurement of diversity in different types of biological collections.
> *Journal of Theoretical Biology*, 13, 131–144.
> https://doi.org/10.1016/0022-5193(66)90013-0

**Margalef's Species Richness (d)** — d = (S − 1) / ln(N)

> Margalef, R. (1958). Information theory in ecology.
> *General Systems*, 3, 36–71.

**Fisher's Alpha (α)** — solved iteratively from S = α ln(1 + N/α)

> Fisher, R. A., Corbet, A. S., & Williams, C. B. (1943).
> The relation between the number of species and the number of individuals in a random
> sample of an animal population.
> *Journal of Animal Ecology*, 12, 42–58.
> https://doi.org/10.2307/1411

**Berger–Parker Dominance (d)** — d = n\_max / N

> Berger, W. H., & Parker, F. L. (1970).
> Diversity of planktonic foraminifera in deep-sea sediments.
> *Science*, 168(3937), 1345–1347.
> https://doi.org/10.1126/science.168.3937.1345

**Hill Numbers (q0, q1, q2)** — effective number of species at diversity orders 0, 1, 2

> Hill, M. O. (1973). Diversity and evenness: a unifying notation and its consequences.
> *Ecology*, 54(2), 427–432.
> https://doi.org/10.2307/1934352

> Jost, L. (2006). Entropy and diversity.
> *Oikos*, 113(2), 363–375.
> https://doi.org/10.1111/j.2006.0030-1299.14714.x

---

## Reef Health & Phase Shift Indicators

**Mortality Index (MI)** — MI = dead / (live hard coral + dead)

Widely used in Indo-Pacific reef monitoring programmes including COREMAP-CTI
(Coral Reef Rehabilitation and Management Programme – Coral Triangle Initiative).
See also:

> English, S., Wilkinson, C., & Baker, V. (Eds.). (1997).
> *Survey Manual for Tropical Marine Resources* (2nd ed.).
> Australian Institute of Marine Science, Townsville.

**Coral : Algae Ratio** — ratio > 1 indicates coral dominance; < 1 signals phase-shift risk

> Hughes, T. P. (1994). Catastrophes, phase shifts, and large-scale degradation of a
> Caribbean coral reef.
> *Science*, 265(5178), 1547–1551.
> https://doi.org/10.1126/science.265.5178.1547

> Bellwood, D. R., Hughes, T. P., Folke, C., & Nyström, M. (2004).
> Confronting the coral reef crisis.
> *Nature*, 429, 827–833.
> https://doi.org/10.1038/nature02691

---

## Bootstrap Confidence Intervals

> Efron, B. (1979). Bootstrap methods: Another look at the jackknife.
> *Annals of Statistics*, 7(1), 1–26.
> https://doi.org/10.1214/aos/1176344552

> Efron, B., & Tibshirani, R. J. (1993).
> *An Introduction to the Bootstrap*.
> Chapman & Hall/CRC, New York.

---

## Group Comparison Tests

**One-way ANOVA** (used when n ≥ 10 per group)

> Zar, J. H. (2010).
> *Biostatistical Analysis* (5th ed.).
> Prentice Hall, Upper Saddle River, NJ.

**Kruskal–Wallis Test** (non-parametric; used when n < 10 per group)

> Kruskal, W. H., & Wallis, W. A. (1952).
> Use of ranks in one-criterion variance analysis.
> *Journal of the American Statistical Association*, 47(260), 583–621.
> https://doi.org/10.1080/01621459.1952.10483441

---

## Multivariate Community Analysis

**Bray–Curtis Dissimilarity**

> Bray, J. R., & Curtis, J. T. (1957).
> An ordination of the upland forest communities of southern Wisconsin.
> *Ecological Monographs*, 27(4), 325–349.
> https://doi.org/10.2307/1942268

**Principal Coordinates Analysis (PCoA / Classical MDS)**

> Gower, J. C. (1966).
> Some distance properties of latent root and vector methods used in multivariate analysis.
> *Biometrika*, 53(3–4), 325–338.
> https://doi.org/10.1093/biomet/53.3-4.325

**Hierarchical Clustering — UPGMA linkage**

> Sokal, R. R., & Michener, C. D. (1958).
> A statistical method for evaluating systematic relationships.
> *University of Kansas Science Bulletin*, 38, 1409–1438.

**PERMANOVA (Permutational Multivariate Analysis of Variance)**

> Anderson, M. J. (2001).
> A new method for non-parametric multivariate analysis of variance.
> *Austral Ecology*, 26(1), 32–46.
> https://doi.org/10.1111/j.1442-9993.2001.01070.pp.x

> McArdle, B. H., & Anderson, M. J. (2001).
> Fitting multivariate models to community data: a comment on distance-based
> redundancy analysis.
> *Ecology*, 82(1), 290–297.
> https://doi.org/10.1890/0012-9658(2001)082[0290:FMMTCD]2.0.CO;2

**SIMPER (Similarity Percentages)**

> Clarke, K. R. (1993).
> Non-parametric multivariate analyses of changes in community structure.
> *Australian Journal of Ecology*, 18(1), 117–143.
> https://doi.org/10.1111/j.1442-9993.1993.tb00438.x

---

## Software Dependencies

Core numerical routines are provided by:

> Harris, C. R., et al. (2020). Array programming with NumPy.
> *Nature*, 585, 357–362.
> https://doi.org/10.1038/s41586-020-2649-2

> Virtanen, P., et al. (2020). SciPy 1.0: Fundamental algorithms for scientific computing in Python.
> *Nature Methods*, 17, 261–272.
> https://doi.org/10.1038/s41592-019-0686-2

> McKinney, W. (2010). Data structures for statistical computing in Python.
> *Proceedings of the 9th Python in Science Conference*, 56–61.
> https://doi.org/10.25080/Majora-92bf1922-00a
