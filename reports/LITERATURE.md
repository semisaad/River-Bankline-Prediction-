# RiverGuard — literature and evidence base

What this file is for: every claim the project makes, and the published work
that supports it. Written so it can be lifted into a thesis, and so that the
contradictions are on the record instead of being discovered at the viva.

**How to read the confidence marks:**

- `[verified]` — the DOI was resolved and the title/authors confirmed live.
- `[checked]` — verified by me directly during this session, not just reported.
- `[gray]` — real and citable, but not journal peer review (agency report).

The project's own numbers are reproduced in section 0 so they can be checked
against `reports/VALIDATION.md`, which is generated from the data.

---

## 0. What the project claims, and what it does not

This section exists because the honest version of the claim is narrower than
expected, and the literature is used to justify the *narrow* claim, not to
inflate it.

**Claimed (supported by measurement in this repository):**

1. Bank movement on this reach can be measured from Landsat at 30 m over 5-year
   pairs, and from Sentinel-2 at 10 m over 1-year pairs.
2. The two sensors agree on the *water mask*: mean IoU 0.79, mean area
   difference −5.9% over 8 overlapping years.
3. A gradient-boosted tree model predicts the next rate better than every
   trivial predictor pooled: MAE **15.675** vs **20.413** m/yr for the strongest
   baseline, across 2414 held-out records and 29 expanding-window folds.
4. More and more recent training data measurably improves the model on a fixed
   target: MAE falls from 29.75 (trained through 1999) to 11.02 m/yr (through
   2023), and a count-matched test shows the gain is **recency, not quantity**.
5. The model's advantage is concentrated in 1996–2015 (18/18 folds) and
   disappears in 2016–2026 (2/11 folds) — D92.

**Not claimed:**

- That the system produces a validated forecast. It does not, and section 4
  explains why that is an expected result rather than a failure of effort.
- That it beats simply assuming the bank did not move. **It does not.** For
  absolute bank position the do-nothing baseline wins: 2021→2026 median error
  37.2 m against 0.0 m; 2023→2026 mean error 30.8 m against 13.8 m.

That last point is the single most important honest statement in the project,
and section 4 is the literature that makes it a *result* rather than a
disappointment.

---

## 1. The direct study for this river

**Hasan, I., Dey, J., Munna, M. M. R., Preya, A., Nisanur, T. B., Memy, M. J., &
Zeba, M. Z. S. (2024).** *Morphological changes of river Bank Erosion and
channel shifting assessment on Arial Khan River of Bangladesh using Landsat
satellite time series images.* Progress in Disaster Science, 24, 100381.
https://doi.org/10.1016/j.pdisas.2024.100381 `[checked]`

This is the closest published work to this project and is the source of the
**21 m/yr** comparison figure used throughout.

What it reports, quoted from the paper's own highlights:

- Erosion of **5142.60 ha** and deposition of **4756.52 ha**, 1993–2024 — so net
  loss, which agrees in sign with this project's finding.
- *"The river shifted an average of **0.66 km**"* over the same period.
- Analysed within a **2 km buffer** of the floodplain; channel-centreline
  migration measured in ArcGIS 10.8; supervised LULC classification.
- Higher migration in Muladi Upazila than Babuganj Upazila.

**Where 21 m/yr comes from:** 0.66 km ÷ 31 years = 21.3 m/yr. It is derived
arithmetic, not a figure the paper states.

**Why that matters, and why this project was previously comparing two different
things.** Hasan et al. report a **reach-scale channel-centreline average**.
RiverGuard reports the **median of individual bank-side displacements at fixed
transects**. A centreline average includes the meander bends where migration is
fastest and is pulled up by the tail; a median of a heavy-tailed distribution
sits below its own mean by construction. The two numbers can both be correct.

This is now stated in `reports/VALIDATION.md` section 5 rather than being
presented as an unexplained discrepancy. Being able to explain a gap is not the
same as closing it — the 250 m measurement strip and the single-reach scope are
still real limitations and are listed as such.

---

## 2. Rates elsewhere on the Ganges–Padma system

