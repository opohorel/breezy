from unittest import TestCase

import multiparent


LINES_1 = "a\nb\nc\nd\ne\n".splitlines(True)
LINES_2 = "a\nc\nd\ne\n".splitlines(True)
LINES_3 = "a\nb\nc\nd\n".splitlines(True)


class Mock(object):

    def __init__(self, **kwargs):
        self.__dict__ = kwargs


class TestMulti(TestCase):

    def test_compare_no_parent(self):
        diff = multiparent.MultiParent.from_lines(LINES_1)
        self.assertEqual([multiparent.NewText(LINES_1)], diff.hunks)

    def test_compare_one_parent(self):
        diff = multiparent.MultiParent.from_lines(LINES_1, [LINES_2])
        self.assertEqual([multiparent.ParentText(0, 0, 0, 1),
                          multiparent.NewText(['b\n']),
                          multiparent.ParentText(0, 1, 2, 3)],
                         diff.hunks)

    def test_compare_two_parents(self):
        diff = multiparent.MultiParent.from_lines(LINES_1, [LINES_2, LINES_3])
        self.assertEqual([multiparent.ParentText(1, 0, 0, 4),
                          multiparent.ParentText(0, 3, 4, 1)],
                         diff.hunks)

    def test_eq(self):
        diff = multiparent.MultiParent.from_lines(LINES_1)
        diff2 = multiparent.MultiParent.from_lines(LINES_1)
        self.assertEqual(diff, diff2)
        diff3 = multiparent.MultiParent.from_lines(LINES_2)
        self.assertFalse(diff == diff3)
        self.assertFalse(diff == Mock(hunks=[multiparent.NewText(LINES_1)]))
        self.assertEqual(multiparent.MultiParent(
                         [multiparent.NewText(LINES_1),
                          multiparent.ParentText(0, 1, 2, 3)]),
                         multiparent.MultiParent(
                         [multiparent.NewText(LINES_1),
                          multiparent.ParentText(0, 1, 2, 3)]))

    def test_to_patch(self):
        self.assertEqual(['i 1\n', 'a\n', '\n', 'c 0 1 2 3\n'],
            list(multiparent.MultiParent([multiparent.NewText(['a\n']),
            multiparent.ParentText(0, 1, 2, 3)]).to_patch()))


class TestNewText(TestCase):

    def test_eq(self):
        self.assertEqual(multiparent.NewText([]), multiparent.NewText([]))
        self.assertFalse(multiparent.NewText(['a']) ==
                         multiparent.NewText(['b']))
        self.assertFalse(multiparent.NewText(['a']) == Mock(lines=['a']))

    def test_to_patch(self):
        self.assertEqual(['i 0\n', '\n'],
                         list(multiparent.NewText([]).to_patch()))
        self.assertEqual(['i 1\n', 'a', '\n'],
                         list(multiparent.NewText(['a']).to_patch()))
        self.assertEqual(['i 1\n', 'a\n', '\n'],
                         list(multiparent.NewText(['a\n']).to_patch()))


class TestParentText(TestCase):

    def test_eq(self):
        self.assertEqual(multiparent.ParentText(1, 2, 3, 4),
                         multiparent.ParentText(1, 2, 3, 4))
        self.assertFalse(multiparent.ParentText(1, 2, 3, 4) ==
                         multiparent.ParentText(2, 2, 3, 4))
        self.assertFalse(multiparent.ParentText(1, 2, 3, 4) ==
                         Mock(parent=1, parent_pos=2, child_pos=3,
                              num_lines=4))

    def test_to_patch(self):
        self.assertEqual(['c 0 1 2 3\n'],
                         list(multiparent.ParentText(0, 1, 2, 3).to_patch()))
