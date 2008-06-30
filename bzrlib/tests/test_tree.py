# Copyright (C) 2006, 2008 Canonical Ltd
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

"""Tests for Tree and InterTree."""

from bzrlib import (
    errors,
    revision,
    tests,
    tree as _mod_tree,
    )
from bzrlib.tests import TestCaseWithTransport
from bzrlib.tree import InterTree


class TestInterTree(TestCaseWithTransport):

    def test_revision_tree_revision_tree(self):
        # we should have an InterTree registered for RevisionTree to
        # RevisionTree.
        tree = self.make_branch_and_tree('.')
        rev_id = tree.commit('first post')
        rev_id2 = tree.commit('second post', allow_pointless=True)
        rev_tree = tree.branch.repository.revision_tree(rev_id)
        rev_tree2 = tree.branch.repository.revision_tree(rev_id2)
        optimiser = InterTree.get(rev_tree, rev_tree2)
        self.assertIsInstance(optimiser, InterTree)
        optimiser = InterTree.get(rev_tree2, rev_tree)
        self.assertIsInstance(optimiser, InterTree)

    def test_working_tree_revision_tree(self):
        # we should have an InterTree available for WorkingTree to 
        # RevisionTree.
        tree = self.make_branch_and_tree('.')
        rev_id = tree.commit('first post')
        rev_tree = tree.branch.repository.revision_tree(rev_id)
        optimiser = InterTree.get(rev_tree, tree)
        self.assertIsInstance(optimiser, InterTree)
        optimiser = InterTree.get(tree, rev_tree)
        self.assertIsInstance(optimiser, InterTree)

    def test_working_tree_working_tree(self):
        # we should have an InterTree available for WorkingTree to 
        # WorkingTree.
        tree = self.make_branch_and_tree('1')
        tree2 = self.make_branch_and_tree('2')
        optimiser = InterTree.get(tree, tree2)
        self.assertIsInstance(optimiser, InterTree)
        optimiser = InterTree.get(tree2, tree)
        self.assertIsInstance(optimiser, InterTree)


class RecordingOptimiser(InterTree):

    calls = []

    def compare(self, want_unchanged=False, specific_files=None,
        extra_trees=None, require_versioned=False, include_root=False,
        want_unversioned=False):
        self.calls.append(
            ('compare', self.source, self.target, want_unchanged,
             specific_files, extra_trees, require_versioned, 
             include_root, want_unversioned)
            )
    
    @classmethod
    def is_compatible(klass, source, target):
        return True


class TestTree(TestCaseWithTransport):

    def test_compare_calls_InterTree_compare(self):
        """This test tests the way Tree.compare() uses InterTree."""
        old_optimisers = InterTree._optimisers
        try:
            InterTree._optimisers = []
            RecordingOptimiser.calls = []
            InterTree.register_optimiser(RecordingOptimiser)
            tree = self.make_branch_and_tree('1')
            tree2 = self.make_branch_and_tree('2')
            # do a series of calls:
            # trivial usage
            tree.changes_from(tree2)
            # pass in all optional arguments by position
            tree.changes_from(tree2, 'unchanged', 'specific', 'extra', 
                              'require', True)
            # pass in all optional arguments by keyword
            tree.changes_from(tree2,
                specific_files='specific',
                want_unchanged='unchanged',
                extra_trees='extra',
                require_versioned='require',
                include_root=True,
                want_unversioned=True,
                )
        finally:
            InterTree._optimisers = old_optimisers
        self.assertEqual(
            [
             ('compare', tree2, tree, False, None, None, False, False, False),
             ('compare', tree2, tree, 'unchanged', 'specific', 'extra',
              'require', True, False),
             ('compare', tree2, tree, 'unchanged', 'specific', 'extra',
              'require', True, True),
            ], RecordingOptimiser.calls)

    def test_changes_from_with_root(self):
        """Ensure the include_root option does what's expected."""
        wt = self.make_branch_and_tree('.')
        delta = wt.changes_from(wt.basis_tree())
        self.assertEqual(len(delta.added), 0)
        delta = wt.changes_from(wt.basis_tree(), wt, include_root=True)
        self.assertEqual(len(delta.added), 1)
        self.assertEqual(delta.added[0][0], '')

    def test_changes_from_with_require_versioned(self):
        """Ensure the require_versioned option does what's expected."""
        wt = self.make_branch_and_tree('.')
        self.build_tree(['known_file', 'unknown_file'])
        wt.add('known_file')

        self.assertRaises(errors.PathsNotVersionedError,
            wt.changes_from, wt.basis_tree(), wt, specific_files=['known_file',
            'unknown_file'], require_versioned=True)

        # we need to pass a known file with an unknown file to get this to
        # fail when expected.
        delta = wt.changes_from(wt.basis_tree(), wt, 
            specific_files=['known_file', 'unknown_file'] ,
            require_versioned=False)
        self.assertEqual(len(delta.added), 1)


