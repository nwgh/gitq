#!/usr/bin/env python

import os

import gitq
import pgl

@pgl.main
def main():
    gitq.include_config()
    gitq.load_series()

    os.execvp('git', ['git', 'diff', '%s~1' % (pgl.config['ACTIVE_PATCH'],)])
