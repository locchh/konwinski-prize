from __future__ import annotations

import re
import shutil
from pathlib import Path

from swebench.harness.constants import ResolvedStatus
from kprize.harness.grading import (
    FAIL_TO_PASS,
    KEY_INSTANCE_ID,
    PASS_TO_PASS,
    get_eval_report,
    get_resolution_status,
)
from kprize.bundling.python_install_dependency_parser import get_channels_block_from_environment_yml
from kprize.collection.constants import KPRIZE_CONSTANTS
from kprize.collection_utils import (
    filter_by_key,
    get_item_by_field,
    get_key_values,
    group_by_key,
)
from kprize.constants import (
    KAGGLE_EVAL_PYTHON_VERSION,
    KAGGLE_OUTPUT_DIR,
    KEY_REPO,
)
from kprize.docker_paths import (
    get_model_patch_file_path,
    get_test_patch_file_path,
    get_working_kprize_assets_dir,
)
from kprize.evaluation.data_path_handler import DataPathHandler
from kprize.evaluation.kprize_env_handler import KprizeEnvHandler
from kprize.file_utils import (
    create_dir_path,
    file_open,
    file_write,
    strip_hidden_ascii_from_file,
)
from kprize.harness.pip_env_manager import (
    PipEnvManager,
    PipEnvManagerType,
)
from kprize.harness.test_spec_creator import TestSpecCreator
from kprize.json_utils import jsons
from kprize.subprocess_utils import (
    echo_command_start_and_finish,
    run_commands,
)
from kprize.time_utils import current_ms, seconds_since


def get_tmp_conda_environment_yml_path(instance_id: str) -> str:
    return f"/root/conda_envs/{instance_id}/environment.yml"


def update_environment_yml_with_local_channel(environment_yml_path: Path, conda_channel_path: Path):
    """
    Update environment.yml to use local conda channel (for offline)

    WARNING: This is not currently used, but may be needed in the future to support conda projects.
    """
    if not environment_yml_path.exists():
        print(f"Environment file not found: {environment_yml_path}")
        return
    if not conda_channel_path.exists():
        print(f"Conda channel not found: {conda_channel_path}")
        return
    environment_yml_content = environment_yml_path.read_text()
    if not environment_yml_content:
        print(f"Environment file is empty: {environment_yml_path}")
        return

    # Add local channel to environment.yml
    channels = get_channels_block_from_environment_yml(environment_yml_content)
    local_conda_channel_content = environment_yml_content.replace(
        channels, f"channels:\n  - file://{conda_channel_path}\n"
    )
    environment_yml_path.write_text(local_conda_channel_content)
    print(f"Updated environment.yml with local channel.\n{local_conda_channel_content}\n")


def get_heredoc_content(heredoc_cmd: str, heredoc_delimiter: str):
    # WARNING: This pattern doesn't seem to work with DOTALL
    # pattern = f"{heredoc_delimiter}'[a-zA-Z_ ]*\n(.*){heredoc_delimiter}"
    # result = re.search(pattern, heredoc_cmd, re.DOTALL)

    # HACK: Instead just remove the first line to get the correct match...
    pos_first_newline = heredoc_cmd.find("\n")
    command_after_first_newline = heredoc_cmd[pos_first_newline:]

    pattern = f"(.*){heredoc_delimiter}"
    result = re.search(pattern, command_after_first_newline, re.DOTALL)

    if result:
        content = result.group(1)
        return content
    else:
        print("ERROR: Unable to extract diff content")
        return False


#  e.g. # cat <<'EOF_59812759871' > $HOME/requirements.txt
def get_heredoc_output_file_path(heredoc_cmd: str, heredoc_delimiter: str):
    pattern = f"{heredoc_delimiter}' > (.*)\n"
    result = re.search(pattern, heredoc_cmd)

    if result:
        file_name = result.group(1)
        print(f"Extracted HEREDOC output file: {file_name}")
        return file_name
    else:
        print("ERROR: Unable to extract file_name from HEREDOC content")
        return False


def create_prediction(instance_id: str, model_patch: str, model_name_or_path: str):
    return {
        KEY_INSTANCE_ID: instance_id,
        "model_patch": model_patch,
        "model_name_or_path": model_name_or_path,
    }


def get_gold_predictions_from_dataset(dataset: dict):
    """
    Get gold predictions for the given data.
    """
    return [create_prediction(datum[KEY_INSTANCE_ID], datum["patch"], "gold") for datum in dataset]


