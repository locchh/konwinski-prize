from __future__ import annotations

import docker
import json
import resource
import traceback

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tqdm import tqdm

from swebench.harness.constants import (
    APPLY_PATCH_FAIL,
    APPLY_PATCH_PASS,
    INSTANCE_IMAGE_BUILD_DIR,
    KEY_INSTANCE_ID,
    RUN_EVALUATION_LOG_DIR,
)
from swebench.harness.docker_utils import (
    remove_image,
    copy_to_container,
    exec_run_with_timeout,
    cleanup_container,
    list_images,
    should_remove,
    clean_images,
)
from kprize.harness.docker_build import (
    BuildImageError,
    build_container,
    build_env_images,
    close_logger,
    setup_logger,
)
from kprize.harness.grading import get_eval_report
from kprize.harness.test_spec import make_test_spec, TestSpec
from kprize.harness.utils import load_swebench_dataset, str2bool
from kprize.harness.grading import get_logs_eval
from swebench.harness.run_evaluation import (
    get_gold_predictions,
    EvaluationError,
    get_dataset_from_preds,
)
from kprize.collection.kprize_global_state import KprizeGlobalState
from kprize.collection.validation.utils import update_unknown_instance_state
from kprize.collection.validation.failure_mode import FailureMode
from kprize.collection.validation.instance_validation_stats import InstanceValidationStats


