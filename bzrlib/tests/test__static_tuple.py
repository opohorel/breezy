# Copyright (C) 2009 Canonical Ltd
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

"""Tests for the StaticTuple type."""

import gc
import sys

from bzrlib import (
    _static_tuple_py,
    errors,
    osutils,
    tests,
    )


def load_tests(standard_tests, module, loader):
    """Parameterize tests for all versions of groupcompress."""
    scenarios = [
        ('python', {'module': _static_tuple_py}),
    ]
    suite = loader.suiteClass()
    if CompiledStaticTuple.available():
        from bzrlib import _static_tuple_c
        scenarios.append(('C', {'module': _static_tuple_c}))
    else:
        # the compiled module isn't available, so we add a failing test
        class FailWithoutFeature(tests.TestCase):
            def test_fail(self):
                self.requireFeature(CompiledStaticTuple)
        suite.addTest(loader.loadTestsFromTestCase(FailWithoutFeature))
    result = tests.multiply_tests(standard_tests, scenarios, suite)
    return result


class _CompiledStaticTuple(tests.Feature):

    def _probe(self):
        try:
            import bzrlib._static_tuple_c
        except ImportError:
            return False
        return True

    def feature_name(self):
        return 'bzrlib._static_tuple_c'

CompiledStaticTuple = _CompiledStaticTuple()


class _Meliae(tests.Feature):

    def _probe(self):
        try:
            from meliae import scanner
        except ImportError:
            return False
        return True

    def feature_name(self):
        return "Meliae - python memory debugger"

Meliae = _Meliae()