def create_test_patch_file(instance_id: str, test_patch: str, output_dir: Path | None = None) -> Path:
    """
    Create a test patch file for a given instance.
    """
    patch_file = get_test_patch_file_path(instance_id, output_dir)
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(test_patch)
    return patch_file


def create_model_patch_file(instance_id: str, model_patch: str, output_dir: Path | None = None) -> Path:
    """
    Create a test patch file for a given instance.
    """
    patch_file = get_model_patch_file_path(instance_id, output_dir)
    patch_file.parent.mkdir(parents=True, exist_ok=True)
    patch_file.write_text(model_patch)
    return patch_file


def run_instances(
    instances: list[dict],
    predictions: list[dict],
    env_handler: KprizeEnvHandler,
    data_path_handler: DataPathHandler,
    apply_model_patch=True,
    run_evaluation=True,
    log_commands=False,
    log_console=False,
    force_online=False,
    use_instance_repos=True,
    use_venv_repos=False,
    pip_env_manager=PipEnvManagerType.MICROMAMBA,
    use_test_patch_file=True,
    force_x86=False,
):
    run_start_ms = current_ms()
    report_map = {}
    run_stats_map = {}
    print(f"==== RUN {run_start_ms} ====")
    print(f"instances = {len(instances)}")
    print(f"apply_model_patch = {apply_model_patch}")
    print(f"force_x86 = {force_x86}")

    KPRIZE_CONSTANTS.use_kprize_configs = True
    KPRIZE_CONSTANTS.latest_config_path = data_path_handler.repo_config_dir

    use_local_conda_channel = False if force_online else data_path_handler.has_local_conda_channel
    # Always use test patch file for instance repos
    use_test_patch_file = use_test_patch_file or use_instance_repos
    use_instance_repos = not force_online and use_instance_repos

    pip_env_manager = PipEnvManager(
        manager=pip_env_manager,
        python_version=KAGGLE_EVAL_PYTHON_VERSION,
        local_conda_channel_dir=data_path_handler.conda_channel_dir if use_local_conda_channel else None,
        local_pip_packages_dir=data_path_handler.pip_packages_dir,
        force_x86=force_x86,
    )

    repos_dir = None
    if use_venv_repos:
        repos_dir = data_path_handler.venv_repo_dir
    elif use_instance_repos:
        repos_dir = data_path_handler.repo_dir

    test_spec_creator = TestSpecCreator(
        pip_env_manager=pip_env_manager,
        instance_repos_dir=repos_dir,
        repo_config_dir=data_path_handler.repo_config_dir,
        disable_apt_install=not force_online,
        reset_tests_after_eval=False,
        include_install_in_repo_setup=not run_evaluation,
        activate_only_in_eval=use_venv_repos,
    )

    for instance_index, instance in enumerate(instances):
        start_instance_ms = current_ms()

        # Get instance data
        instance_id = instance[KEY_INSTANCE_ID]
        print(f"\n==== INSTANCE '{instance_id}' ({instance_index + 1} of {len(instances)}) ====")

        log_file_path = f"{env_handler.output_dir}/logs/{instance_id}/test_output.txt"
        log_file = file_open(log_file_path, "w")
        setup_log_file_path = f"{env_handler.output_dir}/logs/{instance_id}/setup_output.txt"
        setup_log_file = file_open(setup_log_file_path, "w")
        run_stats = {
            "instance_id": instance_id,
        }

        # Delete existing testbed
        print("Clearing testbed.")
        remove_testbed_commands = [f"rm -rf {env_handler.get_test_bed_path()}"] + pip_env_manager.global_env_remove_cmds
        run_commands(remove_testbed_commands, setup_log_file, console_log=log_console)
        print("Testbed ready.")

        # Get prediction
        prediction = get_item_by_field(predictions, KEY_INSTANCE_ID, instance_id)
        has_prediction = prediction is not None
        model_patch = prediction["model_patch"] if has_prediction else None
        # Create model patch file
        model_patch_path = (
            create_model_patch_file(instance_id, model_patch) if has_prediction and apply_model_patch else None
        )

        # Warning if no prediction found
        if not has_prediction and apply_model_patch:
            print(
                f"WARNING: No prediction found for {instance_id}. Evaluation will run without applying a model patch."
            )
        # Create test patch file
        test_patch_path = create_test_patch_file(instance_id, instance["test_patch"]) if use_test_patch_file else None

        # Get test spec
        test_spec = test_spec_creator.make_test_spec(
            instance,
            test_patch_path=test_patch_path,
            model_patch_path=model_patch_path,
        )

        # Run env setup scripts
        print("\n==== Env Scripts START ====\n")
        env_commands = list(test_spec.env_script_list)
        env_commands.append('echo "Env setup complete"')
        # print_list_with_indexes(env_commands)
        start_ms = current_ms()
        if not use_venv_repos:
            run_commands(
                env_commands,
                setup_log_file,
                console_log=log_console,
                log_commands=log_commands,
            )
        t = seconds_since(start_ms)
        run_stats["env_scripts_time"] = t
        print(f"\n==== Env Scripts COMPLETE {t} ====\n")

        # Run repo setup scripts
        print("\n==== Repo Scripts START ====\n")
        repo_commands = list(test_spec.repo_script_list)
        repo_commands.append('echo "Repo setup complete"')
        # print_list_with_indexes(repo_commands)
        start_ms = current_ms()
        run_commands(
            repo_commands,
            setup_log_file,
            console_log=log_console,
            log_commands=log_commands,
        )
        t = seconds_since(start_ms)
        run_stats["repo_scripts_time"] = t
        print(f"\n==== Repo Scripts COMPLETE {t} ====\n")

        # Run eval scripts
        print("\n==== Eval Scripts START ====\n")
        if not run_evaluation:
            print(f"Skipping evaluation. run_evaluation={run_evaluation}")
        else:
            eval_commands = list(test_spec.eval_script_list)
            eval_commands.append('echo "Eval complete"')
            eval_commands = echo_command_start_and_finish(eval_commands)
            # print_list_with_indexes(eval_commands)
            start_ms = current_ms()
            run_commands(
                eval_commands,
                log_file,
                console_log=log_console,
                log_commands=log_commands,
            )
            t = seconds_since(start_ms)
            run_stats["eval_scripts_time"] = t
            print(f"Closing log file {log_file_path}")
            log_file.close()
            setup_log_file.close()
            print(f"\n==== Eval Scripts COMPLETE  {t} ====\n")

            # Remove hidden characters from logs, the break parsing of the grader
            strip_hidden_ascii_from_file(log_file_path)

            # Eval report
            print(f"\n=== REPORT '{instance_id}'===")
            eval_report = get_eval_report(
                test_spec,
                prediction,
                log_file_path,
                log_file_path,
                True,
            )
            report = eval_report[instance_id]
            report_tests_status = report.get("tests_status", {
                FAIL_TO_PASS: {"success": [], "failure": ["ERROR: Test status missing in report"]},
                PASS_TO_PASS: {"success": [], "failure": ["ERROR: Test status missing in report"]},
            })

            run_stats = {
                "resolution_status": get_resolution_status(report_tests_status),
                "f2p_success": len(report_tests_status[FAIL_TO_PASS]["success"]),
                "f2p_failure": len(report_tests_status[FAIL_TO_PASS]["failure"]),
                "p2p_success": len(report_tests_status[PASS_TO_PASS]["success"]),
                "p2p_failure": len(report_tests_status[PASS_TO_PASS]["failure"]),
                "run_time": seconds_since(start_instance_ms),
            } | run_stats
            print(jsons(run_stats))
            report_map[instance_id] = report
            run_stats_map[instance_id] = run_stats
            file_write(
                f"{env_handler.output_dir}/reports/{instance_id}/report_{instance_id}_{run_start_ms}.txt",
                jsons(report),
            )
            file_write(
                f"{env_handler.output_dir}/reports/{instance_id}/summary_{instance_id}_{run_start_ms}.txt",
                jsons(run_stats),
            )
        print(f"\n==== INSTANCE '{instance_id}' COMPLETE ====")

    file_write(
        f"{env_handler.output_dir}/reports/{run_start_ms}/report_{run_start_ms}.txt",
        jsons(report_map),
    )
    file_write(
        f"{env_handler.output_dir}/reports/{run_start_ms}/summary_{run_start_ms}.txt",
        jsons(run_stats_map),
    )
    instance_count = len(instances)
    print(f"==== RUN STATS {run_start_ms} ====")
    print(jsons(run_stats_map))
    print(f"instances = {instance_count}")
    print(f"apply_model_patch = {apply_model_patch}")
    print(f"total time = {seconds_since(run_start_ms)}")
    stats_list = list(run_stats_map.values())
    for rs in ResolvedStatus:
        status = rs.value
        status_instances = filter_by_key(stats_list, "resolution_status", [status])
        print(
            f"{status}({len(status_instances)} of {instance_count}) = {get_key_values(status_instances, KEY_INSTANCE_ID)}"
        )
    print(f"==== RUN {run_start_ms} COMPLETE ====")


