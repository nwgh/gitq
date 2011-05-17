#!/usr/bin/env python

import argparse
import copy
import email
import email.iterators
import os
import re
import subprocess
import sys

import gitq
import pgl

subjre = re.compile('\\[[^\\]]+\\] ')

def hgify(f):
    """Given a file-like object that is the output of git format-patch, turn
    that into the kind of patch that hg expects with its special headers and
    such.
    """
    msg = email.message_from_file(f)
    body = email.iterators.body_line_iterator(msg)
    yield 'From: %s\n' % msg['From']
    yield '\n'
    yield '%s\n' % subjre.sub('', msg['Subject']).replace('\n', ' ')
    for line in body:
        if line.startswith('index '):
            continue
        yield line

@pgl.main
def main():
    ap = argparse.ArgumentParser(description='Make patches for the current queue',
        prog='git qpatch')
    ap.add_argument('--hg', dest='hg', help='Make an HG-style patch',
        action='store_true', default=False)
    ap.add_argument('-o', dest='outdir', help='Directory to write patches to',
        default='.')
    ap.add_argument('base', help='Branch to base on', nargs='?',
        default='master')
    args = ap.parse_args()

    if gitq.repo_has_changes():
        pgl.die('Working copy has uncommitted changes. Either stash or commit '
                'them to continue')

    # Figure out our current HEAD so we can reset to it
    grp = subprocess.Popen(['git', 'rev-parse', '--verify', 'HEAD'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = grp.stdout.readlines()
    if grp.wait():
        pgl.die('Could not figure out HEAD')
    orig_head = lines[0].strip()
    if not orig_head:
        pgl.die('Could not figure out HEAD sha')

    # Figure out the branch name corresponding to our current HEAD
    gb = subprocess.Popen(['git', 'branch', '--no-color', '--contains',
                           orig_head],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = gb.stdout.readlines()
    if gb.wait() or not lines[0].strip():
        pgl.die('Could not figure out current branch')
    orig_branch = lines[0].strip().split()[-1]

    # Figure out where to apply our patches
    gmb = subprocess.Popen(['git', 'merge-base', args.base, orig_head],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = gmb.stdout.readlines()
    if gmb.wait():
        pgl.die('Could not figure out merge-base for %s and HEAD' % (args.base,))
    base = lines[0].strip()
    if not base:
        pgl.die('Could not figure out base to make patches from')

    # Move to our detatched head
    gc = subprocess.Popen(['git', 'checkout', base], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    if gc.wait():
        pgl.die('Error creating patches: noco')

    # Apply the patches
    gcp = subprocess.Popen(['git', 'cherry-pick', '..%s' % (orig_branch,)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gcp.wait()

    # Squash them down
    grenv = copy.deepcopy(os.environ)
    grenv['GIT_EDITOR'] = 'true'
    gr = subprocess.Popen(['git', 'rebase', '-i', '--autosquash', base],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=grenv)
    gr.wait()

    # Use format-patch to make the patches
    gfpargs = ['git', 'format-patch', '-n']
    if args.hg:
        gfpargs.extend(['--no-signature', '--no-stat'])
    if args.outdir != '.':
        gfpargs.extend(['-o', args.outdir])
    gfpargs.append(base)
    gfp = subprocess.Popen(gfpargs, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    patches = gfp.stdout.readlines()
    gfp.wait()

    # Make into hg-style patches if necessary
    if args.hg:
        for patch in patches:
            # Write out to a temporary file
            fname = patch.strip()
            fname_out = '%s.temp' % (fname,)
            fin = file(fname)
            fout = file(fname_out, 'w')
            fout.writelines(hgify(fin))
            fin.close()
            fout.close()

            # And move the temp file into place
            os.unlink(fname)
            os.rename(fname_out, fname)

    # Finally, go back to our original branch
    gc = subprocess.Popen(['git', 'checkout', orig_branch],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gc.wait()

    return 0
