from kprize.constants import KEY_INSTANCE_ID

# This class helps to generate a Jupyter notebook that sets up the environment for a task instance


def get_code_cell(execution_count: int, source: list[str]) -> dict:
    """
    Generate a code cell for a Jupyter notebook.
    :param execution_count:
    :param source:
    :return:
    """
    return {
        "cell_type": "code",
        "execution_count": execution_count,
        "metadata": {},
        "outputs": [],
        "source": source
    }


def get_instance_setup_notebook(instances: list[dict], force_online: bool = False) -> dict:
    """
    Generate a Jupyter notebook that sets up the environment for a task instance
    :param instances: List of task instances
    :param force_online: This is ignore local assets and run in online mode (requires internet)
    :return:
    """
    instance_ids = list(map(lambda i: i[KEY_INSTANCE_ID], instances))
    kprize_assets_dir = "/kaggle/input/kprize-assets"
    kprize_setup_dir = f"{kprize_assets_dir}/kprize_setup"
    return {
        "cells": [
            get_code_cell(1, [
                f"!conda config --add channels file:///{kprize_assets_dir}/conda_packages\n" if not force_online \
                else "!echo 'Running conda in online mode'\n",
                f"!mkdir -p /root/.config/pip/\n",
                f"!cp {kprize_setup_dir}/pip.conf /root/.config/pip/pip.conf\n" if not force_online \
                else "!echo 'Running pip in online mode'\n",
                f"!pip install {kprize_setup_dir}/swebench-2.1.0-py3-none-any.whl\n",
            ]),
            get_code_cell(2, [
                "# Load datasets\n",
                "from kprize.constants import KEY_INSTANCE_ID, KEY_REPO\n",
                "from kprize.collection_utils import filter_by_key, group_by_key\n",
                "from kprize.dataset_utils import read_dataset_from_dir\n",
                "from kprize.eval_utils import run_instances, get_gold_predictions_from_dataset\n",
                "from kprize.evaluation.data_path_handler import DataPathHandler\n",
                "from kprize.evaluation.kprize_env_handler import KprizeEnvHandler\n"
                "print(\"Loading task instance datasets...\")\n",
                "# Read datasets from Kaggle input\n",
                f"dataset = read_dataset_from_dir(\"{kprize_assets_dir}/task_instances\")\n",
                "print(f\"Dataset loaded. {len(dataset)} instances.\")\n",
                "# Filter dataset\n",
                f"ds = filter_by_key(dataset, KEY_INSTANCE_ID, {instance_ids})\n",
                "predictions = get_gold_predictions_from_dataset(ds)\n",
                f"env_handler=KprizeEnvHandler('{kprize_assets_dir}', '/kaggle/working/output')\n",
                f"data_path_handler = DataPathHandler('{kprize_assets_dir}', '/kaggle/input/','/kaggle/working/')\n",
                f"run_instances(ds, predictions,  env_handler=env_handler, data_path_handler=data_path_handler, " +
                f"run_evaluation=False, force_online={force_online}, " +
                "use_instance_repos=True, log_commands=True)\n",
            ]),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

def get_instance_setup_notebook_venv(instances: list[dict]) -> dict:
    """
    Generate a Jupyter notebook that sets up the environment for a task instance
    :param instances: List of task instances
    :param force_online: This is ignore local assets and run in online mode (requires internet)
    :return:
    """
    instance_ids = list(map(lambda i: i[KEY_INSTANCE_ID], instances))
    kprize_assets_dir = "/kaggle/input/kprize-assets"
    kprize_setup_dir = f"{kprize_assets_dir}/kprize_setup"
    output_dir = f"/kaggle/working/output/venv_repos/"
    return {
        "cells": [
            get_code_cell(1, [
                f"!pip install {kprize_setup_dir}/swebench-2.1.0-py3-none-any.whl\n",
            ]),
            get_code_cell(2, [
                "# Load datasets\n",
                "from pathlib import Path\n",
                "from kprize.constants import KEY_INSTANCE_ID, KEY_REPO\n",
                "from kprize.collection_utils import filter_by_key, group_by_key\n",
                "from kprize.dataset_utils import read_dataset_from_dir\n",
                "from kprize.eval_utils import build_instances_venv\n",
                "from kprize.evaluation.data_path_handler import DataPathHandler\n",
                "from kprize.evaluation.kprize_env_handler import KprizeEnvHandler\n"
                "print(\"Loading task instance datasets...\")\n",
                "# Read datasets from Kaggle input\n",
                f"dataset = read_dataset_from_dir(\"{kprize_assets_dir}/task_instances\")\n",
                "print(f\"Dataset loaded. {len(dataset)} instances.\")\n",
                "# Filter dataset\n",
                f"ds = filter_by_key(dataset, KEY_INSTANCE_ID, {instance_ids})\n",
                f"env_handler=KprizeEnvHandler('{kprize_assets_dir}', '/kaggle/working/output')\n",
                f"data_path_handler = DataPathHandler('{kprize_assets_dir}', '/kaggle/input/','/kaggle/working/')\n",
                f"output_repo_dir = Path('{output_dir}')\n",
                f"build_instances_venv(ds, env_handler=env_handler, data_path_handler=data_path_handler, " +
                "output_repo_dir=output_repo_dir, log_commands=True, log_console=True)\n",
                ]),
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }
