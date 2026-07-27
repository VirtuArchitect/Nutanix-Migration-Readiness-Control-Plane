import unittest
from pathlib import Path


class DockerPublishWorkflowTests(unittest.TestCase):
    def test_docker_publish_workflow_builds_smokes_and_pushes_ghcr_image(self):
        workflow = Path(".github/workflows/docker-publish.yml").read_text(encoding="utf-8")

        for expected in (
            "name: Publish Docker image",
            "packages: write",
            "actions/checkout@v5",
            "ghcr.io/${GITHUB_REPOSITORY_OWNER}/nutanix-migration-readiness-control-plane",
            "docker login ghcr.io",
            "docker build",
            "docker run --rm -d --name nmrcp-publish-smoke",
            "/healthz",
            "product_version",
            "docker push",
        ):
            self.assertIn(expected, workflow)


if __name__ == "__main__":
    unittest.main()
