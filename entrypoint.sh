#!/bin/sh
REPOSITORY_NAME="$(echo "$GITHUB_REPOSITORY" | cut -d/ -f 2)"
cd / && pipenv run /gh2asana sync \
                            --gh-url "$GITHUB_API_URL" \
                            --gh-token "$INPUT_GITHUB_TOKEN" \
                            --gh-org "$GITHUB_REPOSITORY_OWNER" \
                            --gh-repo "$REPOSITORY_NAME" \
                            --asana-url "$INPUT_ASANA_URL" \
                            --asana-token "$INPUT_ASANA_TOKEN" \
                            --asana-workspace "$INPUT_ASANA_WORKSPACE" \
                            --asana-project "$INPUT_ASANA_PROJECT" \
                            --direction "$INPUT_SYNC_DIRECTION" \
