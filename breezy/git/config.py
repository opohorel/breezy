# Copyright (C) 2009-2018 Jelmer Vernooij <jelmer@jelmer.uk>
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

"""Config file handling for Git."""

from __future__ import absolute_import

from .. import (
    config,
    )


class GitBranchConfig(config.BranchConfig):
    """BranchConfig that uses locations.conf in place of branch.conf"""

    def __init__(self, branch):
        super(GitBranchConfig, self).__init__(branch)
        # do not provide a BranchDataConfig
        self.option_sources = self.option_sources[0], self.option_sources[2]

    def __repr__(self):
        return "<%s of %r>" % (self.__class__.__name__, self.branch)

    def set_user_option(self, name, value, store=config.STORE_BRANCH,
                        warn_masked=False):
        """Force local to True"""
        config.BranchConfig.set_user_option(
            self, name, value, store=config.STORE_LOCATION,
            warn_masked=warn_masked)

    def _get_user_id(self):
        # TODO: Read from ~/.gitconfig
        return self._get_best_value('_get_user_id')


class GitConfigSectionDefault(config.Section):
    """The "default" config section in git config file"""

    def __init__(self, config):
        self._config = config

    def get(self, name, default=None, expand=True):
        if name == 'email':
            try:
                email = self._config.get((b'user', ), b'email')
            except KeyError:
                return None
            try:
                name = self._config.get((b'user', ), b'name')
            except KeyError:
                return email.decode()
            return '%s <%s>' % (name.decode(), email.decode())
        return None


class GitConfigStore(config.Store):
    """Store that uses gitconfig."""

    def __init__(self, config):
        self._config = config

    def get_sections(self):
        return [
            (self, GitConfigSectionDefault(self._config)),
            ]


class GitBranchStack(config._CompatibleStack):
    """GitBranch stack."""

    def __init__(self, branch):
        section_getters = [self._get_overrides]
        lstore = config.LocationStore()
        loc_matcher = config.LocationMatcher(lstore, branch.base)
        section_getters.append(loc_matcher.get_sections)
        # FIXME: This should also be looking in .git/config for
        # local git branches.
        git = getattr(branch.repository, '_git', None)
        if git:
            cstore = GitConfigStore(git.get_config())
            section_getters.append(cstore.get_sections)
        gstore = config.GlobalStore()
        section_getters.append(gstore.get_sections)
        super(GitBranchStack, self).__init__(
            section_getters,
            # All modifications go to the corresponding section in
            # locations.conf
            lstore, branch.base)
        self.branch = branch
