from pathlib import Path

import docker

def container_stop_safe(container):
    """Stop a container (safely)"""
    try:
        container.stop()
        print(f"Container {container.id[:12]} stopped")
    except docker.errors.NotFound as e:
        print(f"Error stopping container. Container not found.")
    except Exception as e:
        print(f"Error stopping container. {type(e)} {e}")


def container_remove_safe(container):
    """Remove a container (safely)"""
    try:
        container.remove()
        print(f"Container {container.id[:12]} removed")
    except docker.errors.NotFound as e:
        print(f"Error removing container. Container not found.")
    except Exception as e:
        print(f"Error removing container. {type(e)} {e}")


def check_image_exists(image_tag):
    """
    Check if a Docker image exists locally.

    :param image_tag: Name of the image (e.g., 'my-image:latest')
    :return: True if image exists, False otherwise
    """
    client = docker.from_env()
    try:
        # Try to find the image locally
        client.images.get(image_tag)
        print(f"Image {image_tag} already exists.")
        return True
    except docker.errors.ImageNotFound:
        print(f"Image {image_tag} does not exist locally.")
        return False


def build_image_if_not_exists(dockerfile: str, tag: str, path: str ='.') -> any:
    """
    Build a Docker image only if it doesn't already exist.

    :param dockerfile: Dockerfile file name
    :param tag: Tag for the image
    :param path: Build context directory
    :return: Docker image object
    """
    client = docker.from_env()

    # Check if image exists
    try:
        existing_image = client.images.get(tag)
        print(f"Using existing image {tag}")
        return existing_image
    except docker.errors.ImageNotFound:
        # Build the image if it doesn't exist
        print(f"Image {tag} not found. Building...")
        image, build_logs = client.images.build(
            path=path,
            dockerfile=dockerfile,
            tag=tag,
            rm=True,
        )
        return image