#!/usr/bin/env python3
# project template
# Copyright(C) 2021 Red Hat, Inc.
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""This is the main script of the template project."""

from template.version import __version__
import logging
import sys
from datetime import date
from datetime import datetime
from typing import Dict
from typing import Any
from typing import List
from typing import Optional
from urllib.parse import urlparse

import requests
import click
import yaml
from thoth.common import init_logging
from thoth.common import __version__ as thoth_common_version
from thoth.storages import SolverResultsStore
from thoth.storages import __version__ as thoth_storages_version

init_logging()
_LOGGER = logging.getLogger("thoth.solver_project_url")
_DATE_FORMAT = "%Y-%m-%d"

__component_version__ = f"{__version__}+" f"storages.{thoth_storages_version}.common.{thoth_common_version}"


def check_url_candidates(url_candidates: List, name: str) -> Dict[str, Any]:
    """Check URL candidates for any which match GitHub or GitLab."""
    git_source_repos = {}
    possible_urls = []
    for url in url_candidates:
        if not url:
            _LOGGER.warning(
                "Skipping URL as it is not recognized as a GitHub/GitLab repository: %r",
                url,
            )
            continue
        url_netloc = urlparse(url).netloc
        if not url_netloc.startswith("github.com") and not url_netloc.startswith("gitlab.com"):
            _LOGGER.warning(
                "Skipping URL as it is not recognized as a GitHub/GitLab repository: %r",
                url,
            )
            continue
        _LOGGER.debug("Processing URL: %r", url)
        url_path_parts = urlparse(url).path.split("/")[1:]
        if len(url_path_parts) < 2:
            _LOGGER.warning("Skipping URL as GitHub/GitLab repository and organization cannot be parsed: %r", url)
            continue

        org, repo = url_path_parts[:2]
        url_scheme = urlparse(url).scheme
        source_url = f"{url_scheme}://{url_netloc}/{org}/{repo}"
        try:
            response = requests.head(source_url)
            if response.status_code == 200:
                possible_urls.append(source_url)
            else:
                _LOGGER.debug("%r is an invalid Github/GitLab URL", source_url)
        except Exception:
            _LOGGER.exception("Failed to obtain %r with requests.head()", source_url)

    git_source_repos[name] = possible_urls
    return git_source_repos


def get_source_repos(*, start_date: Optional[date], end_date: Optional[date]) -> Dict[str, Any]:
    """Get source URLs of github repos."""
    store = SolverResultsStore()
    store.connect()
    for document_id, doc in store.iterate_results(start_date=start_date, end_date=end_date, include_end_date=True):
        if not doc["result"]["tree"]:
            continue
        _LOGGER.debug("Processing solver document %r", document_id)

        metadata = doc["result"]["tree"][0]["importlib_metadata"]["metadata"]
        name = metadata.get("Name")
        if not name:
            continue
        url_candidates = []
        for url in metadata.get("Project-URL") or []:
            url_candidates.append(url.rsplit(",", maxsplit=1)[-1].strip())
        url_candidates.append(metadata.get("Home-page"))
        git_source_repos = check_url_candidates(url_candidates, name)
    return git_source_repos  # dictionary


def _print_version(ctx: click.Context, _, value: str):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return

    click.echo(__component_version__)
    ctx.exit()


@click.command()
@click.pass_context
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    envvar="THOTH_SOLVER_PROJECT_URL_DEBUG",
    help="Be verbose about what's going on.",
)
@click.option(
    "--version",
    is_flag=True,
    is_eager=True,
    callback=_print_version,
    expose_value=False,
    help="Print version and exit.",
)
@click.option(
    "--start-date",
    envvar="THOTH_GET_SOURCE_REPOS_START_DATE",
    help="Use solver results starting the given date.",
    metavar="YYYY-MM-DD",
    type=str,
)
@click.option(
    "--end-date",
    help="Upper bound for solver results listing.",
    metavar="YYYY-MM-DD",
    envvar="THOTH_GET_SOURCE_REPOS_END_DATE",
    type=str,
)
@click.option(
    "--output",
    help="Store result to a file or print to stdout (-).",
    metavar="FILE",
    envvar="THOTH_GET_SOURCE_REPOS_OUTPUT",
    type=str,
)
def cli(
    _: click.Context,
    verbose: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    output: Optional[str] = None,
):
    """Aggregate Github URLs for GitHub hosted projects on PyPI."""
    if verbose:
        _LOGGER.setLevel(logging.DEBUG)

    _LOGGER.debug("Debug mode is on")
    _LOGGER.info("Version: %s", __component_version__)

    start_date_converted = None
    if start_date:
        start_date_converted = datetime.strptime(start_date, _DATE_FORMAT).date()

    end_date_converted = None
    if end_date:
        end_date_converted = datetime.strptime(end_date, _DATE_FORMAT).date()

    urls = get_source_repos(start_date=start_date_converted, end_date=end_date_converted)

    if output == "-" or not output:
        yaml.safe_dump(urls, sys.stdout)
    else:
        _LOGGER.info("Writing results computed to %r", output)
        with open(output, "w") as f:
            yaml.safe_dump(urls, f)


__name__ == "__main__" and cli()
