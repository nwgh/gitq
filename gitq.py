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
    pgl.config['UNAPPLIED_PATCHES'] = os.path.join(pgl.config['BRANCH_QUEUE'],
        'unapplied')
    pgl.config['SHA_NAME_MAP'] = os.path.join(pgl.config['BRANCH_QUEUE'],
        'shaname')

def load_series():
    """Read queue series info from the metadata file
    """
    pgl.config['ACTIVE_PATCH'] = None
    pgl.config['SERIES'] = []
    pgl.config['UNAPPLIED'] = []
    pgl.config['NAMES'] = {}
    pgl.config['SHAS'] = {}

    with file(pgl.config['QUEUE_SERIES']) as f:
        for line in f:
            base = line.strip()
            pgl.config['SERIES'].append(base)

    if pgl.config['SERIES']:
        pgl.config['ACTIVE_PATCH'] = pgl.config['SERIES'][-1]

    with file(pgl.config['UNAPPLIED_PATCHES']) as f:
        for line in f:
            pgl.config['UNAPPLIED'].append(line.strip())

    with file(pgl.config['SHA_NAME_MAP']) as f:
        for line in f:
            sha, name = line.strip().split(' ', 1)
            pgl.config['NAMES'][sha] = name
            pgl.config['SHAS'][name] = sha

def write_series():
    """Write queue series info to the metadata file
    """
    with file(pgl.config['QUEUE_SERIES'], 'w') as f:
        for base in pgl.config['SERIES']:
            f.write('%s\n' % (base,))

    with file(pgl.config['UNAPPLIED_PATCHES'], 'w') as f:
        for base in pgl.config['UNAPPLIED']:
            f.write('%s\n' % (base,))

    with file(pgl.config['SHA_NAME_MAP'], 'w') as f:
        for sha, name in pgl.config['NAMES'].iteritems():
            f.write('%s %s\n' % (sha, name))

def repo_has_changes():
    """Return True if the working copy has uncommitted changes, False otherwise
    """
    gitstat = subprocess.Popen(['git', 'status', '--porcelain'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    status = gitstat.stdout.readlines()
    if gitstat.wait() == 0 and status:
        if any((s[0] != '#' for s in status)):
            return True
    return False

def update_patch(commit_all=False, commitmsg=None, new=False, name=None, email=None):
    """Makes sure we've committed all our changes, and write the patch series
    for this uber-patch to its patch directory
    """
    if not new:
        patchbase = pgl.config['ACTIVE_PATCH']
    else:
        patchbase = None

    # Now we can go through and make our new revision of the patch
    if patchbase and not commitmsg:
        gitlog = subprocess.Popen(['git', 'log', '-1', '--format=%s',
                                   patchbase],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        origmsg = gitlog.stdout.readlines()[0].strip()
        commitmsg = 'fixup! %s' % (origmsg,)
        gitlog.wait()

    # Can't use repo_has_changes, since that's not quite what we're looking for
    if not repo_has_changes():
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
    if gitcommit.wait():
        return False

    return True