class TestMultiWalker(TestCaseWithTransport):

    def assertStepOne(self, has_more, path, file_id, iterator):
        retval = _mod_tree.MultiWalker._step_one(iterator)
        if not has_more:
            self.assertIs(None, path)
            self.assertIs(None, file_id)
            self.assertEqual((False, None, None), retval)
        else:
            self.assertEqual((has_more, path, file_id),
                             (retval[0], retval[1], retval[2].file_id))

    def test__step_one_empty(self):
        tree = self.make_branch_and_tree('empty')
        repo = tree.branch.repository
        empty_tree = repo.revision_tree(revision.NULL_REVISION)

        iterator = empty_tree.iter_entries_by_dir()
        self.assertStepOne(False, None, None, iterator)
        self.assertStepOne(False, None, None, iterator)

    def test__step_one(self):
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/b/', 'tree/b/c'])
        tree.add(['a', 'b', 'b/c'], ['a-id', 'b-id', 'c-id'])

        iterator = tree.iter_entries_by_dir()
        tree.lock_read()
        self.addCleanup(tree.unlock)

        root_id = tree.path2id('')
        self.assertStepOne(True, '', root_id, iterator)
        self.assertStepOne(True, 'a', 'a-id', iterator)
        self.assertStepOne(True, 'b', 'b-id', iterator)
        self.assertStepOne(True, 'b/c', 'c-id', iterator)
        self.assertStepOne(False, None, None, iterator)
        self.assertStepOne(False, None, None, iterator)

    def assertWalkerNext(self, exp_path, exp_file_id, master_has_node,
                         exp_other_paths, iterator):
        """Check what happens when we step the iterator.

        :param path: The path for this entry
        :param file_id: The file_id for this entry
        :param master_has_node: Does the master tree have this entry?
        :param exp_other_paths: A list of other_path values.
        :param iterator: The iterator to step
        """
        path, file_id, master_ie, other_values = iterator.next()
        self.assertEqual((exp_path, exp_file_id), (path, file_id),
                         'Master entry did not match')
        if master_has_node:
            self.assertIsNot(None, master_ie, 'master should have an entry')
        else:
            self.assertIs(None, master_ie, 'master should not have an entry')
        self.assertEqual(len(exp_other_paths), len(other_values),
                            'Wrong number of other entries')
        for exp_other_path, (other_path, other_ie) in \
                zip(exp_other_paths, other_values):
            self.assertEqual(exp_other_path, other_path, "Other path incorrect")
            if exp_other_path is None:
                self.assertIs(None, other_ie, "Other should not have an entry")
            else:
                self.assertEqual(file_id, other_ie.file_id,
                                 "Incorrect other entry")

    def lock_and_get_basis_and_root_id(self, tree):
        tree.lock_read()
        self.addCleanup(tree.unlock)
        basis_tree = tree.basis_tree()
        basis_tree.lock_read()
        self.addCleanup(basis_tree.unlock)
        root_id = tree.path2id('')
        return basis_tree, root_id

    def test_simple_stepping(self):
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/b/', 'tree/b/c'])
        tree.add(['a', 'b', 'b/c'], ['a-id', 'b-id', 'c-id'])

        tree.commit('first', rev_id='first-rev-id')

        basis_tree, root_id = self.lock_and_get_basis_and_root_id(tree)

        walker = _mod_tree.MultiWalker(tree, [basis_tree])
        iterator = walker.iter_all()
        self.assertWalkerNext(u'', root_id, True, [u''], iterator)
        self.assertWalkerNext(u'a', 'a-id', True, [u'a'], iterator)
        self.assertWalkerNext(u'b', 'b-id', True, [u'b'], iterator)
        self.assertWalkerNext(u'b/c', 'c-id', True, [u'b/c'], iterator)
        self.assertRaises(StopIteration, iterator.next)

    def test_master_has_extra(self):
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/b/', 'tree/c', 'tree/d'])
        tree.add(['a', 'b', 'd'], ['a-id', 'b-id', 'd-id'])

        tree.commit('first', rev_id='first-rev-id')

        tree.add(['c'], ['c-id'])
        basis_tree, root_id = self.lock_and_get_basis_and_root_id(tree)

        walker = _mod_tree.MultiWalker(tree, [basis_tree])
        iterator = walker.iter_all()
        self.assertWalkerNext(u'', root_id, True, [u''], iterator)
        self.assertWalkerNext(u'a', 'a-id', True, [u'a'], iterator)
        self.assertWalkerNext(u'b', 'b-id', True, [u'b'], iterator)
        self.assertWalkerNext(u'c', 'c-id', True, [None], iterator)
        self.assertWalkerNext(u'd', 'd-id', True, [u'd'], iterator)
        self.assertRaises(StopIteration, iterator.next)

    def test_master_renamed_to_earlier(self):
        """The record is still present, it just shows up early."""
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/c', 'tree/d'])
        tree.add(['a', 'c', 'd'], ['a-id', 'c-id', 'd-id'])
        tree.commit('first', rev_id='first-rev-id')
        tree.rename_one('d', 'b')

        basis_tree, root_id = self.lock_and_get_basis_and_root_id(tree)

        walker = _mod_tree.MultiWalker(tree, [basis_tree])
        iterator = walker.iter_all()
        self.assertWalkerNext(u'', root_id, True, [u''], iterator)
        self.assertWalkerNext(u'a', 'a-id', True, [u'a'], iterator)
        self.assertWalkerNext(u'b', 'd-id', True, [u'd'], iterator)
        self.assertWalkerNext(u'c', 'c-id', True, [u'c'], iterator)
        self.assertRaises(StopIteration, iterator.next)

    def test_master_renamed_to_later(self):
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/b', 'tree/d'])
        tree.add(['a', 'b', 'd'], ['a-id', 'b-id', 'd-id'])
        tree.commit('first', rev_id='first-rev-id')
        tree.rename_one('b', 'e')

        basis_tree, root_id = self.lock_and_get_basis_and_root_id(tree)

        walker = _mod_tree.MultiWalker(tree, [basis_tree])
        iterator = walker.iter_all()
        self.assertWalkerNext(u'', root_id, True, [u''], iterator)
        self.assertWalkerNext(u'a', 'a-id', True, [u'a'], iterator)
        self.assertWalkerNext(u'd', 'd-id', True, [u'd'], iterator)
        self.assertWalkerNext(u'e', 'b-id', True, [u'b'], iterator)
        self.assertRaises(StopIteration, iterator.next)

    def test_other_extra(self):
        tree = self.make_branch_and_tree('tree')
        self.build_tree(['tree/a', 'tree/b', 'tree/d'])
        tree.add(['a', 'b', 'd'], ['a-id', 'b-id', 'd-id'])
        tree.commit('first', rev_id='first-rev-id')
        tree.remove(['b'])

        basis_tree, root_id = self.lock_and_get_basis_and_root_id(tree)
        walker = _mod_tree.MultiWalker(tree, [basis_tree])
        iterator = walker.iter_all()
        self.assertWalkerNext(u'', root_id, True, [u''], iterator)
        self.assertWalkerNext(u'a', 'a-id', True, [u'a'], iterator)
        self.assertWalkerNext(u'd', 'd-id', True, [u'd'], iterator)
        self.assertWalkerNext(u'b', 'b-id', False, [u'b'], iterator)
        self.assertRaises(StopIteration, iterator.next)
