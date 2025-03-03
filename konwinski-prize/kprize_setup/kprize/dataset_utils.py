import glob
import shutil
import pandas as pd
from pathlib import Path

from kprize.constants import KAGGLE_INPUT_DIR
from kprize.file_utils import read_json, read_jsonl


def read_dataset_from_dir(dir_path: str, file_filter: str = '*task-instances*'):
    """
    Reads in JSON and JSONL datasets from directory
    :param dir_path: Directory with JSON, JSONL datasets
    :param file_filter: Filter specific dataset files by name
    :return:
    """
    dataset = []
    json_data_files = glob.glob(f"{dir_path}/{file_filter}.json")
    if json_data_files and len(json_data_files) > 0:
        for path in json_data_files:
            dataset = dataset + read_json(path)

    jsonl_data_files = glob.glob(f"{dir_path}/{file_filter}.jsonl")
    if jsonl_data_files and len(jsonl_data_files) > 0:
        for path in jsonl_data_files:
            dataset = dataset + read_jsonl(path)

    return dataset


def read_kaggle_input_dataset(contains: str = 'task-instances'):
    """
    Reads in JSON and JSONL datasets from Kaggle input directory
    :param contains: Filter specific datasets by name
    :return:
    """
    return read_dataset_from_dir(f"{KAGGLE_INPUT_DIR}/*{contains}*", '*')


def extract_offline_assets_from_dataset(input_dir: str, output_dir: str):
    """
    Extract offline assets from dataset

    This handles extracting repos, conda_packages from a Kprize dataset
    :param input_dir:
    :param output_dir:
    :return:
    """
    input_compressed_assets_path = Path(input_dir) / "compressed_assets.z"

    # Unzip repos to working directory
    shutil.unpack_archive(input_compressed_assets_path, output_dir, format='zip')

def convert_task_instance_list_to_parquet(task_instance_list: list[dict], output_path: Path):
    """
    Convert a list of task instances to a Parquet file
    :param task_instance_list: List of task instances
    :param output_path: Output Parquet file
    :return:
    """
    df = pd.DataFrame(task_instance_list)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path)

def convert_jsonl_directory_to_parquet(input_path: Path, output_path: Path):
    """
    Convert JSONL files to Parquet
    :param input_path: Directory containing JSONL files
    :param output_path: Output Parquet file
    :return:
    """
    dataframes = []
    jsonl_files = input_path.glob("*.jsonl")
    for file in jsonl_files:
        df = pd.read_json(file, lines=True)
        dataframes.append(df)
    combined_df = pd.concat(dataframes, ignore_index=True)

    # Create output parquet file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_parquet(output_path)
