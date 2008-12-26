# Copyright (C) 2006 Canonical Ltd
# Authors: Robert Collins <robert.collins@canonical.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA


"""A GIT branch and repository format implementation for bzr."""

try:
    import dulwich as git
except ImportError:
    import os, sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "dulwich"))
    import dulwich as git
from bzrlib import bzrdir
from bzrlib.foreign import ForeignVcs, VcsMappingRegistry, foreign_vcs_registry
from bzrlib.plugins.git.dir import LocalGitBzrDirFormat
from bzrlib.plugins.git.remote import RemoteGitBzrDirFormat
from bzrlib.transport import register_lazy_transport

bzrdir.format_registry.register(
    'git', LocalGitBzrDirFormat,
    help='GIT repository.', 
    native=False, experimental=True,
    )

bzrdir.BzrDirFormat.register_control_format(LocalGitBzrDirFormat)
bzrdir.BzrDirFormat.register_control_format(RemoteGitBzrDirFormat)

register_lazy_transport("git://", 'bzrlib.plugins.git.remote',
                        'GitSmartTransport')


class ForeignGit(ForeignVcs):
    """Foreign Git."""


git_mapping_registry = VcsMappingRegistry()
git_mapping_registry.register_lazy('git-experimental', "bzrlib.plugins.git.mapping",
                                   "BzrGitMappingExperimental")
foreign_vcs_registry.register("git", ForeignGit(git_mapping_registry), 
                                      "Stupid content tracker")


def test_suite():
    from bzrlib.plugins.git import tests
    return tests.test_suite()
