# Lomustine Superstructure Simulation (`ds-mfg/simulation`)

This directory contains the **PharmaPy** mechanistic flowsheet simulation, superstructure graph generator, and black-box optimization scripts that generate the unit-operation capital cost (`capex_coeff.csv`) and raw-material flow cost (`raw_material_cost.csv`) tables consumed by the discrete MILP and QUBO superstructure optimization models in `ds-mfg/discrete_ip/`.

## Process Description and References

The case study models the end-to-end synthesis, solvent switch, cooling crystallization, and filtration of **lomustine** (`lom`, an anticancer active pharmaceutical ingredient) across 40 valid hybrid batch/continuous flowsheet configurations:

1. **First synthesis step (`R01`)**: `ISO + CHA --> interm` in `THF` solvent (`BatchReactor`, `CSTR`, `PlugFlowReactor`, or single-vessel `SemibatchReactor`).
2. **Second synthesis step (`R02`)**: `interm + TBN --> lom + TBA` with parallel side reaction `ISO + TBA --> SUB1` (`BatchReactor`, `CSTR`, `PlugFlowReactor`, or combined in `SemibatchReactor`).
3. **Solvent-switch vaporization (`VAP01`)**: Batch `Evaporator` removing volatile `THF` after adding `C7` (*n*-heptane) antisolvent (`MIX02`).
4. **Crystallization (`CR01`–`CR03`)**: Unseeded cooling `BatchCryst` (`batchU`) or a 1-, 2-, or 3-stage continuous `MSMPR` cascade (`cont1`, `cont2`, `cont3`).
5. **Filtration (`F01`)**: Batch cake filtration (`Filter`), with automatic insertion of `BatchToFlowConnector` (`BatchToFlow01`, `BatchToFlow02`) for batch-to-continuous transitions and `DynamicCollector` (`HOLD01`, `HOLD02`) for continuous-to-batch transitions.

### Primary References

- Casas-Orozco, D., Laky, D. J., Wang, V., Abdi, M., Feng, X., Wood, E., Laird, C. D., Reklaitis, G. V., & Nagy, Z. K. (2023). Techno-economic analysis of dynamic, end-to-end optimal pharmaceutical campaign manufacturing using PharmaPy. *AIChE Journal*, 69(9), e18142. https://doi.org/10.1002/aic.18142
- Barhate, Y., Laky, D. J., Casas-Orozco, D., Reklaitis, G. V., & Nagy, Z. K. (2025). Hybrid rule-based and optimization-driven framework for the synthesis of end-to-end optimal pharmaceutical processes. *AIChE Journal*, e18888. https://doi.org/10.1002/aic.18888

## Directory Layout

- `code/`
  - `generating_structures.py` — Enumerates the 40 valid superstructure operating-mode combinations (`valid_combos`), constructs PharmaPy flowsheet connectivity strings (`make_graph`), builds and solves flowsheets (`make_flowsheet`, `run_flowsheet`), and evaluates mass productivity, crystal size, capital cost, and path/endpoint constraints (`get_mass_and_size`, `get_objective_value`, `get_objective_value_cost`, `get_constraints_values`).
  - `make_units.py` — Configures PharmaPy unit operations (`BatchReactor`, `SemibatchReactor`, `CSTR`, `PlugFlowReactor`, `Evaporator`, `BatchCryst`, `MSMPR`, `Filter`, `Mixer`, `DynamicCollector`, `BatchToFlowConnector`).
  - `helper.py` — Reaction kinetics (`get_rxn_kinetics`), crystallization kinetics and solubility correlation (`get_cryst_kinetics`, `solub_fn`), path constraint integration (`path_constraint`), and `[0, 1]` variable unscaling (`translate_scale`).
  - `config_mapping.py` — Exports superstructure operating-mode combinations and decision-variable bounds.
  - `data_organizer.py` — Evaluates `flowsheet.GetCAPEX()` across the optimized configurations in `data/obj_mass_prod_crys/x_input_sorted.csv`.
  - `nomad_opt.py` & `run_all_opts.py` — PyNomad black-box optimization drivers for individual and batch superstructure configurations.
  - `process_results.py` — Parses NOMAD optimization log files into summary tables.
- `data/`
  - `compounds_lomustine.json` — 9-species thermophysical property database (`ISO`, `CHA`, `interm`, `TBN`, `lom`, `TBA`, `SUB1`, `THF`, `C7`).
  - `bounds.json` — Decision-variable lower and upper bounds for each unit operation and operating mode.
  - `optimal_points_2.json` & `optimal_points_2_PFR.json` — Normalized (`[0, 1]`) optimal decision variables for all 40 superstructure configurations (`#00`–`#39`, with updated `PFR` configurations `#24`–`#35` in `optimal_points_2_PFR.json`).
  - `optimal_mass_size_2_fixed.json` — Reference `[mass_production_kg_per_s, mean_crystal_size_um]` values across the 40 optimal configurations.
  - `capex_coeff.csv` & `raw_material_cost.csv` — Aggregated unit-operation capital and raw-material costs used by `ds-mfg/discrete_ip/`.
  - `obj_mass_prod_crys/` — Sorted NOMAD decision vectors (`x_input_sorted.csv`) and extracted unit-operation CAPEX table (`x_input_with_total_capex.csv`).

## Running Simulations and Tests

From the repository root (in an environment with `PharmaPy` and `assimulo` installed):

```bash
pytest tests/test_ds_mfg_simulation.py
```

To re-evaluate all 40 optimal superstructure configurations:

```bash
python ds-mfg/simulation/code/generating_structures.py
```
