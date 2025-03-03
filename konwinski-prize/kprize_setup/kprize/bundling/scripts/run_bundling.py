import argparse
from pathlib import Path
from kprize.bundling.kprize_bundler import KPrizeBundler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--instances-dir",
        help="Directory of task instance datasets",
        type=str,
        default=Path("task_instances/").absolute(),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        help="Directory to output collected dependencies",
        type=str,
        default=Path("dependencies/").absolute(),
    )
    parser.add_argument(
        "--conda-index",
        help="Force run conda index in docker container",
        action='store_true',
    )
    parser.add_argument(
        "-l",
        "--force-online",
        help="Force online dep usage (pip, conda) env setup in docker",
        type=bool,
        default=True,
    )
    parser.add_argument(
        "-u",
        "--upload-to-kaggle",
        help="Upload kaggle dataset",
        action='store_true',
    )
    parser.add_argument(
        "--skip-docker",
        "--skip-docker-run-instances",
        help="Skip running instances setup in docker",
        action='store_true',
    )
    parser.add_argument(
        "--skip-dataset",
        "--skip-kaggle-dataset-creation",
        help="Skip creating kaggle dataset",
        action='store_true',
    )
    parser.add_argument(
        "--skip-parsing",
        "--skip-docker-log-parsing",
        help="Skip parsing docker logs for package dependencies",
        action='store_true',
    )
    parser.add_argument(
        "-c",
        "--clear-instance",
        help="Clear previous instance run data to re-run instance in docker",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-d",
        "--dataset-id",
        help="Kaggle dataset ID in format username/dataset-name",
        type=str,
        default="justinfiedler123/kprize-assets",
    )
    parser.add_argument(
        "-z",
        "--skip-dataset-compression",
        help="Skip compressing dataset",
        action='store_true',
    )
    parser.add_argument(
        "--venv",
        help="Create venv repos",
        action='store_true',
    )
    parser.add_argument(
        "--splits",
        help="The split to use for the dataset. Default is all",
        nargs='*',
        type=str,
        default=None,
    )
    parser.add_argument(
        "--force-docker-copy",
        help="Force copy of kprize assets to docker",
        action='store_true',
    )
    args = parser.parse_args()

    bundler = KPrizeBundler(
        instances_dir=args.instances_dir,
        output_dir=args.output_dir,
        bundle_compress=not args.skip_dataset_compression,
        create_venv_repos=args.venv,
        split_filter=args.splits,
    )
    bundler.run_dependency_collection(
        force_online=args.force_online,
        conda_index=args.conda_index,
        upload_to_kaggle=args.upload_to_kaggle,
        skip_run_in_docker=args.skip_docker,
        skip_dataset_creation=args.skip_dataset,
        skip_docker_log_parsing=args.skip_parsing,
        clear_instance_id=args.clear_instance,
        dataset_id=args.dataset_id,
        force_copy_assets_to_docker=args.force_docker_copy,
    )