These bracket RiverGuard's 11.2 m/yr median and show the spread of legitimate
definitions. They are useful precisely because they disagree with each other.

**Miah, M. D., Chowdhury, N. A., & Ali, Y. (2025).** *Monitoring multi-decadal
riverbank dynamics of the Padma river in Bangladesh using geospatial analysis
and DSAS model.* Discover Geoscience, 3(1).
https://doi.org/10.1007/s44288-025-00353-w `[checked]`

Reports a mean of **−21.85 m/yr** on the eroding south bank (max −178 m/yr) using
DSAS. Note the shape of that sentence: *a mean, on eroding transects only*. That
is exactly the population that a whole-transect median excludes, which is why
this number sits near the published 21 and far above our 11.2.

**Ferdoush, J., et al. (2022).** *Assessment of meander-bend migration of a
major distributary of the Ganges River within Bangladesh.* River, 1(2), 240–255.
https://doi.org/10.1002/rvr2.21 `[verified]`

Bend-scale migration of **45–108 m/yr**, with 70–80 m/yr at critical bends in
1981–1999. Far above every other figure here — because it measures **bend-apex
migration**, which is the fastest-moving component of a meandering river and not
the same quantity as bank displacement at a fixed transect. Cite this as the
high end, and say what it measures.

**Dewan, A., et al. (2017).** *Assessing channel changes of the Ganges-Padma
River system in Bangladesh using Landsat and hydrological data.* Geomorphology,
276, 257–279. https://doi.org/10.1016/j.geomorph.2016.10.017 `[verified]`

The standard Landsat-based channel-change reference for the Padma system that
feeds the Arial Khan. Useful for the methods chapter.

**Sarker, M. H., Thorne, C. R., Aktar, M. N., & Ferdous, M. R. (2013).**
*Morpho-dynamics of the Brahmaputra–Jamuna River, Bangladesh.* Geomorphology,
215, 45–59. https://doi.org/10.1016/j.geomorph.2013.07.025 `[verified]`

Context for the archived Jamuna work, and for why reach-averaged rates of a
braided river are an unstable definition.

**Reading these together:** published rates for this river system span roughly
**11 to 108 m/yr** and the spread is driven mainly by *what is being measured*
(centreline vs bank; all transects vs eroding only; bend apex vs fixed cast),
not by disagreement about the river. A thesis that says this explicitly is
stronger than one that quotes a single number.

---

## 3. Method lineage — the measurements are standard practice

RiverGuard's transect approach is a riverine adaptation of established coastal
and riverbank methods. This matters for the methodology chapter: the technique
is not invented here.

**Himmelstoss, E. A., et al. (2021).** *Digital Shoreline Analysis System (DSAS)
version 5.1 user guide.* USGS Open-File Report 2021–1091.
https://doi.org/10.3133/ofr20211091 `[gray]`

Defines the transect metrics (NSM, EPR, LRR) that RiverGuard's EPR matches. Also
the source of a caveat worth quoting: DSAS assumes a single reference baseline
and primarily one-sided change — a limitation RiverGuard shares.

**McFeeters, S. K. (1996).** NDWI. International Journal of Remote Sensing,
17(7), 1425–1432. https://doi.org/10.1080/01431169608948714 `[verified]`
**Xu, H. (2006).** MNDWI. International Journal of Remote Sensing, 27(14),
3025–3033. https://doi.org/10.1080/01431160600589179 `[verified]`
**Feyisa, G. L., et al. (2014).** AWEI. Remote Sensing of Environment, 140,
23–35. https://doi.org/10.1016/j.rse.2013.08.029 `[verified]`

The three water indices RiverGuard thresholds. MNDWI is generally the better
choice for turbid, sediment-laden rivers, which is what the Arial Khan is.

**Fisher, A., Flood, N., & Danaher, T. (2016).** *Comparing Landsat water index
methods for automated water classification in eastern Australia.* Remote Sensing
of Environment, 175, 167–182. https://doi.org/10.1016/j.rse.2015.12.055 `[verified]`

Head-to-head comparison showing **index choice moves the water edge by about a
pixel**. This is direct support for RiverGuard's decision to hold the detection
constants identical across sensors (guarded by `09_checks.py` section 8): if the
thresholds differed, the cross-sensor comparison would measure the scripts
rather than the sensors.