def run_instance(
    test_spec: TestSpec,
    pred: dict,
    rm_image: bool,
    force_rebuild: bool,
    client: docker.DockerClient,
    run_id: str,
    timeout: int | None = None,
):
    """
    Run a single instance with the given prediction.
    Args:
        test_spec (TestSpec): TestSpec instance
        pred (dict): Prediction w/ model_name_or_path, model_patch, instance_id
        rm_image (bool): Whether to remove the image after running
        force_rebuild (bool): Whether to force rebuild the image
        client (docker.DockerClient): Docker client
        run_id (str): Run ID
        timeout (int): Timeout for running tests
    """
    # Initialize the kprize global state manager singleton.
    state = KprizeGlobalState()

    # Set up logging directory
    instance_id = test_spec.instance_id
    model_name_or_path = pred.get("model_name_or_path", "None").replace("/", "__")
    log_dir = RUN_EVALUATION_LOG_DIR / run_id / model_name_or_path / instance_id
    log_dir.mkdir(parents=True, exist_ok=True)

    # Link the image build dir in the log dir
    build_dir = INSTANCE_IMAGE_BUILD_DIR / test_spec.instance_image_key.replace(
        ":", "__"
    )
    image_build_link = log_dir / "image_build_dir"
    if not image_build_link.exists():
        try:
            # link the image build dir in the log dir
            image_build_link.symlink_to(build_dir.absolute(), target_is_directory=True)
        except:
            # some error, idk why
            pass
    log_file = log_dir / "run_instance.log"

    # Set up report file + logger
    report_path = log_dir / "report.json"
    if report_path.exists():
        return instance_id, json.loads(report_path.read_text())
    logger = setup_logger(instance_id, log_file)

    # Run the instance
    container = None
    try:
        if test_spec.version is None:
            raise EvaluationError(
                instance_id,
                "No version found for instance",
                logger,
            )
        # Build + start instance container (instance image should already be built)
        container = build_container(
            test_spec, client, run_id, logger, rm_image, force_rebuild
        )
        container.start()
        logger.info(f"Container for {instance_id} started: {container.id}")

        # Run eval script before patch, write output to logs
        eval_file = Path(log_dir / "eval.sh")
        eval_file.write_text(test_spec.eval_script)
        copy_to_container(container, eval_file, Path("/eval.sh"))
        test_output, timed_out, total_runtime = exec_run_with_timeout(
            container, "/bin/bash /eval.sh", timeout
        )
        test_output_before_patch_path = log_dir / "test_output_before_patch.txt"
        logger.info(f"Test runtime: {total_runtime:_.2f} seconds")
        with open(test_output_before_patch_path, "w") as f:
            f.write(test_output)
            logger.info(
                f"Test output before patch for {instance_id} written to {test_output_before_patch_path}"
            )
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                state.set(
                    test_spec.instance_id,
                    InstanceValidationStats(failure_mode=FailureMode.TIMEOUT),
                )
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # Copy model prediction as patch file to container
        patch_file = Path(log_dir / "patch.diff")
        patch_file.write_text(pred["model_patch"] or "")
        logger.info(
            f"Intermediate patch for {instance_id} written to {patch_file}, now applying to container..."
        )
        copy_to_container(container, patch_file, Path("/tmp/patch.diff"))

        # Attempt to apply patch to container
        val = container.exec_run(
            "git apply --allow-empty -v /tmp/patch.diff",
            workdir="/testbed",
            user="root",
        )
        if val.exit_code != 0:
            logger.info(f"Failed to apply patch to container, trying again...")

            # try "patch --batch --fuzz=5 -p1 -i {patch_path}" to try again
            val = container.exec_run(
                "patch --batch --fuzz=5 -p1 -i /tmp/patch.diff",
                workdir="/testbed",
                user="root",
            )
            if val.exit_code != 0:
                logger.info(f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}")
                state.set(
                    test_spec.instance_id,
                    InstanceValidationStats(failure_mode=FailureMode.APPLY_PATCH_FAILURE),
                )
                raise EvaluationError(
                    instance_id,
                    f"{APPLY_PATCH_FAIL}:\n{val.output.decode('utf-8')}",
                    logger,
                )
            else:
                logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")
        else:
            logger.info(f"{APPLY_PATCH_PASS}:\n{val.output.decode('utf-8')}")

        # Get git diff before running eval script
        git_diff_output_before = (
            container.exec_run("git diff", workdir="/testbed")
            .output.decode("utf-8")
            .strip()
        )
        logger.info(f"Git diff before:\n{git_diff_output_before}")

        # Run eval script, write output to logs
        test_output, timed_out, total_runtime = exec_run_with_timeout(
            container, "/bin/bash /eval.sh", timeout
        )
        test_output_path = log_dir / "test_output.txt"
        logger.info(f"Test runtime: {total_runtime:_.2f} seconds")
        with open(test_output_path, "w") as f:
            f.write(test_output)
            logger.info(f"Test output for {instance_id} written to {test_output_path}")
            if timed_out:
                f.write(f"\n\nTimeout error: {timeout} seconds exceeded.")
                state.set(
                    test_spec.instance_id,
                    InstanceValidationStats(failure_mode=FailureMode.TIMEOUT),
                )
                raise EvaluationError(
                    instance_id,
                    f"Test timed out after {timeout} seconds.",
                    logger,
                )

        # Get git diff after running eval script
        git_diff_output_after = (
            container.exec_run("git diff", workdir="/testbed")
            .output.decode("utf-8")
            .strip()
        )

        # Check if git diff changed after running eval script
        logger.info(f"Git diff after:\n{git_diff_output_after}")
        if git_diff_output_after != git_diff_output_before:
            logger.info(f"Git diff changed after running eval script")

        report_map = {
            "instance_id": test_spec.instance_id,
            "FAIL_TO_PASS": [],
            "PASS_TO_PASS": [],
            "FAIL_TO_FAIL": [],
            "PASS_TO_FAIL": [],
        }

        eval_sm, found = get_logs_eval(log_file, test_output_path)
        eval_sm_ref, found_ref = get_logs_eval(log_file, test_output_before_patch_path)
        if not found:
            raise EvaluationError(
                instance_id,
                "No evaluation logs found",
                logger,
            )
        if not found_ref:
            raise EvaluationError(
                instance_id,
                "No reference evaluation logs found",
                logger,
            )
        for test, status in eval_sm.items():
            if status == "PASSED" and eval_sm_ref.get(test, None) == "FAILED":
                report_map["FAIL_TO_PASS"].append(test)
            elif status == "PASSED" and eval_sm_ref.get(test, None) == "PASSED":
                report_map["PASS_TO_PASS"].append(test)
            elif status == "FAILED" and eval_sm_ref.get(test, None) == "FAILED":
                report_map["FAIL_TO_FAIL"].append(test)
            elif status == "FAILED" and eval_sm_ref.get(test, None) == "PASSED":
                report_map["PASS_TO_FAIL"].append(test)

        return report_map
    except EvaluationError as e:
        update_unknown_instance_state(
            test_spec.instance_id, FailureMode.RUN_INSTANCE_FAILURE, state
        )
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except BuildImageError as e:
        update_unknown_instance_state(
            test_spec.instance_id, FailureMode.BUILD_IMAGE_FAILURE, state
        )
        error_msg = traceback.format_exc()
        logger.info(error_msg)
        print(e)
    except Exception as e:
        update_unknown_instance_state(
            test_spec.instance_id, FailureMode.RUN_INSTANCE_FAILURE, state
        )
        error_msg = (
            f"Error in evaluating model for {instance_id}: {e}\n"
            f"{traceback.format_exc()}\n"
            f"Check ({logger.log_file}) for more information."
        )
        logger.error(error_msg)
        print(e)
    finally:
        # Remove instance container + image, close logger
        cleanup_container(client, container, logger)
        if rm_image:
            remove_image(client, test_spec.instance_image_key, logger)
        close_logger(logger)
    return


