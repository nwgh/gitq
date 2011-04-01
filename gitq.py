import copy
import os
import subprocess

import pgl

__checked = False

def check():
    """Make sure we can do all the things we're going to want to do
    """
    if 'GIT_DIR' not in pgl.config:
        pgl.die("You don't appear to be in a git repository!")

    __checked = True

def include_config():
    """Stick our gitq-specific config in the pgl config object
    """
    if not __checked:
        check()

    grp = subprocess.Popen(['git', 'rev-parse', '--verify', 'HEAD'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sha = grp.stdout.readlines()[0].strip()
    grp.wait()

    gnr = subprocess.Popen(['git', 'name-rev', '--name-only', sha],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    branch = gnr.stdout.readlines()[0].strip()
    gnr.wait()

    sanitized_branch = branch.replace('/', '_')

    pgl.config['HEAD_SHA'] = sha
    pgl.config['BRANCH'] = branch
    pgl.config['QUEUES'] = os.path.join(pgl.config['GIT_DIR'], 'queue')
    pgl.config['BRANCH_QUEUE'] = os.path.join(pgl.config['QUEUES'],
        sanitized_branch)
    pgl.config['QUEUE_SERIES'] = os.path.join(pgl.config['BRANCH_QUEUE'],
        'series')

def load_series():
    """Read queue series info from the metadata file
    """
    pgl.config['ACTIVE_PATCH'] = None
    pgl.config['SERIES'] = {}
    pgl.config['SERIES_ORDER'] = []
    active_found = False

    with file(pgl.config['QUEUE_SERIES']) as f:
        for i, line in enumerate(f):
            aflag, base, name = line.split(' ', 2)
            pgl.config['SERIES_ORDER'].append(name)
            pgl.config['SERIES'][name] = {'base':base,
                                          'order':i,
                                          'active':False}
            if aflag == '+':
                if active_found:
                    pgl.warn('WARNING! The patch queue is malformed (2+)')
                pgl.config['ACTIVE_PATCH'] = name
                pgl.config['SERIES'][name]['active'] = True
                active_found = True

    if pgl.config['SERIES'] and not pgl.config['ACTIVE_PATCH']:
        pgl.warn('WARNING! The patch queue is malformed (0+)')

def write_series():
    """Write queue series info to the metadata file
    """
    with file(pgl.config['QUEUE_SERIES']) as f:
        for name in pgl.config['SERIES_ORDER']:
            if pgl.config['ACTIVE_PATCH'] == name:
                aflag = '+'
            else:
                aflag = '-'
            f.write('%s %s %s' %
                ('+' if pgl.config['SERIES'][name]['active'] else '-',
                 pgl.config['SERIES'][name]['base'],
                 name))

def update_patch(commit_all=False, commitmsg=None, name=None, email=None):
    """Makes sure we've committed all our changes, and write the patch series
    for this uber-patch to its patch directory
    """
    patchno = pgl.config['SERIES'][pgl.config['ACTIVE_PATCH']]['order']

    # Now we can go through and make our new revision of the patch
    committed = False
    gitstat = subprocess.Popen(['git', 'status', '--porcelain'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    status = gitstat.stdout.readlines()
    if gitstat.wait() == 0 and status:
        if not any((s[0] != '#' for s in status)):
            pgl.warn('No changes to add to patch')
            return False
        genv = copy.deepcopy(os.environ)
        args = ['git', 'commit']
        if commit_all:
            args.append('-a')
        if commitmsg:
            args += ['-m', commitmsg]
        if name:
            genv['GIT_AUTHOR_NAME'] = name
        if email:
            genv['GIT_AUTHOR_EMAIL'] = email
        gitcommit = subprocess.Popen(args, env=genv)
        gitcommit.wait()
        committed = True

    # Write our patches to disk for safety's sake
    outdir = os.path.join(pgl.config['BRANCH_QUEUE'], '%04d.mbox' % patchno)
    if not os.path.exists(outdir):
        os.mkdir(outdir)
    gfp = subprocess.Popen(['git', 'format-patch', '-o', outdir, '-n',
        patchbase], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gfp.wait()

    return committed
