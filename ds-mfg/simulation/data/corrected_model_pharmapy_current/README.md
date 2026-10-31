# Corrected-Model Lomustine Superstructure Simulation & Black-Box Optimization Tables (`PharmaPy 3194efd`)

> **Provenance Notice**: All files in this directory were generated on the **corrected current `PharmaPy` model (`3194efd`)** without altering any of the legacy 2022–2023 provenance records in `../` (`optimal_points_2.json`, `optimal_points_2_PFR.json`, `optimal_mass_size_2_fixed.json`, `obj_mass_prod_crys/x_input_sorted.csv`, and `obj_mass_prod_crys/x_input_with_total_capex.csv`).

## Why These Tables Differ from the Legacy 2022–2023 Provenance Files

Between the original 2022–2023 superstructure runs (`PharmaPy` commit `04499cc`) and current `PharmaPy` (`3194efd`), four upstream model defects affecting the Lomustine flowsheet were resolved:

1. **`CSTR.material_balance` residence-time inversion (`PharmaPy` commit `88a7a0e`)**:
   - In 2022 `PharmaPy`, the CSTR dilution term used an inverted residence time ($\tau$).
   - In the legacy NOMAD run recorded in `../obj_mass_prod_crys/x_input_sorted.csv`, the optimizer exploited this bug on the 12 `R02 == 'CSTR'` configurations (`#04`–`#07`, `#16`–`#19`, `#28`–`#31`) by driving $\tau_{\text{R02}} \to 0$, producing unphysical runaway `lom` concentrations (`sm_obj_value = -1541.91` on `#28` and a numerical blowup `-5.016e9` on `#06`) and forcing `ratio_hept` up to `1.0–3.8`, which inflated the `R02 == 'CSTR'` edge cost `f09` in `ds-mfg/discrete_ip/data/ssopt_gen_1.csv` to `9.717`.
   - In the corrected `PharmaPy` model (`3194efd`), `CSTR` strictly obeys species conservation ($0 \le X \le 1$), eliminating the runaway concentrations and numerical blowup on `#06`.
2. **`LiquidPhase` / `LiquidStream` solvent-free concentration closure (`PharmaPy` commit `8109dd6`, issue `#439`)**:
   - When `name_solv='THF'` and `mole_conc` are specified (`R01` feed and `Semibatch` `TBN` feed), the `THF` solvent mole fraction is now closed from pure-species liquid molar volumes ($1 - \sum_{j \ne \text{solv}} C_j / \rho_{j,\text{mol}}$) rather than the approximate mixture molar density, shifting `R01` conversion by ~2.5%.
3. **`DynamicCollector` liquid species inventory integration (`PharmaPy` commit `87d0bdd`, issue `#467`)**:
   - `DynamicCollector` (`HOLD01`, `HOLD02`) now integrates extensive liquid molar inventories $N_j$ [$\text{mol}$] rather than intensive mole fractions, ensuring exact species conservation across continuous-to-batch transitions.
4. **`DynamicCollector` slurry holdup volume accounting in `GetCAPEX()` (`PharmaPy` `Containers.py`)**:
   - In 2022 `PharmaPy` (`04499cc`), `DynamicCollector` after a continuous `MSMPR` crystallizer (`cont1`, `cont2`, `cont3`) set `self.vol_phase = self.Outlet.vol_slurry`, which read the un-updated default `vol_slurry = 1.0` $\text{m}^3$ on `Slurry`, causing every `HOLD` tank after continuous crystallization to report an identical vessel volume of $1.0 / 0.75 = 1.333333\text{ m}^3$ (`f17 = 1.333` in `ssopt_gen_1.csv`) regardless of throughput.
   - Current `PharmaPy` (`3194efd`) sets `self.vol_phase = self.Outlet.vol` (`Liquid_1.vol + Solid_1.vol`), reporting the true accumulated slurry holdup capacity ($V_{\text{slurry}} / 0.75$ [$\text{m}^3$]).
5. **Complete 36 / 40 Configuration Coverage**:
   - The legacy `../obj_mass_prod_crys/x_input_sorted.csv` file had 35 rows and was missing configuration `#10` `('batch', 'PFR', 'batch', 'cont2')` (which appeared as `NaN` at Rank 9 in `gurobi_nogoodcuts_results_20260123_151347.json`). All tables in this directory cover all **36** two-reactor configurations (`#00`–`#35`) and all **40** superstructure configurations (`#00`–`#39`, including `#36`–`#39` `Semibatch`).

## Files in This Directory

- `all40_corrected_model_evaluation_and_nomad.json` — Complete record of both the baseline evaluation (at the published AIChE J 2023 `optimal_points_2.json` + `optimal_points_2_PFR.json` decision vectors) and the `PyNomad` (`PyNomadBBO 4.6.0`) black-box re-optimization across all 40 superstructure configurations (`#00`–`#39`).
- `optimal_points_corrected_nomad.json` — Normalized (`[0, 1]^d`) decision vectors for all 40 configurations re-optimized with `PyNomad` on the corrected `PharmaPy` model.
- `optimal_mass_size_corrected_eval.json` — `[mass_productivity_kg_s, mean_crystal_size_um]` for all 40 configurations evaluated at the published 2023 decision vectors on the corrected `PharmaPy` model.
- `optimal_mass_size_corrected_nomad.json` — `[mass_productivity_kg_s, mean_crystal_size_um]` for all 40 configurations at the `PyNomad` re-optimized points on the corrected `PharmaPy` model.
- `x_input_sorted_corrected_eval.csv` & `x_input_sorted_corrected_nomad.csv` — Decision vectors `(Combination, x)` for all 36 two-reactor configurations (`#00`–`#35`, including `#10` `('batch', 'PFR', 'batch', 'cont2')`).
- `x_input_with_total_capex_corrected_eval.csv` & `x_input_with_total_capex_corrected_nomad.csv` — Unit-by-unit `flowsheet.GetCAPEX()` equipment capacities (`CAPEX`, `Total_CAPEX`) and Turton bare-module equipment costs (`Turton_CAPEX_USD`, `Total_Turton_CAPEX_USD` [USD] computed via `../capex_coeff.csv`) for all 36 two-reactor configurations.
- `run_objmassprodcrys_sum_corrected_eval.csv` & `run_objmassprodcrys_sum_corrected_nomad.csv` — 36-configuration summary tables directly compatible with `FlowsheetOptimizer` in `ds-mfg/discrete_ip/flst_opti_IP.py` (plus `run_objmassprodcrys_sum_all40_corrected_*.csv` covering all 40 configurations).