def run_instances(
    predictions: dict,
    instances: list,
    cache_level: str,
    clean: bool,
    force_rebuild: bool,
    max_workers: int,
    run_id: str,
    timeout: int,
):
    """
    Run all instances for the given predictions in parallel.
    Args:
        predictions (dict): Predictions dict generated by the model
        instances (list): List of instances
        cache_level (str): Cache level
        clean (bool): Clean images above cache level
        force_rebuild (bool): Force rebuild images
        max_workers (int): Maximum number of workers
        run_id (str): Run ID
        timeout (int): Timeout for running tests
    """
    client = docker.from_env()
    test_specs = list(map(make_test_spec, instances))
    test_specs = [test_spec for test_spec in test_specs if test_spec is not None]

    # print number of existing instance images
    instance_image_ids = {x.instance_image_key for x in test_specs}
    existing_images = {
        tag for image in client.images.list(all=True) for tag in image.tags
    }
    reusable_images = instance_image_ids.intersection(existing_images)
    if not force_rebuild and reusable_images:
        print(
            f"Found {len(existing_images)} existing instance images. Will reuse them."
        )

    # run instances in parallel
    print(f"Running {len(instances)} instances...")
    with tqdm(total=len(instances), smoothing=0, desc="Running instances") as pbar:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Create a future for running each instance
            futures = {
                executor.submit(
                    run_instance,
                    test_spec,
                    predictions[test_spec.instance_id],
                    should_remove(
                        test_spec.instance_image_key,
                        cache_level,
                        clean,
                        reusable_images,
                    ),
                    force_rebuild,
                    client,
                    run_id,
                    timeout,
                ): None
                for test_spec in test_specs
            }
            results = {}
            # Wait for each future to complete
            for future in as_completed(futures):
                pbar.update(1)
                try:
                    # Update progress bar, check if instance ran successfully
                    res = future.result()
                    if res:
                        instance_id = res["instance_id"]
                        del res["instance_id"]
                        results[instance_id] = res
                except Exception as e:
                    traceback.print_exc()
                    continue
    print("All instances run.")
    return results


