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
    """
    """
    patch = pgl.config['SERIES'][pgl.config['ACTIVE_PATCH']]
    patchno = patch['order']
    patchbase = patch['base']

    # Find out what the grandparent of our new commit will be, so we can figure
    # out if we need to sqush the new commit and its parent
    grp = subprocess.Popen(['git', 'rev-parse', '--verify', 'HEAD~1'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sha = grp.stdout.readlines()[0].strip()
    grp.wait()

    if sha == patchbase:
        # The grandparent is the base of our patch, which means we need to
        # squash the new commit and the previous one. Make a commit message
        # that will make that nice and easy
        gl = subprocess.Popen(['git', 'log', '-1', '--format=%%s'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        msg = gl.stdout.readlines()[0].strip()
        gl.wait()
        commitmsg = 'fixup! %s' % (msg,)

    # Now we can go through and make our new revision of the patch
    committed = False
    gitstat = subprocess.Popen(['git', 'status', '--porcelain'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    status = gitstat.stdout.readlines()
    genv = copy.deepcopy(os.environ)
    if gitstat.wait() == 0 and status:
        have_staged = any((s[0] != ' ' for s in status))
        if not have_staged:
            if not commit_all:
                pgl.warn('No changes added to patch (use "git add" and/or '
                    '"git qnew -a")')
                return False
            files = [s.strip().split(' ', 1)[-1] for s in status]
            args = ['git', 'add'] + files
            gitadd = subprocess.Popen(args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            gitadd.wait()
        args = ['git', 'commit']
        if commitmsg:
            args += ['-m', commitmsg]
        if name:
            genv['GIT_AUTHOR_NAME'] = name
        if email:
            genv['GIT_AUTHOR_EMAIL'] = email
        gitcommit = subprocess.Popen(args, env=genv)
        gitcommit.wait()
        committed = True

    if sha == patchbase:
        # Autosquash our new commit onto our old commit
        genv['GIT_EDITOR'] = 'true'
        gri = subprocess.Popen(['git', 'rebase', '-i', '--autosquash', 'HEAD~2'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=genv)
        gri.stdout.read()
        gri.wait()

    # Write our patch to disk for safety'e sake
    with file('%04d.patch' % patchno, 'w') as f:
        if sha == patchbase:
            gitdiff = subprocess.Popen(['git', 'diff', patchbase, 'HEAD'],
                stdout=f, stderr=subprocess.PIPE)
            gitdiff.wait()

    # Write extra metadata to disk if necessary
    if name or email:
        with file('%04d.meta' % patchno, 'w') as f:
            if name:
                f.write('Name: %s' % (name,))
            if email:
                f.write('Email: %s' % (email,))

    return committed
