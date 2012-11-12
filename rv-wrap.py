#!/usr/bin/env python
#-*- coding:utf-8 -*-
u'''
Review Board に投稿するよ
'''

import sys
import os
import re
import argparse
import subprocess
import urllib2
import urlparse
import csv

from rbtools import postreview, clients
from rbtools.utils import filesystem


def make_parser():
    u'''
    コマンドラインオプションパーサを作るとかそんなの
    '''

    parser = argparse.ArgumentParser(description=u'Review Board にポストするのを楽にする')

    parser.add_argument('--revision', '-r', metavar='REV', dest='revision',
                        help=u'リビジョンいれる (HEAD^ とかそういうの)')
    parser.add_argument('--trac-url', metavar='URL', dest='trac_url',
                        help=u'trac の URL')
    parser.add_argument('--trac-realm', metavar='RELM', dest='trac_realm',
                        help=u'trac の Relm')
    parser.add_argument('--trac-user', metavar='ID', dest='trac_user',
                        help=u'trac の User ID')
    parser.add_argument('--trac-password', metavar='PW', dest='trac_password',
                        help=u'trac の Password')
    parser.add_argument('--review-group', metavar='GROUP', dest='review_group',
                        help=u'Review Board でレビューしてもらうグループ')
    parser.add_argument('--review-user', metavar='USERP', dest='review_user',
                        help=u'Review Board でレビューしてもらうユーザ')

    return parser



FIXED_REGEX = re.compile(r'^fix(?:ed)? #(\d+)')
REFS_REGEX = re.compile(r'^refs? #(\d+)')


class CommitInfo(object):
    u'''
    コミット情報
    '''


    def __init__(self, rev_hash, headers, message, diff):

        self.hash = rev_hash
        self.headers = headers
        self.message = message
        self.diff = diff



    def get_ticket_from_message(self):
        u'''
        コミットメッセージからチケット番号を探す
        '''

        m = FIXED_REGEX.search(self.message)

        if m:
            return ('fixed', int(m.group(1)))

        m = REFS_REGEX.search(self.message)

        if m:
            return ('refs', int(m.group(1)))


def get_commit_info(rev=None):
    u'''
    git リポジトリからコミット情報を取ってくる
    '''

    cmd = ['git', 'log', '-n', '1', '-u']

    if rev is not None:
        cmd.append(rev)

    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    ret = p.wait()

    if ret != 0:
        print >> sys.stderr, p.stderr.read()
        sys.exit(ret)

    stdout = list(reversed(p.stdout.readlines()))

    hash = stdout.pop().split()[1]
    headers = {}

    while 1:
        line = stdout.pop()

        if not line.strip():
            break

        header, value = line.split(':', 1)
        headers[header] = value.strip()

    msg = []

    for x in stdout:
        line = stdout.pop()

        if not line.startswith('    '):
            stdout.append(line)
            break

        msg.append(line.strip())

    message = '\n'.join(msg)

    diff = '\n'.join(x.strip() for x in reversed(stdout))

    return CommitInfo(hash, headers, message, diff)



def _get_url(root):
    u'''
    http://host/path から http://host を得る
    '''

    result = urlparse.urlparse(root)

    url = '{0.scheme}://{0.hostname}'.format(result)

    if (result.port):
        url = url + ':' + str(url.port)

    return url + '/'



def _get_content_encode(resp):
    u'''
    Content-Type からエンコード情報を取ってくる
    '''

    typ = resp.headers.get('Content-Type')

    if typ is None:
        return 'ascii'

    values = typ.split('=')

    if len(values) > 1:
        return values[-1]

    return 'ascii'




def get_ticket_info_from_trac(args, ticket):
    u'''
    trac からチケット情報を取ってくる
    '''

    if args.trac_url is None:
        return None

    mgr = urllib2.HTTPPasswordMgr()
    mgr.add_password(args.trac_realm, _get_url(args.trac_url), args.trac_user, args.trac_password)
    handler = urllib2.HTTPBasicAuthHandler(mgr)
    opener = urllib2.build_opener(handler)

    url = '{0}ticket/{1}?format=csv'.format(args.trac_url, ticket)

    data = opener.open(url)

    encode = _get_content_encode(data)

    reader = csv.DictReader(data)

    value = iter(reader).next()

    return dict((k.decode(encode), v.decode(encode)) for k, v in value.iteritems())



def get_review_info(ticket):
    u'''
    対象チケット情報から review board の review request 情報をとってきて返す
    大体 rbtools.postreview.main から取ってきてる
    '''

    home = os.environ['HOME']

    cookie = os.path.join(home, '.post-review-cookies.txt')
    user_config, configs = filesystem.load_config_files(home)

    postreview.parse_options([])
    options = postreview.options

    repository_info, tool = clients.scan_usable_client(options)

    tool.user_config = user_config
    tool.configs = configs

    tool.check_options()

    server_url = tool.scan_for_server(repository_info)

    server = postreview.ReviewBoardServer(server_url, repository_info, cookie)

    server.login()

    results = server.api_get('/api/review-requests')

    ticket = unicode(ticket)

    requests = [rq for rq in results['review_requests'] if ticket in rq['bugs_closed']]

    return requests



def execute_command(args, cinfo, info, review_id):
    u'''
    post-review を実行するよ
    '''

    cmd = [u'post-review', u'-p']

    if info:
        tid = info['id']
        cmd.extend([u'--bugs-closed', tid])
        cmd.extend([u'--summary', u'#{0} {1}'.format(tid, info.get('summary'))])
    else:
        cmd.append(u'--guess-summary')

    if args.review_user is not None:
        cmd.extend([u'--target-people', args.review_user])

    if args.review_group is not None:
        cmd.extend([u'--target-group', args.review_group])

    if review_id is not None:
        cmd.extend([u'-r', unicode(review_id)])

    cmd.extend([u'--description', cinfo.message])

    p = subprocess.Popen(cmd)

    p.wait()



def main(args=sys.argv[1:]):

    args = make_parser().parse_args(args)

    cinfo = get_commit_info(args.revision)

    tinfo = cinfo.get_ticket_from_message()

    reftype = None
    ticket = None
    review_id = None

    if tinfo is not None:
        ticket = get_ticket_info_from_trac(args, tinfo[1])
        reviews = get_review_info(tinfo[1])

        if reviews:
            review_id = reviews[0]['id']


    execute_command(args, cinfo, ticket, review_id)



if __name__ == '__main__':
    main()
