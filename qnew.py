#!/usr/bin/env python

import argparse
import os

import gitq
import pgl

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Create a new patch',
        prog='git qnew')
    ap.add_argument('pname', help='Name of patch')
    ap.add_argument('-a', dest='all', help='Add all unstaged changes to patch',
        action='store_true', default=False)
    ap.add_argument('-m', dest='commitmsg', help='Commit message for patch',
        default=None)
    # TODO - handle different username/email
    args = ap.parse_args()

    # Make sure we have all the config we need
    gitq.include_config()

    # Make sure our queue directory is setup
    if not os.path.exists(pgl.config['QUEUE_SERIES']):
        if not os.path.exists(pgl.config['BRANCH_QUEUE']):
            if not os.path.exists(pgl.config['QUEUES']):
                os.path.mkdir(pgl.config['QUEUES'])
            os.path.mkdir(pgl.config['BRANCH_QUEUE'])
        file(pgl.config['QUEUE_SERIES'], 'w').close()

    # Update the series metadata on disk, marking our current patch as active
    gitq.load_series()

    if args.pname in pgl.config['SERIES']:
        pgl.die('You already have a patch named %s on the current branch!' %
            (args.pname,))

    if pgl.config['ACTIVE_PATCH']:
        pgl.config['SERIES'][pgl.config['ACTIVE_PATCH']]['active'] = False
    pgl.config['SERIES_ORDER'].append(args.pname)
    patchno = len(pgl.config['SERIES_ORDER']) - 1
    pgl.config['ACTIVE_PATCH'] = args.pname
    pgl.config['SERIES'][args.pname] = {'base':pgl.config['HEAD_SHA'],
                                        'order':patchno,
                                        'active':True}
    curpatch = pgl.config['SERIES'][args.pname]

    gitq.write_series()

    # Commit outstanding changes
    gitq.update_patch(commit_all=args.all, commitmsg=args.commitmsg)

    # Done!
    sys.stdout.write('Started new patch %s on branch %s\n' %
        (args.pname, pgl.config['BRANCH']))
    sys.exit(0)