**Vos, K., et al. (2019).** *CoastSat.* Environmental Modelling & Software,
122, 104528. https://doi.org/10.1016/j.envsoft.2019.104528 `[verified]`
**Vos, K., et al. (2019).** *Sub-annual to multi-decadal shoreline variability
from publicly available satellite imagery.* Coastal Engineering, 150, 160–174.
https://doi.org/10.1016/j.coastaleng.2019.04.004 `[verified]`

The standard open toolkit for satellite shoreline extraction and a quantified
account of the noise floor. Methodological precedent for the whole approach.

---

## 4. The resolution floor — why the negative result is a *result*

This is the section that makes the do-nothing finding defensible rather than
embarrassing. It should be in the discussion chapter.

**Langhorst, T., & Pavelsky, T. (2023).** *Global Observations of Riverbank
Erosion and Accretion From Landsat Imagery.* JGR: Earth Surface, 128(2),
e2022JF006774. https://doi.org/10.1029/2022JF006774 `[verified]`

The key number: minimum detectable change of about **0.35 of a pixel** — roughly
**10 m at 30 m resolution**. RiverGuard's own findings land squarely on this:

- A 30 m Landsat pixel over a 5-year pair is worth **6.0 m/yr** of apparent
  movement. Many bank sides read exactly zero because they did not move a whole
  pixel in five years.
- This is why *"assume the bank never moved"* is such a strong baseline: for
  more than half the bank sides it is not an assumption, it is the measurement.
  The 2021→2026 do-nothing baseline has a **median error of 0.0 m**.
- It is also why Sentinel-2's annual median of 1.2 m/yr is described as mostly
  quantisation: an eighth of one 10 m pixel.

**Luijendijk, A., et al. (2018).** *The State of the World's Beaches.*
Scientific Reports, 8, 6641. https://doi.org/10.1038/s41598-018-24630-6 `[verified]`

Establishes **half-pixel** shoreline precision as the working benchmark in the
field. RiverGuard's numbers sit inside that.

**Mount, N. J., & Louis, J. (2005).** *Estimation and propagation of error in
measurements of river channel movement from aerial imagery.* Earth Surface
Processes and Landforms, 30(5), 635–643. https://doi.org/10.1002/esp.1172 `[verified]`

How measurement error propagates into migration *rates* — the rate is a
difference of two noisy positions, so its error is larger than either.

**Rowland, J. C., et al. (2016).** *A morphology independent methodology for
quantifying planview river change.* Remote Sensing of Environment, 184, 212–228.
https://doi.org/10.1016/j.rse.2016.07.005 `[verified]`

Provides the half-pixel uncertainty framework specifically for river change,
which is a better citation here than the coastal ones.

**Hughes, M. L., McDowell, P. F., & Marcus, W. A. (2006).** *Accuracy assessment
of georectified aerial photographs.* Geomorphology, 74(1–4), 1–16.
https://doi.org/10.1016/j.geomorph.2005.07.001 `[verified]`

Georectification error alone can rival small annual movements — relevant to the
"no independent ground truth" limitation.

**The argument, stated in one paragraph for the thesis:** the model's rate MAE
(15.675 m/yr) and the resolution floor (~10 m at 30 m pixels) are the same order
of magnitude. A model cannot reliably predict detail finer than the measurement
noise of its own target. Therefore the correct conclusion is not "the model
failed" but **"at 30 m resolution and a 5-year step, bank position on this reach
is not predictable beyond persistence"** — and that is a publishable-shaped
finding rather than a null result.

---

## 5. Baseline discipline — why this is a respectable negative

**Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2018).** *The M4
Competition: Results, findings, conclusion and way forward.* International
Journal of Forecasting, 34(4), 802–808.
https://doi.org/10.1016/j.ijforecast.2018.06.001 `[verified]`

**Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2018).** *Statistical and
Machine Learning forecasting methods: Concerns and ways forward.* PLOS ONE,
13(3), e0194889. https://doi.org/10.1371/journal.pone.0194889 `[verified]`

**Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2022).** *M5 accuracy
competition.* International Journal of Forecasting, 38(4), 1346–1364.
https://doi.org/10.1016/j.ijforecast.2021.11.013 `[verified]`

Across the largest forecasting competitions, **simple methods beat most complex
ones**, and machine-learning entries routinely fail to beat naive benchmarks.
RiverGuard's design — score against *three* trivial predictors, take the
strongest, and refuse the claim if it loses — is the discipline this literature
recommends. Finding that the model beats trivial baselines in the past but not
recently (D92) is the kind of finding these competitions are built to surface.

**Bergmeir, C., & Benítez, J. M. (2012).** *On the use of cross-validation for
time series predictor evaluation.* Information Sciences, 191, 192–213.
https://doi.org/10.1016/j.ins.2011.12.028 `[verified]`

Justifies the expanding-window backtest used here, and why a random split would
have been invalid. Cite this for the D63 leakage correction.

**Hyndman, R. J., & Athanasopoulos, G. (2021).** *Forecasting: principles and
practice* (3rd ed.). OTexts. https://otexts.com/fpp3/ `[gray]`

The standard reference on naive/persistence benchmarks and backtesting.

**Vitousek, S., et al. (2023).** *A Model Integrating Satellite-Derived Shoreline
Observations for Predicting Fine-Scale Shoreline Response.* JGR: Earth Surface,
128(7), e2022JF006936. https://doi.org/10.1029/2022JF006936 `[verified]`

The closest analogue to what RiverGuard is attempting: satellite-derived
shoreline observations driving a *predictive* geomorphic model with explicit
skill checks. Cite as the methodological target.

---

## 6. Bankline prediction — a genuinely thin literature

Be honest about this in the thesis. Only four directly on-point papers were
found, and **none of them reports a persistence baseline**.

**Ritu et al. (2023).** *Prediction of Padma river bank shifting and its
consequences on LULC changes.* Ecological Indicators, 156, 111104.
https://doi.org/10.1016/j.ecolind.2023.111104 `[verified]`

Predicts Padma banklines, but reports change rates of **−79.83 and +98.13 m/yr**,
far above every other study here. Treat as a high-end outlier with a different
metric definition; cite with caution.

**Islam & Matin (2023).** *Prediction of fluvial erosion rate in Jamuna River,
Bangladesh.* International Journal of River Basin Management, 21(4), 625–637.
https://doi.org/10.1080/15715124.2022.2068561 `[verified]`

Regression-based erosion-rate prediction for a Bangladeshi river.

**Amini, A., et al. (2024).** *Meanders on the Move: Can AI-Based Solutions
Predict Where They Will Be Located?* Water, 16(17), 2460.
https://doi.org/10.3390/w16172460 `[verified]`

ML on meander migration, largely synthetic framing.

**Wu et al. (2026).** *Prediction of basin-scale river channel migration based on
landscape evolution numerical simulation.* Hydrology and Earth System Sciences,
30(6), 1563–1583. https://doi.org/10.5194/hess-30-1563-2026 `[verified]`

Process-model-based migration prediction — a different approach to the same goal.

**Why this gap is an opportunity, not a weakness.** The measurement literature
(sections 1–4) is mature. The *prediction* literature is young, and the papers in
it generally report skill without testing against "the bank stayed put". This
project's contribution is therefore not a better model — it is **running the
comparison that the existing prediction papers omit**, and reporting that the
baseline wins. That is a contribution.

---

## 7. Motivation — why it matters (Bangladesh impact)

For the introduction. Also the reason a negative result is still worth
reporting: the problem is real and large.

**Haque, C. E., & Zaman, M. Q. (1989).** *Coping with Riverbank Erosion Hazard
and Displacement in Bangladesh.* Disasters, 13(4), 300–314.
https://doi.org/10.1111/j.1467-7717.1989.tb00724.x `[verified]`

The founding study of erosion displacement and coping strategies.

**Hossain, M. (1993).** *Economic effects of riverbank erosion: some evidence
from Bangladesh.* Disasters, 17(1), 25–32.
https://doi.org/10.1111/j.1467-7717.1993.tb00485.x `[verified]`

