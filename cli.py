import argparse
import ghlib
import asanalib
import os
import sys
import json
import util
from sync import Sync, DIRECTION_G2A
import logging
import server
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


def serve(args):
    if not args.gh_url or not args.asana_url:
        fail("Both GitHub and ASANA URL have to be specified!")

    if not args.gh_token:
        fail("No GitHub token specified!")

    if not args.asana_token:
        fail("No asana credentials specified!")

    if not args.asana_project:
        fail("No asana project specified!")

    github = ghlib.GitHub(args.gh_url, args.gh_token)
    asana = asanalib.Asana(args.asana_url, args.asana_token)
    s = Sync(
        github,
        asana.getProject(args.asana_project),
        direction=direction_str_to_num(args.direction),
    )
    server.run_server(s, args.secret, port=args.port)


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
        args.issue_end_state,
        args.issue_reopen_state,
    )
    repo_id = args.gh_org + "/" + args.gh_repo

    if args.state_file:
        if args.state_issue:
            fail("--state-file and --state-issue are mutually exclusive!")

        state = util.state_from_file(args.state_file)
    elif args.state_issue:
        state = asana_project.fetch_repo_state(repo_id, args.state_issue)
    else:
        state = {}

    s = Sync(github, asana_project, direction=direction_str_to_num(args.direction))
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
        help="GitHub API token. Alternatively, the GH2JIRA_GH_TOKEN may be set.",
        default=os.getenv("GH2JIRA_GH_TOKEN"),
    )
    credential_base.add_argument("--asana-url", help="URL of JIRA instance")
    credential_base.add_argument(
        "--asana-token",
        help="JIRA password. Alternatively, the GH2JIRA_JIRA_TOKEN may be set.",
        default=os.getenv("GH2JIRA_JIRA_TOKEN"),
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

    issue_state_base = argparse.ArgumentParser(add_help=False)
    issue_state_base.add_argument(
        "--issue-end-state",
        help="Custom end state (e.g. Closed) Done by default",
        default="Done",
    )
    issue_state_base.add_argument(
        "--issue-reopen-state",
        help="Custom reopen state (e.g. In Progress) To Do by default",
        default="To Do",
    )

    parser = argparse.ArgumentParser(prog="gh2asana")
    subparsers = parser.add_subparsers()

    # serve
    serve_parser = subparsers.add_parser(
        "serve",
        parents=[credential_base, direction_base, issue_state_base],
        help="Spawn a webserver which keeps GitHub alerts and JIRA tickets in sync",
        description="Spawn a webserver which keeps GitHub alerts and JIRA tickets in sync",
    )
    serve_parser.add_argument(
        "--port", help="The port the server will listen on", default=5000
    )
    serve_parser.set_defaults(func=serve)

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        parents=[credential_base, direction_base, issue_state_base],
        help="Synchronize GitHub alerts and JIRA tickets for a given repository",
        description="Synchronize GitHub alerts and JIRA tickets for a given repository",
    )
    sync_parser.add_argument(
        "--state-file",
        help="File holding the current states of all alerts. The program will create the"
        + " file if it doesn't exist and update it after each run.",
        default=None,
    )
    sync_parser.add_argument(
        "--state-issue",
        help="The key of the issue holding the current states of all alerts. The program "
        + 'will create the issue if "-" is given as the argument. The issue will be '
        + "updated after each run.",
        default=None,
    )
    

    def print_usage(args):
        print(parser.format_usage())

    parser.set_defaults(func=print_usage)
    args = parser.parse_args()

    # run the given action
    args.func(args)


main()