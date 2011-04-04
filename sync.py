#!bin/python

import os, subprocess, urllib2, jsonlib, logging, traceback
from github import github
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

class Project(object):
    def __init__(self, config, gh, name):
        self.config = config
        self.gh = gh
        self.name = name
        
    def gitDir(self):
        gitDir = os.path.join(self.config['gitSyncDir'], self.name)
        try:
            os.mkdir(gitDir)
        except OSError: pass
        return gitDir
    
    def syncToLocalGit(self):
        darcsDir = os.path.join(self.config['darcsDir'], self.name)
        try:
            os.rmdir(os.path.join(darcsDir, 'darcs_testing_for_nfs'))
        except OSError: pass
        self.runGitCommand([self.config['darcsToGitCmd'], '--no-verbose', darcsDir])

    def runGitCommand(self, args):
        subprocess.check_call(args, cwd=self.gitDir(),
                          env={'SSH_AUTH_SOCK': self.config['SSH_AUTH_SOCK']})

    def makeGitHubRepo(self):
        try:
            self.gh.repos.create(self.name)
        except urllib2.HTTPError:
            return
        self.runGitCommand(['git', 'remote', 'add', 'origin',
                            'git@github.com:%s/%s.git' % (self.gh.user,
                                                          self.name)])

    def pushToGitHub(self):
        self.runGitCommand(['git', 'push', 'origin', 'master'])

config = jsonlib.read(open("config.json").read())
gh = github.GitHub(config['user'], config['gitHubToken'])

for proj in os.listdir(config['darcsDir']):
    if 'repo' not in proj:
        continue
    if not os.path.isdir(os.path.join(config['darcsDir'], proj)):
        continue
    try:
        p = Project(config, gh, proj)
        log.info("syncing %s" % proj)
        p.syncToLocalGit()
        p.makeGitHubRepo()
        p.pushToGitHub()
    except Exception, e:
        traceback.print_exc()
        
