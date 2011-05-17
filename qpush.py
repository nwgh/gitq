#!/usr/bin/env python

import argparse
import glob
import os
import shutil
import subprocess
import sys

import gitq
import pgl

def do_cleanup_and_fix_series(patchdir_ref, patchdir, apply_sha, apply_name):
    """Performs cleanup and re-writing of metadata after a qpush succeeds
    """
    # Remove cache of patchdir
    os.unlink(patchdir_ref)

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

def check_am_and_maybe_die(gitam):
    """Check the status of our git-am subprocess and die appropriately if it
    failed for some reason
    """
    lines = gitam.stdout.readlines()
    failed = None
    for l in lines:
        if l.startswith('Applying: '):
            sys.stdout.write(l)
        elif l.startswith('Patch failed at '):
            failed = l
    if gitam.wait():
        if failed:
            sys.stdout.write(failed)
        else:
            sys.stdout.write('Patching failed\n')
        sys.stdout.write('When you have resolved this problem run "git qpush --resolved"\n')
        sys.stdout.write('To restore the original branch and stop pushing run "git qpush --abort"\n')
        sys.exit(1)

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Apply a popped patch',
        prog='git qpush')
    ap.add_argument('pname', help='Name of patch', default=None, nargs='?')
    ap.add_argument('-i', dest='interactive', help='Choose patch interactively',
        default=False, action='store_true')
    ap.add_argument('--resolved', dest='resolved', help='Continue paused qpush',
        default=False, action='store_true')
    ap.add_argument('--abort', dest='abort', help='Abort paused qpush',
        default=False, action='store_true')
    args = ap.parse_args()

    # Make sure we have all the config we need
    gitq.include_config()
    gitq.load_series()

    if args.abort:
        gitam = subprocess.Popen(['git', 'am', '--abort'])
        return gitam.wait()

    if args.resolved:
        gitam = subprocess.Popen(['git', 'am', '--resolved', '--reject'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        check_am_and_maybe_die(gitam)

        patchdir_ref = os.path.join(pgl.config['QUEUES'], 'applying_dir')
        patchdir = None
        with file(patchdir_ref) as f:
            patchdir = f.read()

        apply_sha = os.path.split(patchdir)[1]
        apply_name = pgl.config['NAMES'][apply_sha]

        do_cleanup_and_fix_series(patchdir_ref, patchdir, apply_sha, apply_name)

        return 0

    # Make sure we have no uncommitted changes
    if gitq.repo_has_changes():
        pgl.die('Working directory has uncommitted changes. Either qrefresh '
                'or stash them before continuing.')

    if not pgl.config['UNAPPLIED']:
        pgl.die('No patches for this branch!')

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

    # Get the list of patches to apply using git-am
    patchdir = os.path.join(pgl.config['BRANCH_QUEUE'], apply_sha)
    if not os.path.exists(patchdir):
        pgl.die('Missing patch directory for %s. Oops!' % (apply_name,))

    patches = glob.glob(os.path.join(patchdir, '*.patch'))
    if not patches:
        pgl.die('Missing patches for %s. Oops!' % (apply_name,))

    # Save our patchdir off for later use
    patchdir_ref = os.path.join(pgl.config['QUEUES'], 'applying_dir')
    with file(patchdir_ref, 'w') as f:
        f.write(patchdir)

    # Re-apply the patches
    gitamargs = ['git', 'am', '--reject']
    gitamargs.extend(patches)
    gitam = subprocess.Popen(gitamargs, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    check_am_and_maybe_die(gitam)

    do_cleanup_and_fix_series(patchdir_ref, patchdir, apply_sha, apply_name)

    return 0
