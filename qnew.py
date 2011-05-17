#!/usr/bin/env python

import argparse
import os
import sys

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
                os.mkdir(pgl.config['QUEUES'])
            os.mkdir(pgl.config['BRANCH_QUEUE'])
        file(pgl.config['QUEUE_SERIES'], 'w').close()
    if not os.path.exists(pgl.config['UNAPPLIED_PATCHES']):
        file(pgl.config['UNAPPLIED_PATCHES'], 'w').close()
    if not os.path.exists(pgl.config['SHA_NAME_MAP']):
        file(pgl.config['SHA_NAME_MAP'], 'w').close()

    # Make sure we don't already have a patch named like the one we want
    gitq.load_series()

    # Commit outstanding changes
    if not gitq.update_patch(commit_all=args.all, commitmsg=args.commitmsg,
                             new=True):
        pgl.die('Nothing to make a new patch from!')

    # Do this again here to figure out the base of our new patch
    gitq.include_config()
    patchbase = pgl.config['HEAD_SHA']

    # Update our stored idea of the patch series on disk
    pgl.config['SERIES'].append(patchbase)
    pgl.config['ACTIVE_PATCH'] = patchbase
    pgl.config['NAMES'][patchbase] = args.pname
    gitq.write_series()

    # Done!
    sys.stdout.write('Started new patch on branch %s\n' %
        (pgl.config['BRANCH'],))

    return 0
