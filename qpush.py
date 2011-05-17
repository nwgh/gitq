#!/usr/bin/env python

import argparse
import glob
import os
import shutil
import subprocess
import sys

import gitq
import pgl

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Apply a popped patch',
        prog='git qpush')
    ap.add_argument('pname', help='Name of patch', default=None)
    ap.add_argument('-i', dest='interactive', help='Choose patch interactively',
        default=False, action='store_true')
    # TODO - handle different username/email
    args = ap.parse_args()

    # Make sure we have all the config we need
    gitq.include_config()

    gitq.load_series()

    if not pgl.config['UNAPPLIED']:
        pgl.die('No patches for this branch!')

    # Make sure we have no uncommitted changes
    if gitq.repo_has_changes():
        pgl.die('Working directory has uncommitted changes. Either qrefresh '
                'or stash them before continuing.')

    # Figure out what patch to apply if they didn't specify on the command line
    apply_sha, apply_name = None, None
    if args.interactive:
        while apply_sha is None:
            sys.stdout.write('Choose a patch to apply:\n')
            for i, sha in enumerate(pgl.config['UNAPPLIED']):
                sys.stdout.write('%d %s\n' % (i + 1, pgl.config['NAMES'][sha]))
            sys.stdout.flush()
            choice = raw_input('> ')
            try:
                if 0 < int(choice) <= len(pgl.config['UNAPPLIED']):
                    apply_sha = pgl.config['UNAPPLIED'][choice - 1]
                    apply_name = pgl.config['NAMES'][apply_sha]
            except ValueError:
                pass
    elif args.pname:
        if args.pname not in pgl.config['SHAS']:
            pgl.die('Unknown patch: %s' % (args.pname,))
        apply_name = args.pname
        apply_sha = pgl.config['SHAS'][args.pname]
    else:
        apply_sha = pgl.config['UNAPPLIED'][-1]
        apply_name = pgl.config['NAMES'][apply_sha]

    # Re-apply the patch using git am
    patchdir = os.path.join(pgl.config['BRANCH_QUEUE'], apply_sha)
    if not os.path.exists(patchdir):
        pgl.die('Missing patch directory for %s. Oops!' % (apply_name,))

    patches = glob.glob(os.path.join(patchdir, '*.patch'))
    if not patches:
        pgl.die('Missing patches for %s. Oops!' % (apply_name,))

    for patch in patches:
        gitam = subprocess.Popen(['git', 'am', patch], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        if gitam.wait():
            gitreset = subprocess.Popen(['git', 'reset', '--hard',
                                         pgl.config['HEAD_SHA']],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            gitreset.wait()
            pgl.die('Failed to apply patches!')

    # Remove saved patches directory
    shutil.rmtree(patchdir)

    # Put our reapplied patch in the series, and save to disk
    gitq.include_config() # Re-read HEAD sha
    pgl.config['SERIES'].append(pgl.config['HEAD_SHA'])
    pgl.config['UNAPPLIED'].remove(apply_sha)

    # Now that we may (or may not) have a new base sha for this patch,
    # update that info, too
    pgl.config['SHAS'][apply_name] = pgl.config['HEAD_SHA']
    del pgl.config['NAMES'][apply_sha]
    pgl.config['NAMES'][pgl.config['HEAD_SHA']] = apply_name

    gitq.write_series()

    return 0
