# Corrected-Model Discrete IP Superstructure Rankings (`PharmaPy 3194efd`)

> **Provenance Notice**: All files in this directory and in `../data/corrected_model_pharmapy_current/` were generated on the **corrected current `PharmaPy` model (`3194efd`)** without altering any legacy provenance files in `../data/ssopt_gen_1.csv` or `../result_gurobi/`.

## Mathematical Link Between `PharmaPy` Simulation and `ssopt_gen_1.csv`

Each nonzero arc weight (`Flow Cost`) in `ds-mfg/discrete_ip/data/ssopt_gen_1.csv` is the empirical mean of the unit equipment sizes (`flowsheet.GetCAPEX()`, i.e. vessel volumes $V_{\text{tot}}$ [$\text{m}^3$]) across the 36 two-reactor superstructure configurations (`#00`–`#35`), rounded to 4 decimal places:

| Edge | From $\to$ To | Unit Mode (`uo`) | Physical Meaning of Arc Cost | Legacy `ssopt_gen_1.csv` | Corrected Eval (`3194efd`) | Corrected `PyNomad` (`3194efd`) | Corrected Turton CAPEX [$10^6\text{ USD}$] |
|---|---|---|---|---:|---:|---:|---:|
| `f01` | `n01 -> n02` | `PFR` | Mean `R01` volume ($R_{01}=\text{PFR}$) | `0.0289` | `0.0300` | `0.0300` | `0.0073` |
| `f02` | `n01 -> n02` | `CSTR` | Mean `R01` volume ($R_{01}=\text{CSTR}$) | `0.0399` | `0.0400` | `0.0400` | `0.0087` |
| `f03` | `n01 -> n02` | `batch` | Mean `R01` volume ($R_{01}=\text{batch}$) | `0.1225` | `0.1333` | `0.1333` | `0.0175` |
| `f06` | `n03 -> n04` | `holdT` | Mean `HOLD01` volume ($R_{01}\ne\text{batch}, R_{02}=\text{batch}$) | `4.9590` | `5.0435` | `5.0436` | `0.0294` |
| `f08` | `n05 -> n06` | `PFR` | Mean `R02 + HOLD01` volume ($R_{02}=\text{PFR}$) | `6.1930` | `6.3813` | `6.3828` | `0.0522` |
| `f09` | `n05 -> n06` | `CSTR` | Mean `R02 + HOLD01` volume ($R_{02}=\text{CSTR}$) | `9.7170` | `6.5591` | `6.5652` | `0.0613` |
| `f10` | `n05 -> n06` | `batch` | Mean `R02` volume ($R_{02}=\text{batch}$) | `3.3520` | `3.4087` | `3.4087` | `0.0865` |
| `f11` | `n06 -> n07` | `batch` | Mean `VAP01` volume | `6.1630` | `5.7140` | `5.7116` | `0.0992` |
| `f13` | `n08 -> n09` | `cont1` | Mean `CR01` volume ($\text{CR}=\text{cont1}$) | `0.7390` | `0.7587` | `0.7262` | `0.0352` |
| `f14` | `n08 -> n09` | `cont2` | Mean `CR01 + CR02` volume ($\text{CR}=\text{cont2}$) | `0.8400` | `0.7785` | `0.7674` | `0.0483` |
| `f15` | `n08 -> n09` | `cont3` | Mean `CR01 + CR02 + CR03` volume ($\text{CR}=\text{cont3}$) | `1.2710` | `1.1508` | `1.1500` | `0.0722` |
| `f16` | `n07 -> n10` | `batchU` | Mean `CR01` volume ($\text{CR}=\text{batchU}$) | `6.9900` | `5.6289` | `5.6054` | `0.0790` |
| `f17` | `n09 -> n10` | `holdT` | Mean slurry `HOLD` tank volume after continuous `CR` | `1.3330` | `6.1733` | `6.1587` | `0.0329` |

## Key Impact on the 36-Solution Discrete IP Ranking

1. **Resolution of the `batchU` vs. `cont1` Rank Inversion**:
   - In 2022 `PharmaPy` (`04499cc`), `DynamicCollector` read the un-updated default `Slurry.vol_slurry = 1.0` $\text{m}^3$, so every holding tank after a continuous `MSMPR` crystallizer reported `f17 = 1.0 / 0.75 = 1.333` $\text{m}^3$ instead of the true accumulated slurry volume (`6.159` $\text{m}^3$). That caused the legacy discrete IP to rank `('batch', 'batch', 'batch', 'cont1')` (`#01`) at **Rank 1** (`ip_obj = 11.7095`) and `('batch', 'batch', 'batch', 'batchU')` (`#00`) at **Rank 15** (`ip_obj = 16.6275`), even though in the full flowsheet `#00` has less than half the vessel volume (`Total_CAPEX = 0.8608` $\text{m}^3$ vs. `2.6619` $\text{m}^3$) and a better productivity/crystal-size objective (`-170.68` vs. `-131.70`).
   - On the corrected `PharmaPy` model (`ssopt_gen_1_corrected_nomad.csv`), **`#00` `('batch', 'batch', 'batch', 'batchU')` moves from Rank 15 to Rank 1** (`ip_obj = 14.8590`), matching the true nonlinear flowsheet ranking.
2. **Elimination of `R02 = CSTR` Runaway Artifact and Missing `#10` `NaN`**:
   - Fixing the CSTR residence-time inversion (`88a7a0e`) lowers `f09` from `9.7170` to `6.5652`, removes the `-5.016e9` numerical blowup on `#06` `('batch', 'CSTR', 'batch', 'cont2')`, and populates `#10` `('batch', 'PFR', 'batch', 'cont2')` (`sm_obj_value = -213.2862`, `sm_capex = 13.0424`), which was `NaN` in the legacy 35-row table.

## Files in This Directory

- `discrete_ip_36_solutions_comparison.csv` — Side-by-side table of all 36 discrete superstructure configurations comparing `Legacy_IP_Rank`, `Corrected_Eval_IP_Rank`, `Corrected_Nomad_IP_Rank`, `ip_obj_value`, `sm_obj_value`, `sm_capex`, and `Corrected_Nomad_Turton_USD`.
- `nogoodcuts_corrected_nomad.json` — All 36 iterative no-good-cut MILP solutions solved on `../data/corrected_model_pharmapy_current/ssopt_gen_1_corrected_nomad.csv` paired with `PyNomad` re-optimized `PharmaPy` metrics.
- `nogoodcuts_corrected_eval.json` — All 36 iterative no-good-cut MILP solutions solved on `../data/corrected_model_pharmapy_current/ssopt_gen_1_corrected_eval.csv` paired with baseline corrected-model `PharmaPy` metrics.
- `nogoodcuts_legacy_edges_corrected_nomad_sim.json` — All 36 iterative no-good-cut MILP solutions solved on the legacy `../data/ssopt_gen_1.csv` edge costs paired with the corrected `PharmaPy` simulation metrics.
