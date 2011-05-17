#!/usr/bin/env python

import argparse
import os

import gitq
import pgl

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Update a patch',
        prog='git qrefresh')
    ap.add_argument('-a', dest='all', help='Add all unstaged changes to patch',
        action='store_true', default=False)
    args = ap.parse_args()

    gitq.include_config()

    gitq.load_series()

    if not os.path.exists(pgl.config['QUEUE_SERIES']):
        pgl.die('There is no git queue for branch %s here!' %
            (pgl.config['BRANCH'],))

    if not gitq.update_patch(commit_all=args.all):
        pgl.die('There was nothing to update the patch with!')

    return 0
