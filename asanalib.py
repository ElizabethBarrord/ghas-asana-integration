from asana.rest import ApiException
from pprint import pprint
import re
import util
import logging
import requests
import json
import asana


TITLE_PREFIXES = {
    "Alert": "[Code Scanning Alert]:",
    "Secret": "[Secret Scanning Alert]:",
}

DESC_TEMPLATE = """
{long_desc}

{alert_url}

----
This issue was automatically generated from a GitHub alert, and will be automatically resolved once the underlying problem is fixed.
DO NOT MODIFY DESCRIPTION BELOW LINE.
REPOSITORY_NAME={repo_id}
ALERT_TYPE={alert_type}
ALERT_NUMBER={alert_num}
REPOSITORY_KEY={repo_key}
ALERT_KEY={alert_key}
"""


STATE_ISSUE_SUMMARY = "[Code Scanning Issue States]"
STATE_ISSUE_KEY = util.make_key("gh2asana-state-issue")
STATE_ISSUE_TEMPLATE = """
This issue was automatically generated and contains states required for the synchronization between GitHub and ASANA.
DO NOT MODIFY DESCRIPTION BELOW LINE.
ISSUE_KEY={issue_key}
""".format(
    issue_key=STATE_ISSUE_KEY
)

logger = logging.getLogger(__name__)


class Asana:
    def __init__(self, url, user, token):
        self.url = url
        self.user = user
        self.token = token
        self.a = ASANA(url, basic_auth=(user, token))

    def auth(self):
        return self.user, self.token

    def getProject(self, projectkey, endstate, reopenstate):
        return AsanaProject(self, projectkey, endstate, reopenstate)


class AsanaProject:
    def __init__(self, asana, projectkey, workspaceid, endstate, reopenstate):
        self.asana = asana
        self.projectkey = projectkey
        self.workspaceid = workspaceid
        self.a = self.asana.a
        self.endstate = endstate
        self.reopenstate = reopenstate

    def get_state_issue(self, issue_key="-"):
        if issue_key != "-":
            return self.j.issue(issue_key)

        issue_search = 'project={asana_project} and description ~ "{key}"'.format(
            asana_project='"{}"'.format(self.projectkey), key=STATE_ISSUE_KEY
        )
        issues = list(
            filter(
                lambda i: i.fields.summary == STATE_ISSUE_SUMMARY,
                self.j.search_issues(issue_search, maxResults=0),
            )
        )

        if len(issues) == 0:
            return self.j.create_issue(
                project=self.projectkey,
                workspaceid=self.workspaceid,
                summary=STATE_ISSUE_SUMMARY,
                description=STATE_ISSUE_TEMPLATE,
                data={"name": "GHAS Alert"},
            )
        elif len(issues) > 1:
            issues.sort(key=lambda i: i.id())  # keep the oldest issue
            for i in issues[1:]:
                i.delete()

        i = issues[0]

        # When fetching issues via the search_issues() function, we somehow
        # cannot access the attachments. To do that, we need to fetch the issue
        # via the issue() function first.
        return self.j.issue(i.key)

    def fetch_repo_state(self, repo_id, issue_key="-"):
        i = self.get_state_issue(issue_key)

        for a in i.fields.attachment:
            if a.filename == repo_id_to_fname(repo_id):
                return util.state_from_json(a.get())

        return {}

    def save_repo_state(self, repo_id, state, issue_key="-"):
        i = self.get_state_issue(issue_key)

        # remove previous state files for the given repo_id
        for a in i.fields.attachment:
            if a.filename == repo_id_to_fname(repo_id):
                self.j.delete_attachment(a.id)

        # attach the new state file
        self.asana.attach_file(
            i.key, repo_id_to_fname(repo_id), util.state_to_json(state)
        )

    def create_issue(
        self,
        repo_id,
        short_desc,
        long_desc,
        alert_url,
        alert_type,
        alert_num,
        repo_key,
        alert_key,
    ):
        logger.info(
            "hit create_issuse"
            )
        raw = self.a.create_issue(
            configuration = asana.Configuration()
            configuration.access_token = self.asana.token
            configuration.host = self.asana.url
            api_client = asana.ApiClient(configuration)
            api_instance = asana.TasksApi(api_client)
            body = asana.TasksBody({"name": "From Action", "workspace": self.workspaceid, projects: [self.projectkey]})
            opt_fields = ["workspace","workspace.name"]

            try:
                # Create a task
                api_response = api_instance.create_task(body, opt_fields=opt_fields)
                pprint(api_response)
            except ApiException as e:
                print("Exception when calling TasksApi->create_task: %s\n" % e)


            # project=self.projectkey,
            # summary="{prefix} {short_desc} in {repo}".format(
            #     prefix=TITLE_PREFIXES[alert_type], short_desc=short_desc, repo=repo_id
            # ),
            # notes=DESC_TEMPLATE.format(
            #     long_desc=long_desc,
            #     alert_url=alert_url,
            #     repo_id=repo_id,
            #     alert_type=alert_type,
            #     alert_num=alert_num,
            #     repo_key=repo_key,
            #     alert_key=alert_key,
            # ),
            # issuetype={"name": "Bug"},
        )
        logger.info(
            "Created issue {issue_key} for alert {alert_num} in {repo_id}.".format(
                issue_key=raw.key, alert_num=alert_num, repo_id=repo_id
            )
        )
        logger.info(
            "Created issue {issue_key} for {alert_type} {alert_num} in {repo_id}.".format(
                issue_key=raw.key,
                alert_type=alert_type,
                alert_num=alert_num,
                repo_id=repo_id,
            )
        )

        return AsanaIssue(self, raw)


class AsanaIssue:
    def __init__(self, project, workspace rawissue):
        self.project = project
        self.workspace = workspace
        self.rawissue = rawissue
        self.a = self.project.a

    def is_managed(self):
        if parse_alert_info(self.rawissue.fields.description)[0] is None:
            return False
        return True

    def get_alert_info(self):
        return parse_alert_info(self.rawissue.fields.description)

    def key(self):
        return self.rawissue.key

    def id(self):
        return self.rawissue.id

    def delete(self):
        logger.info("Deleting issue {ikey}.".format(ikey=self.key()))
        self.rawissue.delete()

    def get_state(self):
        return self.parse_state(self.rawissue.fields.status.name)

    def adjust_state(self, state):
        if state:
            self.transition(self.reopenstate)
        else:
            self.transition(self.endstate)

    def parse_state(self, raw_state):
        return raw_state != self.endstate


def parse_alert_info(desc):
    """
    Parse all the fields in an issue's description and return
    them as a tuple. If parsing fails for one of the fields,
    return a tuple of None's.
    """
    failed = None, None, None, None
    m = re.search("REPOSITORY_NAME=(.*)$", desc, re.MULTILINE)
    if m is None:
        return failed
    repo_id = m.group(1)

    m = re.search("ALERT_TYPE=(.*)$", desc, re.MULTILINE)
    if m is None:
        alert_type = None
    else:
        alert_type = m.group(1)
    m = re.search("ALERT_NUMBER=(.*)$", desc, re.MULTILINE)

    if m is None:
        return failed
    alert_num = int(m.group(1))
    m = re.search("REPOSITORY_KEY=(.*)$", desc, re.MULTILINE)
    if m is None:
        return failed
    repo_key = m.group(1)
    m = re.search("ALERT_KEY=(.*)$", desc, re.MULTILINE)
    if m is None:
        return failed
    alert_key = m.group(1)

    return repo_id, alert_num, repo_key, alert_key, alert_type


def repo_id_to_fname(repo_id):
    return repo_id.replace("/", "^") + ".json"
