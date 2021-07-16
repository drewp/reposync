#!/usr/bin/python3
from pathlib import Path

from sync import Project, getSshAuthSock

p = Project(Path('.').absolute())
p.makeGithubRepo()
p.hgToGithub()
