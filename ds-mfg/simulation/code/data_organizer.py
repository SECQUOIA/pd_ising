from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from generating_structures import get_input_dictionary, make_graph, run_flowsheet
from helper import translate_scale


def organize_capex_data(
    compounds_path: Path = DATA_DIR / "compounds_lomustine.json",
    input_csv_path: Path = DATA_DIR / "obj_mass_prod_crys" / "x_input_sorted.csv",
    bounds_path: Path = DATA_DIR / "bounds.json",
    output_csv_path: Path = SCRIPT_DIR / "x_input_with_total_capex_2.csv",
) -> pd.DataFrame:
    """Extract CAPEX using PharmaPy's GetCAPEX for each configuration in x_input_sorted.csv."""
    data_lines = pd.read_csv(
        input_csv_path,
        header=0,
        names=["Combination", "Values"],
    )

    # Initialize 'CAPEX' and 'Total_CAPEX' columns in the DataFrame
    data_lines["CAPEX"] = None
    data_lines["Total_CAPEX"] = None

    with open(bounds_path, encoding="utf-8") as f:
        all_vars = json.load(f)

    for index, row in data_lines.iterrows():
        combo_str = row["Combination"]
        values_str = row["Values"]

        # Clean and format the combination string
        layout = tuple(
            combo_str.replace("('", "")
            .replace("')", "")
            .replace("'", "")
            .replace("_", " ")
            .split()
        )

        # Split the numeric values into a list of floats
        x = [float(val) for val in values_str.split()]

        graph = make_graph(layout)
        bound_dict = get_input_dictionary(all_vars, layout)
        input_dict = deepcopy(bound_dict)

        for count, key in enumerate(input_dict.keys()):
            input_dict[key] = translate_scale(x[count], bound_dict[key])

        # Calling PharmaPy
        flowsheet, success = run_flowsheet(
            path=str(compounds_path),
            inputs=input_dict,
            layout=layout,
            graph=graph,
        )

        if success:
            capex = flowsheet.GetCAPEX()
            total_capex = sum(capex.values())

            data_lines.at[index, "CAPEX"] = capex
            data_lines.at[index, "Total_CAPEX"] = total_capex

    if output_csv_path is not None:
        data_lines.to_csv(output_csv_path, index=False)

    return data_lines


def main() -> None:
    organize_capex_data()


if __name__ == "__main__":
    main()
