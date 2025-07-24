# CodeGPT SWE-Bench Results


## Directory Structure

```
.
├── data
│   └── results                                
│       ├── RUN_NAME               # Run by model 
│       │   ├── diffs              # Diff file per instance
│       │   ├── errors             # Error message (if any)
│       │   ├── patches            # Patch & fuzzy matching
│       │   └── trajs              # MultiAgent trajectories 
│       └── swe-bench              # SWE-Bench results for RUN_NAME
├── notebooks
│   ├── 00_create_graphs.ipynb     # Create graph for each instance
│   ├── 01_test_prompt.ipynb       # Test with a single instance 
│   ├── 02_get_patches.ipynb       # Get patches for all (30) instances
│   ├── 03_summarise_results.ipynb # Summarise results
│   ├── CodeGPT_Patcher.py         # MultiAgent Approach
│   └── utils.py                   # Utility functions
├── prompts
│   ├── agents.ts                  # MultiAgent prompts
│   └── tools_description.ts       # Tools description
├── README.md
└── requirements.txt
```

## Running swe-bench

After executing the `02_get_patches.ipynb` notebook, you can run the following command inside the SWE-bench repo to evaluate the results:

```
RUN_NAME=CodeGPT_MultiAgent_Llama4_Maverick
python -m swebench.harness.run_evaluation \
    --predictions_path /home/pudu/judini/swe-bench/data/results/$RUN_NAME.jsonl \
    --max_workers 2
``` 