Village-level measurement of farmland and crop-income loss.

**Hutton, C. E., & Haque, C. E. (2004).** *Human Vulnerability, Dislocation and
Resettlement.* Disasters, 28(1), 41–62.
https://doi.org/10.1111/j.0361-3666.2004.00242.x `[verified]`

The widely cited vulnerability/resettlement framework.

**Penning-Rowsell, E., Sultana, P., & Thompson, P. (2013).** *The 'last resort'?
Population movement in response to climate-related hazards in Bangladesh.*
Environmental Science & Policy, 27, S44–S59.
https://doi.org/10.1016/j.envsci.2012.03.009 `[verified]`

Migration as adaptation of last resort.

**Bhuiyan, M. A. H., et al. (2017).** *Exploring impacts and livelihood
vulnerability of riverbank erosion hazard among rural household along the river
Padma.* Environmental Systems Research, 6(1), 25.
https://doi.org/10.1186/s40068-017-0102-9 `[verified]`

Household-level vulnerability on the Padma — the river system that feeds the
Arial Khan.

**Alam, G. M. M., et al. (2020).** *Hazards, food insecurity and human
displacement in rural riverine Bangladesh.* International Journal of Disaster
Risk Reduction, 43, 101364. https://doi.org/10.1016/j.ijdrr.2019.101364 `[verified]`

**Billah, M. M., et al. (2023).** *Riverbank Erosion and Rural Food Security in
Bangladesh.* World, 4(3), 528–544. https://doi.org/10.3390/world4030033 `[verified]`

**Asian Development Bank (2014).** *Flood and Riverbank Erosion Risk Management
Investment Program: Sector Assessment.* RRP BAN 44167.
https://www.adb.org/sites/default/files/linked-documents/44167-013-ssa.pdf `[gray]`

Source of the commonly quoted **5,000–6,000 ha/yr lost** and ~**100,000 people
affected per year**. Widely repeated, but this is a project document, not peer
review — cite it as such or find the primary source.

---

## 8. Datasets — what is available and what was used

**Used in this project:**

| dataset | reference | use here |
|---|---|---|
| Landsat 4/5 TM, 7 ETM+, 8/9 OLI L2 | USGS (2021) FS 2021-3055; https://doi.org/10.5066/P9OGBGM6, P9C7I13B, P9IAXOVV `[gray]` | the 1989–2026 long record |
| Sentinel-2 L2A | Drusch et al. (2012), RSE 120, 25–36, https://doi.org/10.1016/j.rse.2011.11.026 `[verified]` | 2019–2026 cross-sensor check |
| Google Earth Engine | Gorelick et al. (2017), RSE 202, 18–27, https://doi.org/10.1016/j.rse.2017.06.031 `[verified]` | all compositing and export |
| ERA5-Land | Muñoz-Sabater et al. (2021), ESSD 13, 4349–4383, https://doi.org/10.5194/essd-13-4349-2021 `[verified]` | climate columns (no gain, D90) |

**Available but not used, and worth naming in a limitations/future-work
section:**

| dataset | reference | why it could matter |
|---|---|---|
| JRC Global Surface Water | Pekel et al. (2016), Nature 540, 418–422, https://doi.org/10.1038/nature20584 `[verified]` | independent water-occurrence product to cross-check masks |
| GloFAS discharge | Harrigan et al. (2020), ESSD 12, 2043–2060, https://doi.org/10.5194/essd-12-2043-2020; data https://doi.org/10.24381/cds.a4fdd6b9 `[verified]` | tried, rejected — the reach is small and local (D90) |
| HydroSHEDS / HydroATLAS | Lehner et al. (2008), Eos 89(10), 93–94, https://doi.org/10.1029/2008EO100001; Linke et al. (2019), Sci Data 6, 283, https://doi.org/10.1038/s41597-019-0300-6 `[verified]` | basin attributes, drainage area |
| BWDB water level / discharge | http://www.hydrology.bwdb.gov.bd `[gray]` | **the highest-value missing input** — observed stage would let the model separate water-level change from bank change |
| FFWC | https://www.ffwc.gov.bd `[gray]` | flood/water-level forecasts |
| GRDC | https://grdc.bafg.de `[gray]` | WMO discharge archive |

