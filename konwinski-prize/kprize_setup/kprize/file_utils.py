import json
import os
import re
import shutil
from pathlib import Path


def file_open(file_path: str, mode: str = 'w'):
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return open(file_path, mode)


def file_write(file_path: str, content: str, mode: str = 'w'):
    output_file = file_open(file_path, mode)
    output_file.write(content)
    output_file.close()


def read_json(file_path: str):
    with open(file_path, 'r') as f:
        json_data = json.load(f)
        return json_data


def read_jsonl(file_path: str):
    with open(file_path, 'r') as f:
        return [json.loads(line) for line in f]

def to_jsonl_str(json_list: list) -> str:
    jsonl_str = ""
    for entry in json_list:
        jsonl_str += json.dumps(entry) + "\n"
    return jsonl_str

def convert_json_to_jsonl(input_path: str, output_path: str):
    json_list = read_json(input_path)
    with open(output_path, 'w') as outfile:
        jsonl_str = to_jsonl_str(json_list)
        outfile.write(jsonl_str)
        outfile.close()


def strip_hidden_ascii(text: str):
    hidden_ascii_escape_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return hidden_ascii_escape_regex.sub('', text)


def strip_hidden_ascii_from_file(file_path: str):
    with open(file_path, "r") as f:
        content = strip_hidden_ascii(f.read())
        f.close()
    file_write(file_path, content)


def zip_dir(input_dir_path: str, output_dir_path: str):
    shutil.make_archive(base_name=output_dir_path, format='zip', root_dir=input_dir_path)


def create_dir_path(path: Path|str) -> Path:
    if isinstance(path, str):
        path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_directory_skip_existing(src, dst):
    def ignore_existing(dir, contents):
        return [f for f in contents if os.path.exists(os.path.join(dst, f))]

    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore_existing)


def copy_selective_files(src, dst, file_extensions: list[str] | None=None, specific_files: list[str] | None=None):
    """
    Copies only specific files from source to destination directory.

    Args:
    - src: Source directory
    - dst: Destination directory
    - file_extensions: List of file extensions to copy (e.g. ['.txt', '.py'])
    - specific_files: List of exact filenames to copy
    """
    def copy_filter(src_path):
        # If no filters are specified, copy everything
        if not file_extensions and not specific_files:
            return True

        # Get the filename
        filename = os.path.basename(src_path)

        # Check against specific filenames
        if specific_files and filename in specific_files:
            return True

        # Check against file extensions
        if file_extensions and any(filename.endswith(ext) for ext in file_extensions):
            return True

        return False

    shutil.copytree(src, dst, copy_function=shutil.copy2, ignore=lambda dir, contents:
    [item for item in contents if not copy_filter(os.path.join(dir, item))])

def copy_selective_dirs(src: Path, dst:Path, specific_dirs: list[str]):
    """
    Copies only specific directories from source to destination directory.

    Args:
    - src: Source directory
    - dst: Destination directory
    - dir_names: List of directory names to copy
    """
    sub_dirs = get_immediate_subdirectories(src)
    for sub_dir in sub_dirs:
        if sub_dir.name in specific_dirs:
            shutil.copytree(sub_dir, dst / sub_dir.name)

def get_immediate_subdirectories(path: Path) -> list[Path]:
    return [p for p in path.iterdir() if p.is_dir()]