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


def serve(args):
    if not args.gh_url or not args.asana_url:
        fail("Both GitHub and ASANA URL have to be specified!")

    if not args.gh_token:
        fail("No GitHub token specified!")

    if not args.asana_token:
        fail("No ASANA credentials specified!")

    if not args.asana_project:
        fail("No ASANA project specified!")

    if not args.secret:
        fail("No Webhook secret specified!")

    github = ghlib.GitHub(args.gh_url, args.gh_token)
    asana = asanalib.Asana(args.asana_url, args.asana_token)
    asana_project = asanalib.AsanaProject(asana, args.asana_project, args.asana_workspace)
    s = Sync(
        github,
        asana,
        asana_project,
        args.asana_workspace,
        direction=direction_str_to_num(args.direction),
    )
    server.run_server(s, args.secret, port=args.port)


def sync(args):
    if not args.gh_url or not args.asana_url:
        fail("Both GitHub and ASANA URL have to be specified!")

    if not args.gh_token:
        fail("No GitHub credentials specified!")

    if not args.asana_workspace or not args.asana_token:
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
    asana_project = asanalib.AsanaProject(asana, args.asana_project, args.asana_workspace)

    repo_id = args.gh_org + "/" + args.gh_repo


    s = Sync(github, asana, asana_project, args.asana_workspace, direction=direction_str_to_num(args.direction))
    s.sync_repo(repo_id)


def check_hooks(args):
    pass


def install_hooks(args):
    if not args.hook_url:
        fail("No hook URL specified!")

    if not args.secret:
        fail("No hook secret specified!")

    if not args.gh_url and not args.asana_url:
        fail("Neither GitHub nor ASANA URL specified!")

    # user wants to install a github hook
    if args.gh_url:
        if not args.gh_token:
            fail("No GitHub token specified!")

        if not args.gh_org:
            fail("No GitHub organization specified!")

        github = ghlib.GitHub(args.gh_url, args.gh_token)

        if args.gh_repo:
            ghrepo = github.getRepository(args.gh_org + "/" + args.gh_repo)
            ghrepo.create_hook(url=args.hook_url, secret=args.secret)
        else:
            github.create_org_hook(url=args.hook_url, secret=args.secret)

    # user wants to install a ASANA hook
    if args.asana_url:
        if not args.asana_workspace or not args.asana_token:
            fail("No ASANA credentials specified!")
        asana = asanalib.Asana(args.asana_url, args.asana_workspace, args.asana_token)
        asana.create_hook("github_asana_synchronization_hook", args.hook_url, args.secret)


def list_hooks(args):
    if not args.gh_url and not args.asana_url:
        fail("Neither GitHub nor ASANA URL specified!")

    # user wants to list github hooks
    if args.gh_url:
        if not args.gh_token:
            fail("No GitHub token specified!")

        if not args.gh_org:
            fail("No GitHub organization specified!")

        github = ghlib.GitHub(args.gh_url, args.gh_token)

        if args.gh_repo:
            for h in github.getRepository(
                args.gh_org + "/" + args.gh_repo
            ).list_hooks():
                print(json.dumps(h, indent=4))
        else:
            for h in github.list_org_hooks(args.gh_org):
                print(json.dumps(h, indent=4))

    # user wants to list ASANA hooks
    if args.asana_url:
        if not args.asana_workspace or not args.asana_token:
            fail("No ASANA credentials specified!")

        asana = asanalib.Asana(args.asana_url, args.asana_workspace, args.asana_token)

        for h in asana.list_hooks():
            print(json.dumps(h, indent=4))


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
    credential_base.add_argument("--asana-workspace", help="ASANA workspace")
    credential_base.add_argument(
        "--asana-token",
        help="ASANA password. Alternatively, the GH2ASANA_ASANA_TOKEN may be set.",
        default=os.getenv("GH2ASANA_ASANA_TOKEN"),
    )
    credential_base.add_argument("--asana-project", help="ASANA project key")
    credential_base.add_argument("--asana-labels", help="ASANA bug label(s)")
    credential_base.add_argument(
        "--secret",
        help="Webhook secret. Alternatively, the GH2ASANA_SECRET may be set.",
        default=os.getenv("GH2ASANA_SECRET"),
    )

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
        help="Spawn a webserver which keeps GitHub alerts and ASANA tickets in sync",
        description="Spawn a webserver which keeps GitHub alerts and ASANA tickets in sync",
    )
    serve_parser.add_argument(
        "--port", help="The port the server will listen on", default=5000
    )
    serve_parser.set_defaults(func=serve)

    # sync
    sync_parser = subparsers.add_parser(
        "sync",
        parents=[credential_base, direction_base, issue_state_base],
        help="Synchronize GitHub alerts and ASANA tickets for a given repository",
        description="Synchronize GitHub alerts and ASANA tickets for a given repository",
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
    sync_parser.set_defaults(func=sync)

    # hooks
    hooks = subparsers.add_parser(
        "hooks",
        help="Manage ASANA and GitHub webhooks",
        description="Manage ASANA and GitHub webhooks",
    )

    hooks_subparsers = hooks.add_subparsers()

    # list hooks
    hooks_list = hooks_subparsers.add_parser(
        "list",
        parents=[credential_base],
        help="List existing GitHub or ASANA webhooks",
        description="List existing GitHub or ASANA webhooks",
    )
    hooks_list.set_defaults(func=list_hooks)

    # install hooks
    hooks_install = hooks_subparsers.add_parser(
        "install",
        parents=[credential_base],
        help="Install existing GitHub or ASANA webhooks",
        description="Install GitHub or ASANA webhooks",
    )
    hooks_install.add_argument("--hook-url", help="Webhook target url")
    hooks_install.add_argument(
        "--insecure-ssl",
        action="store_true",
        help="Install GitHub hook without SSL check",
    )
    hooks_install.set_defaults(func=install_hooks)

    # check hooks
    hooks_check = hooks_subparsers.add_parser(
        "check",
        parents=[credential_base],
        help="Check that hooks are installed properly",
        description="Check that hooks are installed properly",
    )
    hooks_check.set_defaults(func=check_hooks)

    def print_usage(args):
        print(parser.format_usage())

    parser.set_defaults(func=print_usage)
    args = parser.parse_args()

    # run the given action
    args.func(args)


main()
