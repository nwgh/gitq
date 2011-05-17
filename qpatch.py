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
    ap = argparse.ArgumentParser(
        description='Make patches for the current queue', prog='git qpatch')
    ap.add_argument('--hg', dest='hg', help='Make an HG-style patch',
        action='store_true', default=False)
    ap.add_argument('-o', dest='outdir', help='Directory to write patches to',
        default='.')
    ap.add_argument('--nocleanup', dest='nocleanup',
        help='Do not reset to QPATCH_HEAD after creating patches',
        default=False, action='store_true')
    args = ap.parse_args()

    if gitq.repo_has_changes():
        pgl.die('Working copy has uncommitted changes. Either stash or commit '
                'them to continue')

    gitq.include_config()
    gitq.load_series()

    # Figure out our current HEAD so we can reset to it
    grp = subprocess.Popen(['git', 'rev-parse', '--verify', 'HEAD'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = grp.stdout.readlines()
    if grp.wait():
        pgl.die('Could not figure out HEAD')
    orig_head = lines[0].strip()
    if not orig_head:
        pgl.die('Could not figure out HEAD sha')

    # Set up a symbolic ref so we can get back to where we were
    gsr = subprocess.Popen(['git', 'symbolic-ref', 'QPATCH_HEAD', orig_head],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gsr.wait()

    # Squash down our patches into a sane set of patches
    base = '%s~1' % (pgl.config['SERIES'][0],)
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

    if not args.nocleanup:
        # Finally, go back to our original state
        gc = subprocess.Popen(['git', 'reset', '--hard', orig_head],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        gc.wait()

    return 0
