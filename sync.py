#!bin/python

import os, subprocess, urllib2, json, logging, traceback, time
from github import Github, GithubException
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
        try:
            subprocess.check_call(args, cwd=self.gitDir(),
                                  env={'SSH_AUTH_SOCK': self.config['SSH_AUTH_SOCK'],
                                       'HOME': os.environ['HOME'], # darcs-to-git uses this
                                       })
        except:
            log.error("in %s" % self.gitDir())
            raise

    def makeGitHubRepo(self):
        try:
            self.gh.create_repo(self.name)
        except GithubException, e:
            assert e.data['errors'][0]['message'].startswith('name already exists'), e
            return
        self.runGitCommand(['git', 'remote', 'add', 'origin',
                            'git@github.com:%s/%s.git' % (self.gh.login,
                                                          self.name)])

    def pushToGitHub(self):
        self.runGitCommand(['git', 'push', 'origin', 'master'])

config = json.loads(open("config.json").read())

# to get this token:
# curl -u drewp https://api.github.com/authorizations -d '{"scopes":["repo"]}'
# from http://developer.github.com/v3/oauth/#oauth-authorizations-api
gh = Github(config['gitHubToken']).get_user()

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
        
