#!bin/python

import os, subprocess, json, logging, traceback, time, re
from pathlib import Path
from github import Github, GithubException
logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

class Project(object):
    def __init__(self, config, gh, projRoot: Path):
        self.config = config
        self.gh = gh
        self.projRoot = projRoot
        self.name = projRoot.name

    def darcsTime(self):
        j = os.path.join
        darcsPriv = j(self.config['darcsDir'], self.name, '_darcs')
        for n in ['inventory', 'hashed_inventory']:
            if os.path.exists(j(darcsPriv, n)):
                return os.path.getmtime(j(darcsPriv, n))
        raise ValueError("can't find a darcs time")

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
        self.runGitCommand([self.config['darcsToGitCmd'], '--verbose', darcsDir])

    def runGitCommand(self, args, callKw={}):
        try:
            subprocess.check_call(args, cwd=self.gitDir(),
                                  env={'SSH_AUTH_SOCK': self.config['SSH_AUTH_SOCK'],
                                       'HOME': os.environ['HOME'], # darcs-to-git uses this
                                       }, **callKw)
        except:
            log.error("in %s" % self.gitDir())
            raise

    def makeGitHubRepo(self):
        try:
            self.gh.create_repo(self.name)
        except GithubException as e:
            print('exists')
            assert e.data['errors'][0]['message'].startswith('name already exists'), (e, self.name)
            return
        self.runGitCommand(['git', 'remote', 'add', 'origin',
                            'git@github.com:%s/%s.git' % (self.gh.login,
                                                          self.name)])

    def pushToGitHub(self):
        self.runGitCommand(['git', 'push', 'origin', 'master'])

    def hgToGitHub(self):
        subprocess.check_call(['hg', 'bookmark', '-r', 'default', 'main'],
                              cwd=self.projRoot)
        subprocess.check_call(['hg', 'push',
                               f'git+ssh://git@github.com/{self.gh.login}/{self.name}'
                               ],
                              cwd=self.projRoot,
                              env={'SSH_AUTH_SOCK': self.config['SSH_AUTH_SOCK']})

def getSshAuthSock():
    keychain = subprocess.check_output([
        "keychain", "--noask", "--quiet", "--eval", "id_rsa"]).decode('ascii')
    m = re.search(r'SSH_AUTH_SOCK=([^; \n]+)', keychain)
    if m is None:
        raise ValueError("couldn't find SSH_AUTH_SOCK in output "
                         "from keychain: %r" % keychain)
    return m.group(1)

if __name__ == '__main__':
    config = json.loads(open("config.json").read())
    config['SSH_AUTH_SOCK'] = getSshAuthSock()

    # to get this token:
    # curl -u drewp https://api.github.com/authorizations -d '{"scopes":["repo"]}'
    # --new:
    # from https://docs.github.com/en/developers/apps/building-oauth-apps/authorizing-oauth-apps#non-web-application-flow -> https://github.com/settings/tokens to make one

    gh = Github(config['gitHubToken']).get_user()

    for proj in os.listdir(config['darcsDir']):
        if not os.path.isdir(os.path.join(config['darcsDir'], proj)):
            continue
        try:
            p = Project(config, gh, proj)

            if p.darcsTime() < time.time() - 86400*config['tooOldDays']:
                continue

            log.info("syncing %s", proj)
            p.syncToLocalGit()
            p.makeGitHubRepo()
            p.pushToGitHub()
        except Exception as e:
            traceback.print_exc()
