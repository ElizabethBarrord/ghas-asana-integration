import asana
from asana.rest import ApiException
from pprint import pprint
import re
import util
import logging
import requests
import json


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
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.configuration = asana.Configuration()
        self.configuration.access_token = token
        self.client = asana.ApiClient(self.configuration)

    def auth(self):
        return self.token

    # def getProject(self, projectkey):
    #     return AsanaProject(self, projectkey)


class AsanaProject:
    def __init__(self, asana, projectkey, workspace):
        self.asana = asana
        self.projectkey = projectkey
        self.workspace = workspace

    # def get_state_issue(self, issue_key="-"):
    #     if issue_key != "-":
    #         return self.a.issue(issue_key)

    #     issue_search = 'project={asana_project} and description ~ "{key}"'.format(
    #         asana_project='"{}"'.format(self.projectkey), key=STATE_ISSUE_KEY
    #     )
    #     issues = list(
    #         filter(
    #             lambda i: i.fields.summary == STATE_ISSUE_SUMMARY,
    #             self.a.fetch_issues(issue_search, maxResults=0),
    #         )
    #     )

    #     if len(issues) == 0:
    #         return self.a.create_issue(
    #             project=self.projectkey,
    #             workspace=self.workspace,
    #             summary=STATE_ISSUE_SUMMARY,
    #             description=STATE_ISSUE_TEMPLATE,
    #             data={"name": "GHAS Alert"},
    #         )
    #     elif len(issues) > 1:
    #         issues.sort(key=lambda i: i.id())  # keep the oldest issue
    #         for i in issues[1:]:
    #             i.delete()

    #     i = issues[0]

    #     # When fetching issues via the search_issues() function, we somehow
    #     # cannot access the attachments. To do that, we need to fetch the issue
    #     # via the issue() function first.
    #     return self.a.issue(i.key)

    # def fetch_repo_state(self, repo_id, issue_key="-"):
    #     i = self.get_state_issue(issue_key)

    #     for a in i.fields.attachment:
    #         if a.filename == repo_id_to_fname(repo_id):
    #             return util.state_from_json(a.get())

    #     return {}

    # def save_repo_state(self, repo_id, state, issue_key="-"):
    #     i = self.get_state_issue(issue_key)

    #     # remove previous state files for the given repo_id
    #     for a in i.fields.attachment:
    #         if a.filename == repo_id_to_fname(repo_id):
    #             self.a.delete_attachment(a.id)

    #     # attach the new state file
    #     self.asana.attach_file(
    #         i.key, repo_id_to_fname(repo_id), util.state_to_json(state)
    #     )

    # create issue in asana using asana api
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
        try:
            title = TITLE_PREFIXES[alert_type] + " " + long_desc
            desc = DESC_TEMPLATE.format(
                repo_id=repo_id,
                alert_type=alert_type,
                alert_num=alert_num,
                repo_key=repo_key,
                alert_key=alert_key,
                alert_url=alert_url,
                long_desc=long_desc,
            )
            api_instance = asana.TasksApi(self.asana.client)
            project = self.projectkey # str | The project in which to search for the task.
            workspace = self.workspace # str | The workspace or organization in which to search for the task.
            body = asana.TasksBody({"workspace": workspace,"name":title, "projects":["1205454322162505"],"notes":desc}) # TasksBody | The task to create.
            # opt_fields = ["projects","projects.name"]
            api_response = api_instance.create_task(body)
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling TasksApi->get_tasks: %s\n" % e)


    def fetch_issues(self, key):
        
        try:
            api_instance = asana.TasksApi(self.asana.client)
            project = self.projectkey # str | The project in which to search for the task.
            workspace = self.workspace # str | The workspace or organization in which to search for the task.
            api_response = api_instance.get_tasks(project=project, workspace=workspace)
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling TasksApi->get_tasks: %s\n" % e)

        # issue_search = 'project={jira_project} and description ~ "{key}"'.format(
        #     jira_project='"{}"'.format(self.projectkey), key=key
        # )
        # issues = list(
        #     filter(
        #         lambda i: i.is_managed(),
        #         [
        #             JiraIssue(self, raw)
        #             for raw in self.j.search_issues(issue_search, maxResults=0)
        #         ],
        #     )
        # )
        logger.debug(
            "Search {search} returned {num_results} results.".format(
                search=issue_search, num_results=len(issues)
            )
        )
        return issues



class AsanaIssue:
    def __init__(self, project, workspace, rawissue):
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