def remove_local_pip_conf():
    """
    Remove local pip configuration
    :return:
    """
    pip_conf = Path("/root/.config/pip/pip.conf")
    if pip_conf.exists():
        pip_conf.unlink()
        print("Removed local pip.conf")

def build_instances_venv(
    instances: list[dict],
    env_handler: KprizeEnvHandler,
    data_path_handler: DataPathHandler,
    output_repo_dir: Path,
    log_commands=True,
    log_console=True,
    pip_env_manager_type=PipEnvManagerType.VENV,
    disable_apt_install=False,
):
    run_start_ms = current_ms()
    print(f"==== RUN {run_start_ms} ====")
    print(f"instances = {len(instances)}")

    KPRIZE_CONSTANTS.use_kprize_configs = True
    KPRIZE_CONSTANTS.latest_config_path = data_path_handler.repo_config_dir

    pip_env_manager = PipEnvManager(
        manager=pip_env_manager_type,
        python_version=KAGGLE_EVAL_PYTHON_VERSION,
    )
    test_spec_creator = TestSpecCreator(
        pip_env_manager=pip_env_manager,
        instance_repos_dir=None,
        local_repos_dir=data_path_handler.git_repo_dir,
        repo_config_dir=data_path_handler.repo_config_dir,
        disable_apt_install=disable_apt_install,
        reset_tests_after_eval=False,
        include_install_in_repo_setup=True,
        testbed_dir=str(env_handler.get_test_bed_path()),
        activate_only_in_eval=False,
    )

    for instance_index, instance in enumerate(instances):
        # Get instance data
        instance_id = instance[KEY_INSTANCE_ID]
        print(f"\n==== INSTANCE '{instance_id}' ({instance_index + 1} of {len(instances)}) ====")

        setup_log_file_path = f"{env_handler.output_dir}/logs/{instance_id}/setup_output.txt"
        setup_log_file = file_open(setup_log_file_path, "w")
        run_stats = {
            "instance_id": instance_id,
        }

        # Delete existing testbed
        print("Clearing testbed.")
        remove_testbed_commands = ([f"rm -rf {env_handler.get_test_bed_path()}"] +
                                   pip_env_manager.global_env_remove_cmds)
        run_commands(remove_testbed_commands, setup_log_file, console_log=log_console)
        print("Testbed ready.")

        # Get test spec
        test_spec = test_spec_creator.make_test_spec(
            instance,
            test_patch_path=None,
            model_patch_path=None,
        )

        # Run env setup scripts
        print("\n==== Env Scripts START ====\n")
        env_commands = list(test_spec.env_script_list)
        env_commands.append('echo "Env setup complete"')
        # print_list_with_indexes(env_commands)
        start_ms = current_ms()
        run_commands(
            env_commands,
            setup_log_file,
            console_log=log_console,
            log_commands=log_commands,
        )
        t = seconds_since(start_ms)
        run_stats["env_scripts_time"] = t
        print(f"\n==== Env Scripts COMPLETE {t} ====\n")

        # Run repo setup scripts
        print("\n==== Repo Scripts START ====\n")
        repo_commands = list(test_spec.repo_script_list)
        repo_commands.append('echo "Repo setup complete"')
        # print_list_with_indexes(repo_commands)
        start_ms = current_ms()
        run_commands(
            repo_commands,
            setup_log_file,
            console_log=log_console,
            log_commands=log_commands,
        )
        t = seconds_since(start_ms)
        run_stats["repo_scripts_time"] = t
        print(f"\n==== Repo Scripts COMPLETE {t} ====\n")

        # Close logs
        setup_log_file.close()

        # Export current repo
        print("Exporting current repo")
        output_instance_repo_dir = output_repo_dir / f"repo__{instance_id}"
        if output_instance_repo_dir.exists():
            print(f"Output repo already exists: {output_instance_repo_dir}. Removing...")
            shutil.rmtree(output_instance_repo_dir)
        shutil.copytree(
            env_handler.get_test_bed_path(),
            output_instance_repo_dir,
            ignore=shutil.ignore_patterns('.git')
        )
