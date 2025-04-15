#!/bin/bash
#SBATCH --job-name=sleep_array    # Job name
#SBATCH --array=1-5              # Array range (will create 5 jobs)
#SBATCH --time=00:01:00          # Time limit hrs:min:sec
#SBATCH --output=sleep_%a_%j.log # Standard output log (%a is array task ID, %j is job ID)
#SBATCH --error=sleep_%a_%j.err  # Standard error log
#SBATCH --cpus-per-task=1        # Number of CPUs per task

# Get the array task ID
TASK_ID=$SLURM_ARRAY_TASK_ID

# Sleep for TASK_ID * 10 seconds
sleep $((TASK_ID * 10))

# Print some information
echo "Task $TASK_ID completed after sleeping for $((TASK_ID * 10)) seconds"
echo "Host: $(hostname)"
echo "Job ID: $SLURM_JOB_ID"
echo "Array Job ID: $SLURM_ARRAY_JOB_ID"
echo "Array Task ID: $SLURM_ARRAY_TASK_ID"