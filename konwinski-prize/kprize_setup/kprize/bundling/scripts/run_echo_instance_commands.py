import argparse
from pathlib import Path

from kprize.collection.constants import KPRIZE_CONSTANTS
from kprize.collection_utils import group_by_key, filter_by_key
from kprize.constants import KEY_REPO, KEY_INSTANCE_ID
from kprize.dataset_utils import read_dataset_from_dir
from kprize.docker_paths import get_input_conda_channel_dir, get_input_pip_packages_dir
from kprize.evaluation.data_path_handler import DataPathHandler
from kprize.harness.pip_env_manager import PipEnvManagerType, PipEnvManager
from kprize.harness.test_spec_creator import TestSpecCreator


def log_instance_commands(
        instances: list[dict[str, any]],
        env_manager: PipEnvManagerType = PipEnvManagerType.MICROMAMBA
):
    print("Logging instance commands...")
    pip_env_manager = PipEnvManager(
        env_manager,
        python_version="3.11",
        local_conda_channel_dir=Path(get_input_conda_channel_dir()),
        local_pip_packages_dir=Path(get_input_pip_packages_dir()),
    )
    spec_creator = TestSpecCreator(
        pip_env_manager=pip_env_manager,
        instance_repos_dir=Path("dependencies/collected/venv_repos/"),
        #local_repos_dir=Path("dependencies/collected/git_repos/"),
        repo_config_dir=Path("repo_configs"),
        disable_apt_install=True,
        reset_tests_after_eval=False,
        include_install_in_repo_setup=False,
        # activate_only_in_eval=True,
    )
    for instance in instances:
        instance_id = instance[KEY_INSTANCE_ID]
        test_patch = instance["test_patch"]
        model_patch = instance["patch"]
        test_patch_path = Path("patches/") / f"test_patch_{instance_id}.diff"
        model_patch_path = Path("patches/") / f"model_patch_{instance_id}.diff"
        print(f"Instance: {instance_id} commit={instance['base_commit']}")
        test_spec = spec_creator.make_test_spec(
            instance,
            test_patch_path=test_patch_path,
            model_patch_path=model_patch_path,
        )
        # spec_creator.create_test_patch_file(instance_id, test_patch, Path("patches/"))
        # spec_creator.create_model_patch_file(instance_id, model_patch, Path("patches/"))
        print("ENV commands:")
        print(test_spec.env_script_list)
        print("REPO commands:")
        print(test_spec.repo_script_list)
        print("EVAL commands:")
        print(test_spec.eval_script_list)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--instances-dir",
        help="Directory of task instance datasets",
        type=str,
        default=Path("task_instances/test_scrap").absolute(),
    )
    parser.add_argument(
        "-c",
        "--count",
        help="Number of instances to log",
        type=int,
        default=None
    )
    parser.add_argument(
        "-e",
        "--env",
        help="Environment manager to use",
        type=str,
        default=PipEnvManagerType.MICROMAMBA.value
    )
    parser.add_argument(
        "-i",
        "--instance",
        help="Instance ID to log",
        type=str,
        default=None
    )
    args = parser.parse_args()

    KPRIZE_CONSTANTS.use_kprize_configs = True
    KPRIZE_CONSTANTS.latest_config_path = "repo_configs"

    print(f" > instances-dir={args.instances_dir}")
    loaded_instances = read_dataset_from_dir(args.instances_dir)
    print(f"Loaded {len(loaded_instances)} instances")

    if args.instance:
        loaded_instances = filter_by_key(loaded_instances, KEY_INSTANCE_ID, [args.instance.strip()])
    elif args.count:
        loaded_instances = loaded_instances[:args.count]

    log_instance_commands(loaded_instances, PipEnvManagerType[args.env])

    # data_path_handler = DataPathHandler("dependencies/kaggle_dataset/train", verbose=True)
    # # env_handler = KprizeEnvHandler("kprize-assets-new", verbose=True)
    # data_path_handler.unpack_data_path()
    # full_dataset = data_path_handler.read_instances()
    # print(full_dataset)

    # log_file = Path("dependencies/docker/working/output/logs/instance_id/test_output.txt")
    # log_info = PytestLogParser.parse(log_file)
    # print(jsons(asdict(log_info)))

