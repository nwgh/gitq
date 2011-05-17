#!/usr/bin/env python

import os
import subprocess
import sys

import gitq
import pgl

@pgl.main
def main():
    # Make sure we have all the config we need
    gitq.include_config()

    gitq.load_series()

    patchbase = pgl.config['ACTIVE_PATCH']

    if not patchbase:
        pgl.die('No patches for this branch!')

    # Make sure we have no uncommitted changes
    if gitq.repo_has_changes():
        pgl.die('Working copy has uncommitted stages. Either qrefresh or '
                'stash them before continuing.')

    # Write the patch to disk using format-patch
    patchdir = os.path.join(pgl.config['BRANCH_QUEUE'], patchbase)
    os.mkdir(patchdir)
    gfp = subprocess.Popen(['git', 'format-patch', '-o', patchdir,
                            '--no-signature', '-n', '--no-stat',
                            '%s~1' % (patchbase,)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if gfp.wait():
        pgl.die('Failed to pop patch')

    # Reset our working copy to before the patch
    reset_point = '%s~1' % (patchbase,)
    gitreset = subprocess.Popen(['git', 'reset', '--hard', reset_point],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gitreset.wait()

    # Move our now-saved patch into the unapplied list and save new state
    pgl.config['SERIES'] = pgl.config['SERIES'][:-1]
    pgl.config['UNAPPLIED'].append(patchbase)

    gitq.write_series()

    return 0