**The BWDB row is the single most valuable outstanding action.** The project
already knows that water level confounds the measurement (Landsat +0.16, S2
+0.42 between stage and measured rate). Observed stage would convert that from a
stated caveat into a control variable.

---

## 9. Contradictions and caveats — read this before writing the discussion

Deliberately not buried. Each of these can be used against the project at a
viva, so each is answered here.

1. **The 21 m/yr figure is derived, not quoted.** No source was found stating
   "21 m/yr bank erosion on the Arial Khan". It is 0.66 km ÷ 31 yr from Hasan et
   al. (2024), and it is a *channel-centreline average*. Any thesis sentence must
   say "derived from", not "reported by". This is now handled in
   `VALIDATION.md` section 5.

2. **The 11.2 vs 21 gap is mostly definitional.** Median of all transects vs
   mean centreline shift; Miah et al. (2025) report a mean of 21.9 m/yr on
   eroding transects only. The numbers coexist. What is *not* explained away is
   the 250 m strip and the single-reach scope — those remain limitations.

3. **Ferdoush et al. (2022) report 45–108 m/yr.** Much faster than anything
   else. It measures bend-apex migration, a different quantity. Do not present
   this as a refutation, and do not hide it either.

4. **Ritu et al. (2023) report −79.83 / +98.13 m/yr on the Padma.** A high-end
   outlier with a likely different metric definition. Cite cautiously.

5. **The resolution floor plausibly explains much of the negative result.**
   Langhorst & Pavelsky (2023): ~0.35 px minimum detectable change ≈ 10 m at
   30 m. The model's MAE is the same order. Frame this as the expected behaviour
   of a noisy geomorphic series — which the forecasting-competition literature
   (Makridakis et al.) predicts — and then *test* it, rather than treating it as
   an excuse.

6. **No published bankline-prediction paper found runs a persistence baseline.**
   So this project's negative result cannot be cited as disagreeing with prior
   work. It fills a gap. Say that explicitly; it is the contribution.

7. **The do-nothing baseline wins on position, but the model wins on rate MAE.**
   These are different questions and both results are true. The rate backtest
   compares against the *training median rate*; the position figure compares
   against *zero movement*. A viva examiner will ask which baseline is "the"
   baseline. Have the answer ready: both, for different questions, and the
   project reports both.

8. **Gray literature in this file is marked `[gray]`.** The ADB land-loss
   figures and the USGS/DSAS technical documents are real and citable, but they
   are not journal peer review. Do not describe them as peer-reviewed.

9. **Reference years follow print issues** (Dewan 2017, Feyisa 2014,
   Penning-Rowsell 2013, Alam 2020). Online-first years are 1–2 years earlier.
   Match the style used in the thesis reference list.

---

## 10. One-paragraph summary for the thesis abstract

Satellite time series were used to measure and then attempt to predict bankline
movement on the Arial Khan River, Bangladesh. Bank movement was measured at
fixed transects from Landsat (30 m, 5-year pairs, 1989–2026) and Sentinel-2
(10 m, 1-year pairs, 2019–2026) dry-season water masks, with the two sensors
agreeing on water extent to a mean IoU of 0.79. A gradient-boosted tree model
reduced prediction error against the strongest trivial baseline (MAE 15.675
against 20.413 m/yr across 2414 held-out records), and a learning-curve
experiment showed that the gain comes from the *recency* of training data rather
than its quantity. However, the model did not beat a persistence baseline for
absolute bank position, and its advantage over trivial predictors was confined
to pre-2016 folds. This outcome is consistent with published estimates of the
minimum detectable change achievable from 30 m imagery (≈0.35 pixel), which
places the model's error in the same range as the measurement noise of its own
target. The study's contribution is therefore not a superior forecast but the
demonstration — absent from the existing bankline-prediction literature — that
on this reach, at this resolution, persistence is a stronger predictor of bank
position than machine learning, and that this can be established rigorously
rather than assumed.
