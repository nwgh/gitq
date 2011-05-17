#!/usr/bin/env python

import os
import shutil
import subprocess
import sys

import gitq
import pgl

@pgl.main
def main():
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
    else:
        apply_sha = pgl.config['UNAPPLIED'][-1]
        apply_name = pgl.config['NAMES'][apply_sha]

    # Re-apply the patch using git am
    patchdir = os.path.join(pgl.config['BRANCH_QUEUE'], apply_sha)
    gitam = subprocess.Popen(['git', 'am', patchdir], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    if gitam.wait():
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
