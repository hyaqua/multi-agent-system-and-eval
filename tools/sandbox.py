from __future__ import annotations

import logging
import tarfile
import io
import shlex

import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from config import DockerConfig

logger = logging.getLogger(__name__)


def _shell_quote(s: str) -> str:
    return shlex.quote(s)


class SandboxManager:
    def __init__(self, config: DockerConfig):
        self.config = config
        self.client = docker.from_env()
        self._ensure_image()

    def _ensure_image(self):
        try:
            self.client.images.get(self.config.image)
            logger.info(f"Sandbox image '{self.config.image}' found.")
        except ImageNotFound:
            logger.info(f"Building sandbox image '{self.config.image}'...")
            self._build_image()

    def _build_image(self):
        dockerfile = """\
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc g++ && \\
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pygame pytest pylint radon flake8

WORKDIR /workspace

# Non-root user for safety
RUN useradd -m -s /bin/bash coder
USER coder
"""
        # Build from string via tarball
        f = io.BytesIO()
        tar = tarfile.open(fileobj=f, mode="w")
        dockerfile_bytes = dockerfile.encode("utf-8")
        info = tarfile.TarInfo(name="Dockerfile")
        info.size = len(dockerfile_bytes)
        tar.addfile(info, io.BytesIO(dockerfile_bytes))
        tar.close()
        f.seek(0)

        self.client.images.build(
            fileobj=f,
            custom_context=True,
            tag=self.config.image,
            rm=True,
        )
        logger.info("Sandbox image built successfully.")

    def create_container(self) -> str:
        container = self.client.containers.run(
            image=self.config.image,
            command="sleep infinity",
            detach=True,
            mem_limit=self.config.memory_limit,
            nano_cpus=self.config.cpu_count * 1_000_000_000,
            network_disabled=self.config.network_disabled,
            working_dir="/workspace",
            # Safety: read-only root filesystem with writable workspace
            tmpfs={"/tmp": "size=64M"},
        )
        logger.info(f"Container created: {container.id[:12]}")
        return container.id

    def exec_command(
        self,
        container_id: str,
        command: str,
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        timeout = timeout or self.config.timeout_seconds
        container = self.client.containers.get(container_id)

        # Wrap the command in `timeout` so it can't hang forever.
        # Exit code 124 means the timeout was hit.
        wrapped_command = f"timeout {timeout} bash -c {_shell_quote(command)}"

        try:
            result = container.exec_run(
                cmd=["bash", "-c", wrapped_command],
                workdir="/workspace",
                demux=True,
            )

            stdout = result.output[0].decode("utf-8", errors="replace") if result.output[0] else ""
            stderr = result.output[1].decode("utf-8", errors="replace") if result.output[1] else ""

            # Truncate very long outputs
            max_len = 5000
            if len(stdout) > max_len:
                stdout = stdout[:max_len] + "\n... (truncated)"
            if len(stderr) > max_len:
                stderr = stderr[:max_len] + "\n... (truncated)"

            return result.exit_code, stdout, stderr

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return 1, "", str(e)

    @staticmethod
    def is_timeout_exit(exit_code: int) -> bool:
        return exit_code == 124

    def write_file(self, container_id: str, filepath: str, content: str):
        # Use tar to put a file into the container
        container = self.client.containers.get(container_id)

        f = io.BytesIO()
        tar = tarfile.open(fileobj=f, mode="w")
        data = content.encode("utf-8")
        info = tarfile.TarInfo(name=filepath)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        tar.close()
        f.seek(0)

        container.put_archive("/workspace", f)

    def read_file(self, container_id: str, filepath: str) -> str | None:
        container = self.client.containers.get(container_id)
        try:
            bits, _ = container.get_archive(f"/workspace/{filepath}")
            f = io.BytesIO()
            for chunk in bits:
                f.write(chunk)
            f.seek(0)
            tar = tarfile.open(fileobj=f)
            member = tar.getmembers()[0]
            extracted = tar.extractfile(member)
            if extracted:
                return extracted.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def list_files(self, container_id: str, path: str = ".") -> str:
        exit_code, stdout, _ = self.exec_command(
            container_id, f"find {path} -type f | head -100"
        )
        return stdout if exit_code == 0 else ""

    def destroy_container(self, container_id: str):
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove(force=True)
            logger.info(f"Container destroyed: {container_id[:12]}")
        except Exception as e:
            logger.warning(f"Failed to destroy container: {e}")
