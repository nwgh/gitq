#!/usr/bin/env python

import argparse
import glob
import os
import shutil
import subprocess
import sys

import gitq
import pgl

def check_am_and_maybe_die(gitam):
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
        sys.stdout.write('When you have resolved this problem run "git qcommit --resolved"\n')
        sys.stdout.write('To restore the original branch and stop pushing run "git qcommit --abort"\n')
        sys.exit(1)

def do_cleanup(patchdir, abfile):
    # Cleanup our temporary files
    shutil.rmtree(patchdir)
    os.unlink(abfile)

def do_cleanup_and_empty_series(patchdir, abfile):
    do_cleanup(patchdir, abfile)

    # These are no longer patches, so get them out of the series
    for sha in pgl.config['SERIES']:
        name = pgl.config['NAMES'][sha]
        del pgl.config['NAMES'][sha]
        del pgl.config['SHAS'][name]
    pgl.config['SERIES'] = []
    pgl.config['ACTIVE_PATCH'] = None
    gitq.write_series()

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Commit an applied queue series',
        prog='git qcommit')
    ap.add_argument('branch', help='Branch to commit to', default='master',
        nargs='?')
    ap.add_argument('--resolved', dest='resolved',
        help='Continue paused qcommit', default=False, action='store_true')
    ap.add_argument('--abort', dest='abort', help='Abort paused qcommit',
        default=False, action='store_true')
    args = ap.parse_args()

    if gitq.repo_has_changes():
        pgl.die('Working copy has changes. Stash or commit to continue.')

    gitq.include_config()
    gitq.load_series()

    patchdir = os.path.join(pgl.config['QUEUES'], 'qcommit_patches')
    abfile = os.path.join(pgl.config['QUEUES'], 'abortbranch')

    if args.abort:
        # Abort the underlying git-am
        gitam = subprocess.Popen(['git', 'am', '--abort'])
        gitam.wait()

        # Figure out our original branch was
        abortbranch = None
        with file(abfile) as f:
            abortbranch = f.read()

        # Go back to our original branch
        gc = subprocess.Popen(['git', 'checkout', '-b', abortbranch],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gc.wait()

        # Figure out what commit we were at before this mess started
        gsr = subprocess.Popen(['git', 'symbolic-ref', 'QPATCH_HEAD'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        lines = gsr.readlines()
        gsr.wait()
        sha = lines[0].strip()

        # Reset to that commit so we're back where we started
        gr = subprocess.Popen(['git', 'reset', '--hard', sha],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gr.wait()

        do_cleanup(patchdir, abfile)

        return 0

    if args.resolved:
        # Tell our underlying git-am to keep going
        gitam = subprocess.Popen(['git', 'am', '--resolved', '--reject'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        check_am_and_maybe_die(gitam)

        do_cleanup_and_empty_series(patchdir, abfile)

        return 0

    # Make sure we know where to apply our patches
    grp = subprocess.Popen(['git', 'rev-parse', '--verify', args.branch],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if grp.wait():
        pgl.die('Could not find branch %s' % (args.branch,))

    # Make sure our temporary patch location isn't already in use
    if os.path.exists(patchdir):
        gitstart = patchdir.rindex('.git')
        pgl.die("It appears that another 'git qcommit' is already in progress.\n"
                "Remove %s if that is not the case." % (patchdir[gitstart:],))

    # Figure out what branch we're on
    gb = subprocess.Popen(['git', 'branch', '--color=never', '--contains',
                           'HEAD'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = gb.stdout.readlines()
    gb.wait()
    for l in lines:
        if l.startswith('*'):
            abortbranch = l.strip().split()[-1]
            with file(abfile, 'w') as f:
                f.write(abortbranch)
            break

    # Use our patch generator to create patches for git-am
    gqp = subprocess.Popen(['git', 'qpatch', '--nocleanup', '-o', patchdir],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if gqp.wait():
        pgl.die('Error exporting patches for commit')

    # Get our list of patches to apply
    patches = glob.glob(os.path.join(patchdir, '*.patch'))

    # Go to our destination branch
    gc = subprocess.Popen(['git', 'checkout', args.branch],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gc.wait()

    # Now run git am
    gaargs = ['git', 'am', '--reject']
    gaargs.extend(patches)
    gitam = subprocess.Popen(gaargs, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    check_am_and_maybe_die(gitam)

    do_cleanup_and_empty_series(patchdir, abfile)

    return 0
