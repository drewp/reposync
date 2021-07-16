#!/usr/bin/python3
from pathlib import Path
import json

from github import Github
from sync import Project, getSshAuthSock

config = json.loads(open("config.json").read())
config['SSH_AUTH_SOCK'] = getSshAuthSock()

# to get this token:
# curl -u drewp https://api.github.com/authorizations -d '{"scopes":["repo"]}'
# from http://developer.github.com/v3/oauth/#oauth-authorizations-api
gh = Github(config['gitHubToken']).get_user()

p = Project(config, gh, Path('.').absolute())
p.makeGitHubRepo()
p.hgToGitHub()