class TestStaticTuple(tests.TestCase):

    def test_create(self):
        k = self.module.StaticTuple('foo')
        k = self.module.StaticTuple('foo', 'bar')

    def test_create_bad_args(self):
        self.assertRaises(ValueError, self.module.StaticTuple)
        lots_of_args = ['a']*300
        # too many args
        self.assertRaises(ValueError, self.module.StaticTuple, *lots_of_args)
        # not a string
        self.assertRaises(TypeError, self.module.StaticTuple, 10)
        
    def test_as_tuple(self):
        k = self.module.StaticTuple('foo')
        t = k.as_tuple()
        self.assertEqual(('foo',), t)
        k = self.module.StaticTuple('foo', 'bar')
        t = k.as_tuple()
        self.assertEqual(('foo', 'bar'), t)

    def test_len(self):
        k = self.module.StaticTuple('foo')
        self.assertEqual(1, len(k))
        k = self.module.StaticTuple('foo', 'bar')
        self.assertEqual(2, len(k))
        k = self.module.StaticTuple('foo', 'bar', 'b', 'b', 'b', 'b', 'b')
        self.assertEqual(7, len(k))

    def test_getitem(self):
        k = self.module.StaticTuple('foo', 'bar', 'b', 'b', 'b', 'b', 'z')
        self.assertEqual('foo', k[0])
        self.assertEqual('foo', k[0])
        self.assertEqual('foo', k[0])
        self.assertEqual('z', k[6])
        self.assertEqual('z', k[-1])

    def test_refcount(self):
        f = 'fo' + 'oo'
        num_refs = sys.getrefcount(f)
        k = self.module.StaticTuple(f)
        self.assertEqual(num_refs + 1, sys.getrefcount(f))
        b = k[0]
        self.assertEqual(num_refs + 2, sys.getrefcount(f))
        b = k[0]
        self.assertEqual(num_refs + 2, sys.getrefcount(f))
        c = k[0]
        self.assertEqual(num_refs + 3, sys.getrefcount(f))
        del b, c
        self.assertEqual(num_refs + 1, sys.getrefcount(f))
        del k
        self.assertEqual(num_refs, sys.getrefcount(f))

    def test__repr__(self):
        k = self.module.StaticTuple('foo', 'bar', 'baz', 'bing')
        self.assertEqual("('foo', 'bar', 'baz', 'bing')", repr(k))

    def assertCompareEqual(self, k1, k2):
        self.assertTrue(k1 == k2)
        self.assertTrue(k1 <= k2)
        self.assertTrue(k1 >= k2)
        self.assertFalse(k1 != k2)
        self.assertFalse(k1 < k2)
        self.assertFalse(k1 > k2)

    def test_compare_same_obj(self):
        k1 = self.module.StaticTuple('foo', 'bar')
        self.assertCompareEqual(k1, k1)

    def test_compare_equivalent_obj(self):
        k1 = self.module.StaticTuple('foo', 'bar')
        k2 = self.module.StaticTuple('foo', 'bar')
        self.assertCompareEqual(k1, k2)

    def test_compare_similar_obj(self):
        k1 = self.module.StaticTuple('foo' + ' bar', 'bar' + ' baz')
        k2 = self.module.StaticTuple('fo' + 'o bar', 'ba' + 'r baz')
        self.assertCompareEqual(k1, k2)

    def assertCompareDifferent(self, k_small, k_big):
        self.assertFalse(k_small == k_big)
        self.assertFalse(k_small >= k_big)
        self.assertFalse(k_small > k_big)
        self.assertTrue(k_small != k_big)
        self.assertTrue(k_small <= k_big)
        self.assertTrue(k_small < k_big)

    def test_compare_all_different_same_width(self):
        k1 = self.module.StaticTuple('baz', 'bing')
        k2 = self.module.StaticTuple('foo', 'bar')
        self.assertCompareDifferent(k1, k2)

    def test_compare_some_different(self):
        k1 = self.module.StaticTuple('foo', 'bar')
        k2 = self.module.StaticTuple('foo', 'zzz')
        self.assertCompareDifferent(k1, k2)

    def test_compare_diff_width(self):
        k1 = self.module.StaticTuple('foo')
        k2 = self.module.StaticTuple('foo', 'bar')
        self.assertCompareDifferent(k1, k2)

    def test_compare_to_tuples(self):
        k1 = self.module.StaticTuple('foo')
        self.assertCompareEqual(k1, ('foo',))
        self.assertCompareEqual(('foo',), k1)
        self.assertCompareDifferent(k1, ('foo', 'bar'))
        self.assertCompareDifferent(k1, ('foo', 10))

        k2 = self.module.StaticTuple('foo', 'bar')
        self.assertCompareEqual(k2, ('foo', 'bar'))
        self.assertCompareEqual(('foo', 'bar'), k2)
        self.assertCompareDifferent(k2, ('foo', 'zzz'))
        self.assertCompareDifferent(('foo',), k2)
        self.assertCompareDifferent(('foo', 'aaa'), k2)
        self.assertCompareDifferent(('baz', 'bing'), k2)
        self.assertCompareDifferent(('foo', 10), k2)

    def test_hash(self):
        k = self.module.StaticTuple('foo')
        self.assertEqual(hash(k), hash(('foo',)))
        k = self.module.StaticTuple('foo', 'bar', 'baz', 'bing')
        as_tuple = ('foo', 'bar', 'baz', 'bing')
        self.assertEqual(hash(k), hash(as_tuple))
        x = {k: 'foo'}
        # Because k == , it replaces the slot, rather than having both
        # present in the dict.
        self.assertEqual('foo', x[as_tuple])
        x[as_tuple] = 'bar'
        self.assertEqual({as_tuple: 'bar'}, x)

    def test_slice(self):
        k = self.module.StaticTuple('foo', 'bar', 'baz', 'bing')
        self.assertEqual(('foo', 'bar'), k[:2])
        self.assertEqual(('baz',), k[2:-1])

    def test_referents(self):
        # We implement tp_traverse so that things like 'meliae' can measure the
        # amount of referenced memory. Unfortunately gc.get_referents() first
        # checks the IS_GC flag before it traverses anything. So there isn't a
        # way to expose it that I can see.
        self.requireFeature(Meliae)
        from meliae import scanner
        strs = ['foo', 'bar', 'baz', 'bing']
        k = self.module.StaticTuple(*strs)
        if isinstance(k, _static_tuple_py.StaticTuple):
            # The python version references objects slightly different than the
            # compiled version
            self.assertEqual([k._tuple, _static_tuple_py.StaticTuple],
                             scanner.get_referents(k))
        else:
            self.assertEqual(sorted(strs), sorted(scanner.get_referents(k)))

    def test_intern(self):
        unique_str1 = 'unique str ' + osutils.rand_chars(20)
        unique_str2 = 'unique str ' + osutils.rand_chars(20)
        key = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertFalse(key in self.module._interned_keys)
        key2 = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertEqual(key, key2)
        self.assertIsNot(key, key2)
        key3 = key.intern()
        self.assertIs(key, key3)
        self.assertTrue(key in self.module._interned_keys)
        self.assertEqual(key, self.module._interned_keys[key])
        key2 = key2.intern()
        self.assertIs(key, key2)

    def test__c_intern_handles_refcount(self):
        if self.module is _static_tuple_py:
            return # Not applicable
        unique_str1 = 'unique str ' + osutils.rand_chars(20)
        unique_str2 = 'unique str ' + osutils.rand_chars(20)
        key = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertFalse(key in self.module._interned_keys)
        self.assertFalse(key._is_interned())
        key2 = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertEqual(key, key2)
        self.assertIsNot(key, key2)
        refcount = sys.getrefcount(key)
        self.assertEqual(2, refcount)

        key3 = key.intern()
        self.assertIs(key, key3)
        self.assertTrue(key in self.module._interned_keys)
        self.assertEqual(key, self.module._interned_keys[key])
        del key3
        # We should not increase the refcount just via 'intern'
        self.assertEqual(2, sys.getrefcount(key))
        self.assertTrue(key._is_interned())
        key2 = key2.intern()
        # We have one more ref in 'key2' but otherwise no extra refs
        self.assertEqual(3, sys.getrefcount(key))
        self.assertIs(key, key2)

    def test__c_keys_are_not_immortal(self):
        if self.module is _static_tuple_py:
            return # Not applicable
        unique_str1 = 'unique str ' + osutils.rand_chars(20)
        unique_str2 = 'unique str ' + osutils.rand_chars(20)
        key = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertFalse(key in self.module._interned_keys)
        self.assertEqual(2, sys.getrefcount(key))
        key = key.intern()
        self.assertEqual(2, sys.getrefcount(key))
        self.assertTrue(key in self.module._interned_keys)
        self.assertTrue(key._is_interned())
        del key
        # Create a new entry, which would point to the same location
        key = self.module.StaticTuple(unique_str1, unique_str2)
        self.assertEqual(2, sys.getrefcount(key))
        # This old entry in _interned_keys should be gone
        self.assertFalse(key in self.module._interned_keys)
        self.assertFalse(key._is_interned())
