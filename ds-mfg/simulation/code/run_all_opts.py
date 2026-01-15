"""
This script runs the NOMAD optimization algorithm for all possible
combinations of operating modes for the reactor, vaporizer, and crystallizer.

The script writes the current combination of operating modes to a file 'active_fs.txt'
and then runs the NOMAD optimization algorithm with the 'nomad_opt.py' script.

The script is designed to be run on a cluster with a job submission script that
will run this script for each combination of operating modes.

"""
import itertools
import datetime
import sys
import os
from pathlib import Path
from io import StringIO

# All reactor operating mode options
R01_opts = ['batch', 'CSTR', 'PFR']
R02_opts = ['batch', 'CSTR', 'PFR']

# All vaporizer operating mode options
VAP01_opts = ['batch']

# All crystallizer operating mode options
# cont# is continuous crystallizer with # crystallizer units 
CR01_opts = ['batchU', 'cont1', 'cont2', 'cont3']  

# Ordering 
UO_keys = {0: 'R01', 1: 'R02', 2: 'VAP01', 3: 'CR01'}
UO_keys_sb = {0: 'R01', 2: 'VAP01', 3: 'CR01'}

all_combos = list(itertools.product(*[R01_opts, R02_opts, VAP01_opts, CR01_opts]))
valid_combos = []

# 
for i in all_combos:
    if 'Semibatch' not in i:
        valid_combos.append(i)
    elif i[0] == 'Semibatch' and i[1] == 'Semibatch':
        # if R01 is semibatch, R02 must be semibatch for valid combo
        valid_combos.append(i)

# Save the valid combos to a file
with open('valid_combos.txt', 'w') as f:
    for i in valid_combos:
        f.write(str(i) + '\n')

# Create timestamp for this run
timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
run_id = f"run_{timestamp}"

# Create directories for systematic data storage
data_dir = Path(f"../data/obj_mass_prod_capex")
results_dir = Path(f"../results")
log_dir = Path(f"../logs")

# Ensure directories exist
data_dir.mkdir(parents=True, exist_ok=True)
results_dir.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)

# Create log file for this run
log_file_path = log_dir / f"logfile_{run_id}.txt"
combi_file_path = data_dir / f"valid_combos_{run_id}.txt"

# Save valid combos for this run
with open(combi_file_path, 'w') as f:
    for i in valid_combos:
        f.write(str(i) + '\n')

print(f"Starting optimization run: {run_id}")
print(f"Log file: {log_file_path}")
print(f"Combinations file: {combi_file_path}")
print(f"Total combinations to process: {len(valid_combos)}")

# Initialize log file
with open(log_file_path, 'w') as f:
    f.write(f"Optimization run started: {datetime.datetime.now()}\n")
    f.write(f"Run ID: {run_id}\n")
    f.write(f"Total combinations: {len(valid_combos)}\n")
    f.write("="*80 + "\n\n")

for i, combo in enumerate(valid_combos):
    file = 'active_fs.txt'

    with open(file, 'w') as filetowrite:
        for item in combo:
            filetowrite.write(item + ' ')

    print(f"Running NOMAD optimization for combo {i+1}/{len(valid_combos)}: {combo}")
    
    # Log the start of this combination
    with open(log_file_path, 'a') as f:
        f.write(f"\n{'='*60}\n")
        f.write(f"Combination {i+1}/{len(valid_combos)}: {combo}\n")
        f.write(f"Started at: {datetime.datetime.now()}\n")
        f.write(f"{'='*60}\n")

    # Capture output from nomad_opt.py using file descriptor redirection
    try:
        # Create a temporary file to capture output
        import tempfile
        import shutil
        
        # Create a temporary file for capturing output
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt') as temp_file:
            temp_filename = temp_file.name
        
        # Store original file descriptors
        original_stdout_fd = os.dup(1)  # stdout
        original_stderr_fd = os.dup(2)  # stderr
        
        # Open the temporary file for writing
        temp_fd = os.open(temp_filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        
        # Redirect stdout and stderr to the temporary file
        os.dup2(temp_fd, 1)  # Redirect stdout
        os.dup2(temp_fd, 2)  # Redirect stderr
        
        try:
            # Execute the nomad_opt.py script
            exec(open("nomad_opt.py").read())
        finally:
            # Restore original file descriptors
            os.dup2(original_stdout_fd, 1)  # Restore stdout
            os.dup2(original_stderr_fd, 2)  # Restore stderr
            
            # Close the temporary file descriptor
            os.close(temp_fd)
            os.close(original_stdout_fd)
            os.close(original_stderr_fd)
        
        # Read the captured output from the temporary file
        with open(temp_filename, 'r') as temp_file:
            captured_output = temp_file.read()
        
        # Clean up the temporary file
        os.unlink(temp_filename)
        
        # Write the captured output to the log file
        with open(log_file_path, 'a') as f:
            if captured_output:
                f.write(captured_output)
                f.flush()  # Ensure it's written immediately
        
        # Also print to console
        if captured_output:
            print(captured_output)
            
    except Exception as e:
        error_msg = f"Error running nomad_opt.py: {e}\n"
        print(error_msg)
        with open(log_file_path, 'a') as f:
            f.write(error_msg)

# Log completion
with open(log_file_path, 'a') as f:
    f.write(f"\n{'='*80}\n")
    f.write(f"Optimization run completed: {datetime.datetime.now()}\n")
    f.write(f"Run ID: {run_id}\n")

print(f"\nOptimization run completed!")
print(f"Log file: {log_file_path}")
print(f"To process the data, run:")
print(f"python process_results.py {run_id} --save --summary")
