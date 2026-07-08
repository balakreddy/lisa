# Copyright (c) Microsoft Corporation.
# Licensed under the MIT license.

"""
Fedora Cloud Validation Tests

This test suite validates Fedora cloud image configuration and
functionality. Tests cover OS identification, package management,
boot validation, service status, system logging, and user management.
"""

from logging import Logger
from typing import Any, Dict

from assertpy.assertpy import assert_that

from lisa import (
    Node,
    SkippedException,
    TestCaseMetadata,
    TestSuite,
    TestSuiteMetadata,
    simple_requirement,
)
from lisa.operating_system import Fedora
from lisa.tools import Cat


@TestSuiteMetadata(
    area="fedora",
    category="functional",
    description="""
    Fedora Cloud Image Validation Tests.

    Validates Fedora cloud image configuration across cloud platforms.
    Tests cover: OS identification, package management, boot validation,
    service status, system logging, and user management.
    """,
)
class FedoraCloudValidation(TestSuite):
    """
    Fedora cloud image validation tests.

    These tests validate that Fedora cloud images are properly configured
    and functional across different cloud platforms (Azure, AWS, etc.).
    """

    def before_case(self, log: Logger, **kwargs: Any) -> None:
        node = kwargs["node"]
        if type(node.os) is not Fedora:
            raise SkippedException(
                f"{node.os.information.full_version} is not supported; "
                "this suite runs on Fedora only (excluding subclasses)."
            )

    @TestCaseMetadata(
        description="""
        Verify Fedora edition self-identification.

        Validates /etc/os-release fields, fedora-release package version,
        and SUPPORT_END date.
        """,
        priority=1,
        requirement=simple_requirement(supported_os=[Fedora]),
    )
    def verify_fedora_edition_identification(self, node: Node) -> None:
        """
        Verify that the Fedora image correctly identifies itself.

        Reads /etc/os-release and checks:
        - ID is "fedora"
        - VERSION is present
        - CPE_NAME includes :fedora:<VERSION_ID>
        - Installed fedora-release RPM version matches VERSION_ID
        - SUPPORT_END date is still in the future
        - PRETTY_NAME field is present
        """
        cat = node.tools[Cat]

        # Source /etc/os-release and parse into a dict
        os_release_content = cat.read("/etc/os-release", force_run=True)

        fields: Dict[str, str] = {}
        for line in os_release_content.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                fields[key.strip()] = val.strip().strip('"')

        # ID must be 'fedora'
        assert_that(fields.get("ID", "").lower()).described_as(
            "/etc/os-release ID must be 'fedora'"
        ).is_equal_to("fedora")

        version_id = fields.get("VERSION_ID", "")
        assert_that(version_id).described_as(
            "/etc/os-release must have VERSION_ID"
        ).is_not_empty()

        # VERSION field must exist
        version = fields.get("VERSION", "")
        assert_that(version).described_as(
            "/etc/os-release must have VERSION"
        ).is_not_empty()

        # CPE_NAME must contain :fedora:<VERSION_ID>
        cpe = fields.get("CPE_NAME", "")
        assert_that(cpe).described_as(
            f"CPE_NAME must contain ':fedora:{version_id}'"
        ).contains(f":fedora:{version_id}")

        # Installed fedora-release-common RPM version must match VERSION_ID
        rpm_ver = node.execute("rpm -q --qf '%{VERSION}' fedora-release-common")
        assert_that(rpm_ver.exit_code).described_as(
            "fedora-release-common must be installed"
        ).is_equal_to(0)
        assert_that(rpm_ver.stdout.strip()).described_as(
            f"fedora-release-common version must match VERSION_ID ({version_id})"
        ).is_equal_to(version_id)

        # SUPPORT_END must be in the future
        support_end = fields.get("SUPPORT_END", "")
        if support_end:
            date_check = node.execute(
                f'[ "$(date +%s)" -lt "$(date -d "{support_end}" +%s)" ]',
                shell=True,
            )
            assert_that(date_check.exit_code).described_as(
                f"SUPPORT_END ({support_end}) must be in the future"
            ).is_equal_to(0)

        # PRETTY_NAME field must exist
        assert_that(fields.get("PRETTY_NAME", "")).described_as(
            "/etc/os-release must have PRETTY_NAME"
        ).is_not_empty()

        node.log.info(f"Fedora edition validated: VERSION_ID={version_id}")

    @TestCaseMetadata(
        description="""
        Verify no failed systemd services after boot.

        Checks that all systemd services started successfully by verifying
        systemctl reports zero failed units.
        """,
        priority=1,
        requirement=simple_requirement(supported_os=[Fedora]),
    )
    def verify_services_started(self, node: Node) -> None:
        """
        Validate no systemd services are in failed state.

        Verifies systemctl --all --failed reports zero loaded failed units.
        """
        # Check for failed services
        result = node.execute("systemctl is-system-running")
        state = result.stdout.strip()
        node.log.info(f"systemctl is-system-running:\n{state}")

        if result.exit_code > 0:
            failed_units_result = node.execute("systemctl --all --failed --no-pager")
            node.log.info(f"Failed units:\n{failed_units_result.stdout}")
            assert_that(state).described_as(
                f"System must be running (got {state}). "
                f"Failed: {failed_units_result.stdout}"
            ).is_equal_to("running")
