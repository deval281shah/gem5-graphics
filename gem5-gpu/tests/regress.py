#! /usr/bin/env python
# Copyright (c) 2005-2007 The Regents of The University of Michigan
# Copyright (c) 2014 Mark D. Hill and David A. Wood
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met: redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer;
# redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution;
# neither the name of the copyright holders nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# Author: Joel Hestness

import sys
import os
import optparse
import datetime
from subprocess import call

exec_path = os.path.basename(os.getcwd())

if exec_path != 'gem5':
    print >>sys.stderr, "ERROR: Regressions must be executed from the gem5" \
                        " subdirectory. For example:\n" \
                        "\t% cd /path/to/your/gem5-gpu/gem5\n" \
                        "\t% ../gem5-gpu/tests/regress.py"
    sys.exit(-1)

(head_path, tail_path) = os.path.split(os.path.realpath(__file__))
test_progs = os.path.join(head_path, 'test-progs')
if not os.path.exists(test_progs):
    print >>sys.stderr, "ERROR: Missing test programs, which should be at " \
                        "\'%s\'" % test_progs
    sys.exit(-1)

if os.environ.get('M5_TEST_PROGS', None) != None:
    print >>sys.stderr, "WARNING: Hijacking the M5_TEST_PROGS environment " \
                        "variable for running tests"
os.environ['M5_TEST_PROGS'] = test_progs

optparser = optparse.OptionParser()
add_option = optparser.add_option
add_option('-v', '--verbose', action='store_true', default=False,
           help='echo commands before executing')
add_option('--builds',
           default='X86_VI_hammer_GPU,' \
           'X86_MI_example_GPU,' \
           'X86_MESI_Two_Level_GPU,' \
           'X86_MOESI_hammer_GPU,' \
           'ARM_MI_example_GPU,' \
           'ARM_VI_hammer_GPU',
           help="comma-separated build build_targets to test " \
                "(default: '%default')")
add_option('--modes',
           default='se_gpu',
           help="comma-separated modes to test (default: '%default')")
add_option('--test-variants', default='opt',
           help="comma-separated build variants to test (default: '%default')"\
           ", set to '' for none")
add_option('--compile-variants', default='fast',
           help="comma-separated build variants to compile only (not test) " \
           "(default: '%default'), set to '' for none", metavar='VARIANTS')
add_option('--scons-opts', default='', metavar='OPTS',
           help='scons options')
add_option('-j', '--jobs', type='int', default=1, metavar='N',
           help='number of parallel jobs to use (0 to use all cores)')
add_option('-k', '--keep-going', action='store_true',
           help='keep going after errors')
add_option('--update-ref', action='store_true',
           help='update reference outputs')
add_option('-D', '--build-dir', default='', metavar='DIR',
           help='build directory location')
add_option('-n', "--no-exec", default=False, action='store_true',
           help="don't actually invoke scons, just echo SCons command line")

(options, tests) = optparser.parse_args()


# split a comma-separated list, but return an empty list if given the
# empty string
def split_if_nonempty(s):
    if not s:
        return []
    return s.split(',')

# split list options on ',' to get Python lists
builds = split_if_nonempty(options.builds)
modes = split_if_nonempty(options.modes)
test_variants = split_if_nonempty(options.test_variants)
compile_variants = split_if_nonempty(options.compile_variants)

options.build_dir = os.path.join(options.build_dir, 'build')

# Call os.system() and raise exception if return status is non-zero
def system(cmd, keep_going=False):
    try:
        retcode = call(cmd, shell=True)
        if retcode < 0:
            print >>sys.stderr, "Child was terminated by signal", -retcode
            print >>sys.stderr, "When attemping to execute: %s" % cmd
            if not keep_going:
                sys.exit(1)
        elif retcode > 0:
            print >>sys.stderr, "Child returned", retcode
            print >>sys.stderr, "When attemping to execute: %s" % cmd
            if not keep_going:
                sys.exit(1)
    except OSError, e:
        print >>sys.stderr, "Execution failed:", e
        print >>sys.stderr, "When attemping to execute: %s" % cmd
        if not keep_going:
            sys.exit(1)

targets = []

# start with compile-only targets, if any
if compile_variants:
    for variant in compile_variants:
        for build in builds:
            targets.append(['%s' % build, '%s/%s/gem5.%s' % (options.build_dir,
                                                             build, variant)])

# By default run the 'quick' tests, all expands to quick and long
if not tests:
    tests = ['quick']
elif 'all' in tests:
    tests = ['quick', 'long']

# set up test targets for scons, since we don't have any quick SPARC
# full-system tests exclude it
for build in builds:
    for variant in test_variants:
        for test in tests:
            for mode in modes:
                targets.append(['%s' % build, '%s/%s/tests/%s/%s/%s' %
                                              (options.build_dir, build,
                                               variant, test, mode)])

def cpu_count():
    if 'bsd' in sys.platform or sys.platform == 'darwin':
        try:
            return int(os.popen('sysctl -n hw.ncpu').read())
        except ValueError:
            pass
    else:
        try:
            return os.sysconf('SC_NPROCESSORS_ONLN')
        except (ValueError, OSError, AttributeError):
            pass

    raise NotImplementedError('cannot determine number of cpus')

scons_opts = options.scons_opts
if options.jobs != 1:
    if options.jobs == 0:
        options.jobs = cpu_count()
    scons_opts += ' -j %d' % options.jobs
if options.keep_going:
    scons_opts += ' -k'
if options.update_ref:
    scons_opts += ' --update-ref'

# We generally compile gem5.fast only to make sure it compiles OK;
# it's not very useful to run as a regression test since assertions
# are disabled.  Thus there's not much point spending time on
# link-time optimization.
scons_opts += ' --ignore-style --no-lto EXTRAS=../gem5-gpu/src:../gpgpu-sim'

from distutils.spawn import find_executable
sconsloc = find_executable('scons')

for target in targets:
    cmd = 'python %s %s --default=../../gem5-gpu/build_opts/%s %s' % \
          (sconsloc, scons_opts, target[0], target[1])
    print "Building/Running scons command: %s\n" % cmd
    if options.no_exec:
        print cmd
    else:
        system(cmd, options.keep_going)
    print "\n"