def main(
    dataset_name: str,
    split: str,
    instance_ids: list,
    max_workers: int,
    force_rebuild: bool,
    cache_level: str,
    clean: bool,
    open_file_limit: int,
    run_id: str,
    timeout: int,
):
    """
    Run evaluation harness for the given dataset and predictions.
    """
    # set open file limit
    assert len(run_id) > 0, "Run ID must be provided"
    resource.setrlimit(resource.RLIMIT_NOFILE, (open_file_limit, open_file_limit))
    client = docker.from_env()

    predictions = get_gold_predictions(dataset_name, split)

    # Initialize the failure mode for each instance.
    instance_ids = [pred["instance_id"] for pred in predictions]
    state = KprizeGlobalState()
    state.set("instance_ids", instance_ids)
    state.set(instance_ids, InstanceValidationStats(failure_mode=FailureMode.UNKNOWN))

    predictions = {pred[KEY_INSTANCE_ID]: pred for pred in predictions}

    # get dataset from predictions
    dataset = get_dataset_from_preds(
        dataset_name, split, instance_ids, predictions, run_id
    )
    for instance in dataset:
        instance["FAIL_TO_PASS"] = []
        instance["PASS_TO_PASS"] = []
    existing_images = list_images(client)
    print(f"Running {len(dataset)} unevaluated instances...")
    if not dataset:
        print("No instances to run.")
    else:
        # build environment images + run instances
        build_env_images(client, dataset, force_rebuild, max_workers)
        results = run_instances(
            predictions,
            dataset,
            cache_level,
            clean,
            force_rebuild,
            max_workers,
            run_id,
            timeout,
        )

    # clean images + make final report
    clean_images(client, existing_images, cache_level, clean)

    # open dataset_name and add the results fields to it
    with open(dataset_name, "r") as f:
        data = [
            json.loads(task)
            for task in Path(dataset_name).read_text().strip().split("\n")
        ]
        if len(data) == 1 and isinstance(data[0], list):
            data = data[0]
        if isinstance(data[0], str):
            data = [eval(instance) for instance in data]
        for instance in data:
            instance_id = instance["instance_id"]

            if instance_id in results:
                # merge two dictionaries, crash on duplicate keys
                if any(k in instance for k in results[instance_id]):
                    state.set(
                        instance_id,
                        InstanceValidationStats(
                            failure_mode=FailureMode.DUPLICATE_INSTANCE
                        ),
                    )
                    raise ValueError(f"Duplicate keys in {instance_id}")
                instance.update(results[instance_id])

    last_dot_idx = dataset_name.rfind(".")
    dataset_name_w_results_all = (
        dataset_name[:last_dot_idx] + "_validated.all" + dataset_name[last_dot_idx:]
    )
    dataset_name_w_results = (
        dataset_name[:last_dot_idx] + "_validated" + dataset_name[last_dot_idx:]
    )
    with open(dataset_name_w_results, "w") as f, open(
        dataset_name_w_results_all, "w"
    ) as f_all:
        for instance in data:
            print(json.dumps(instance), file=f_all)
            if len(instance.get("FAIL_TO_PASS", [])) > 0:
                print(json.dumps(instance), file=f)

    return data


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "--dataset_name",
        default="princeton-nlp/SWE-bench_Lite",
        type=str,
        help="Name of dataset or path to JSON file.",
    )
    parser.add_argument(
        "--split", type=str, default="test", help="Split of the dataset"
    )
    parser.add_argument(
        "--instance_ids",
        nargs="+",
        type=str,
        help="Instance IDs to run (space separated)",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=4,
        help="Maximum number of workers (should be <= 75%% of CPU cores)",
    )
    parser.add_argument(
        "--open_file_limit", type=int, default=4096, help="Open file limit"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1_800,
        help="Timeout (in seconds) for running tests for each instance",
    )
    parser.add_argument(
        "--force_rebuild",
        type=str2bool,
        default=False,
        help="Force rebuild of all images",
    )
    parser.add_argument(
        "--cache_level",
        type=str,
        choices=["none", "base", "env", "instance"],
        help="Cache level - remove images above this level",
        default="env",
    )
    # if clean is true then we remove all images that are above the cache level
    # if clean is false, we only remove images above the cache level if they don't already exist
    parser.add_argument(
        "--clean", type=str2bool, default=False, help="Clean images above cache level"
    )
    parser.add_argument(
        "--run_id", type=str, required=True, help="Run ID - identifies the run"
    )
    args = parser.parse_args()

    main(**vars(args))
