import argparse
import ghlib
import asanalib
import os
import sys
import json
import util
from sync import Sync, DIRECTION_G2A
import logging
import anticrlf

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(anticrlf.LogFormatter("%(levelname)s:%(name)s:%(message)s"))
handler.setLevel(logging.DEBUG)
root.addHandler(handler)


def fail(msg):
    print(msg)
    sys.exit(1)


def direction_str_to_num(dstr):
    if dstr == "gh2asana":
        return DIRECTION_G2A
    else:
        fail('Unknown direction argument "{direction}"!'.format(direction=dstr))

def sync(args):
    if not args.gh_url or not args.asana_url:
        fail("Both GitHub and ASANA URL have to be specified!")

    if not args.gh_token:
        fail("No GitHub credentials specified!")

    if not args.asana_token:
        fail("No ASANA credentials specified!")

    if not args.asana_project:
        fail("No ASANA project specified!")
    
    if not args.asana_workspace:
        fail("No ASANA workspace specified!")

    if not args.gh_org:
        fail("No GitHub organization specified!")

    if not args.gh_repo:
        fail("No GitHub repository specified!")

    github = ghlib.GitHub(args.gh_url, args.gh_token)
    asana = asanalib.Asana(args.asana_url, args.asana_token)
    asana_project = asana.getProject(
        args.asana_project,
        args.asana_workspace,
    )
    repo_id = args.gh_org + "/" + args.gh_repo
    
    state = {}

    s = Sync(github, asana_project, asana_workspace, direction=direction_str_to_num(args.direction))
    s.sync_repo(repo_id, states=state)

    if args.state_file:
        util.state_to_file(args.state_file, state)
    elif args.state_issue:
        asana_project.save_repo_state(repo_id, state, args.state_issue)



def main():
    credential_base = argparse.ArgumentParser(add_help=False)
    credential_base.add_argument("--gh-org", help="GitHub organization")
    credential_base.add_argument("--gh-repo", help="GitHub repository")
    credential_base.add_argument(
        "--gh-url",
        help="API URL of GitHub instance",
    )
    credential_base.add_argument(
        "--gh-token",
        help="GitHub API token. Alternatively, the GH2ASANA_GH_TOKEN may be set.",
        default=os.getenv("GH2ASANA_GH_TOKEN"),
    )
    credential_base.add_argument("--asana-url", help="URL of ASANA instance")
    credential_base.add_argument(
        "--asana-token",
        help="ASANA password. Alternatively, the GH2ASANA_ASANA_TOKEN may be set."
    )
    credential_base.add_argument("--asana-project", help="Asana project key")

    credential_base.add_argument("--asana-workspace", help="Asana workspace")

    direction_base = argparse.ArgumentParser(add_help=False)
    direction_base.add_argument(
        "--direction",
        help='Sync direction. Possible values are "gh2asana" (alert states have higher priority than issue states),'
        + '"asana2gh" (issue states have higher priority than alert states) and "both" (adjust in both directions)',
        default="both",
    )

    parser = argparse.ArgumentParser(prog="gh2asana")
    subparsers = parser.add_subparsers()

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        parents=[credential_base, direction_base],
        help="Synchronize GitHub alerts and ASANA tickets for a given repository",
        description="Synchronize GitHub alerts and ASANA tickets for a given repository",
    )

    def print_usage(args):
        print(parser.format_usage())

    parser.set_defaults(func=print_usage)
    print("HIThere")
    args = parser.parse_args()

    # run the given action
    args.func(args)

main()