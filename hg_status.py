from dataclasses import dataclass, field
import datetime
import json
import logging
from pathlib import Path
import time
import traceback
from typing import Dict, Optional, Tuple

import cyclone.httpserver
import cyclone.sse
import cyclone.web
from cycloneerr import PrettyErrorHandler
from dateutil.parser import parse
from dateutil.tz import tzlocal
import docopt
from ruamel.yaml import YAML
from standardservice.logsetup import log, verboseLogging
import treq
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.utils import getProcessOutput, _UnexpectedErrorOutput
import tzlocal

local = tzlocal.get_localzone()
githubOwner = 'drewp'


@inlineCallbacks
def runHg(cwd, args):
    if args[0] not in ['push']:
        args.extend(['-T', 'json'])
    j = yield getProcessOutput('/usr/local/bin/hg', args, path=cwd)
    returnValue(json.loads(j) if j else None)


@dataclass
class Repo:
    path: Path
    github: bool
    _cache: Dict[str, Tuple[float, object]] = field(default_factory=dict)

    def _isStale(self, group) -> Optional[object]:
        now = time.time()
        if group not in self._cache:
            return True
        if now > self._cache[group][0] + 86400:
            return True
        print('fresh')
        return False

    def _save(self, group, obj):
        now = time.time()
        self._cache[group] = (now, obj)

    def _get(self, group):
        print('get')
        return self._cache[group][1]

    @inlineCallbacks
    def getStatus(self):
        if self._isStale('status'):
            try:
                statusResp = yield runHg(self.path, ['status'])
            except Exception as e:
                status = {'error': repr(e)}
            else:
                unknowns = len([row for row in statusResp if row['status'] == '?'])
                status = {'unknown': unknowns, 'changed': len(statusResp) - unknowns}
            self._save('status', status)
        returnValue(self._get('status'))

    @inlineCallbacks
    def getLatestHgCommit(self):
        if self._isStale('log'):
            rows = yield runHg(self.path, ['log', '--limit', '1'])
            commit = rows[0]
            sec = commit['date'][0]
            t = datetime.datetime.fromtimestamp(sec, local)
            self._save('log', {'email': commit['user'], 't': t.isoformat(), 'message': commit['desc']})
        returnValue(self._get('log'))

    @inlineCallbacks
    def getLatestGithubCommit(self):
        if self._isStale('github'):
            resp = yield treq.get(f'https://api.github.com/repos/{githubOwner}/{self.path.name}/commits?per_page=1',
                                  timeout=5,
                                  headers={
                                      'User-agent': 'reposync by github.com/drewp',
                                      'Accept': 'application/vnd.github.v3+json'
                                  })
            ret = yield treq.json_content(resp)
            commit = ret[0]['commit']
            t = parse(commit['committer']['date']).astimezone(local).isoformat()
            self._save('github', {'email': commit['committer']['email'], 't': t, 'message': commit['message']})
        returnValue(self._get('github'))

    @inlineCallbacks
    def clearGithubMaster(self):
        '''bang(pts/13):/tmp/reset% git init
Initialized empty Git repository in /tmp/reset/.git/
then github set current to a new branch called 'clearing' with https://developer.github.com/v3/repos/#update-a-repository
bang(pts/13):/tmp/reset% git remote add origin git@github.com:drewp/href.git
bang(pts/13):/tmp/reset% git push origin :master
To github.com:drewp/href.git
 - [deleted]         master
maybe --set-upstream origin
bang(pts/13):/tmp/reset% git remote set-branches origin master
?
then push
then github setdefault to master
then github delete clearing 
'''

    @inlineCallbacks
    def pushToGithub(self):
        if not self.github:
            raise ValueError
        yield runHg(self.path, ['bookmark', '--rev', 'default', 'master'])
        out = yield runHg(self.path, ['push', f'git+ssh://git@github.com/{githubOwner}/{self.path.name}.git'])
        print(f'out fompushh {out}')


class GithubSync(PrettyErrorHandler, cyclone.web.RequestHandler):

    @inlineCallbacks
    def post(self):
        try:
            path = self.get_argument('repo')
            repo = [r for r in self.settings.repos if str(r.path) == path][0]
            yield repo.pushToGithub()
        except Exception:
            traceback.print_exc()
            raise


class Statuses(cyclone.sse.SSEHandler):

    def update(self, key, data):
        self.sendEvent(json.dumps({'key': key, 'update': data}).encode('utf8'))

    def bind(self):
        self.toProcess = self.settings.repos[:]
        reactor.callLater(0, self.runOne)

    @inlineCallbacks
    def runOne(self):
        if not self.toProcess:
            print('done')
            return
        repo = self.toProcess.pop(0)

        try:
            update = {'path': str(repo.path), 'github': repo.github, 'status': (yield repo.getStatus()), 'hgLatest': (yield repo.getLatestHgCommit())}
            if repo.github:
                update['githubLatest'] = (yield repo.getLatestGithubCommit())
            self.update(str(repo.path), update)
        except Exception:
            log.warn(f'not reporting on {repo}')
            traceback.print_exc()
        reactor.callLater(0, self.runOne)


def main():
    args = docopt.docopt('''
Usage:
  hg_status.py [options]

Options:
  -v, --verbose  more logging
''')
    verboseLogging(args['--verbose'])

    import sys
    sys.path.append('/usr/lib/python3/dist-packages')
    import OpenSSL

    yaml = YAML(typ='safe')
    config = yaml.load(open('config.yaml'))
    repos = [Repo(Path(row['dir']), row['github']) for row in config['hg_repos']]

    class Application(cyclone.web.Application):

        def __init__(self):
            handlers = [
                (r"/()", cyclone.web.StaticFileHandler, {
                    'path': '.',
                    'default_filename': 'index.html'
                }),
                (r'/build/(bundle\.js)', cyclone.web.StaticFileHandler, {
                    'path': './build/'
                }),
                (r'/status/events', Statuses),
                (r'/githubSync', GithubSync),
            ]
            cyclone.web.Application.__init__(
                self,
                handlers,
                repos=repos,
                debug=args['--verbose'],
                template_path='.',
            )

    reactor.listenTCP(10001, Application())
    reactor.run()


if __name__ == '__main__':
    main()
