import os
import json
import time
import pandas as pd

from helper import set_openai_key,\
                    test_openai_api,\
                    create_openai_client,\
                    function_to_schema

from helper import generate_tree_string,\
                    get_lines_from_file,\
                    search_code, \
                    get_object_definition,\
                    generate_patches

from agent import Agent

# Define paths
comp_dir = "konwinski-prize"
comp_kaggle_evaluation_dir = os.path.join(comp_dir, "kaggle_evaluation")
comp_kprize_setup_dir = os.path.join(comp_dir, "kprize_setup")
comp_data_zip_path = os.path.join(comp_dir, "data.a_zip")
comp_data_dir = os.path.join(comp_dir, "data")
comp_data_parquet_path = os.path.join(comp_data_dir, "data.parquet")
comp_conda_packages_dir = os.path.join(comp_data_dir, "conda_packages")
comp_pip_packages_dir = os.path.join(comp_data_dir, "pip_packages")
comp_repo_configs_dir = os.path.join(comp_data_dir, "repo_configs")
comp_repos_dir = os.path.join(comp_data_dir, "repos")

# Create client
model_name = "gpt-3.5-turbo"
set_openai_key()
test_openai_api()
client = create_openai_client()

# Read Dataframe
kprize_df = pd.read_parquet(comp_data_parquet_path)

for idx in range(len(kprize_df)):
    
    # Get current repo data
    row = kprize_df.iloc[idx]
    problem_statement = row["problem_statement"]
    instance_id = row["instance_id"]
    repo_path = os.path.join(comp_repos_dir, f'repo__{instance_id}')
    print(repo_path)

    system_prompt_template = """
    ### Context
    You are a software automation agent responsible for diagnosing and resolving issues in a repository.  
    Your task is to configure and utilize the provided tools efficiently.  
    If the tools are insufficient, identify the gap, propose alternatives, and justify their necessity.  
    Only call generate_patches if you can specify the exact files and modifications needed to resolve the issue.  
    Do not request permission or confirmation before executing an action or generating a patch.  

    ### Metadata
    - Repository root path: {repo_path}
    """

    tools = [generate_tree_string, get_lines_from_file, search_code, get_object_definition, generate_patches]
    tool_schemas = [function_to_schema(tool) for tool in tools]
    tools_map = {tool.__name__: tool for tool in tools}

    # Init messages
    messages = []
    system_prompt = system_prompt_template.format(repo_path=repo_path)
    messages.append({"role":"system","content":system_prompt})
    prompt = "Generate a patch to resolve the following repository issue:\n{problem_statement}"
    prompt = prompt.format(problem_statement=problem_statement)
    messages.append({"role":"user","content":prompt})

    # Create agent and 
    swe_agent = Agent(client, tool_schemas, tools_map, messages, model_name)
    swe_agent.run()
    steps = swe_agent.steps
    with open(f"agent_steps_{instance_id}.json", "w") as f:
        json.dump(steps, f, indent=2)

    time.sleep(60)