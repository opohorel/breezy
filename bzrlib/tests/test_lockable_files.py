# Copyright (C) 2005 by Canonical Ltd

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from bzrlib.tests import TestCaseInTempDir
from bzrlib.transport import get_transport
from bzrlib.lockable_files import LockableFiles
from bzrlib.errors import NoSuchFile, ReadOnlyError
from StringIO import StringIO

class TestLockableFiles(TestCaseInTempDir):
    def setUp(self):
        super(self.__class__, self).setUp()
        transport = get_transport('.')
        transport.mkdir('.bzr')
        transport.put('.bzr/my-lock', StringIO(''))
        self.lockable = LockableFiles(transport, 'my-lock')

    def test_read_write(self):
        self.assertRaises(NoSuchFile, self.lockable.controlfile, 'foo')
        self.lockable.lock_write()
        try:
            unicode_string = u'bar\u1234'
            self.assertEqual(4, len(unicode_string))
            byte_string = unicode_string.encode('utf-8')
            self.assertEqual(6, len(byte_string))
            self.assertRaises(UnicodeEncodeError, self.lockable.put, 'foo', 
                              StringIO(unicode_string))
            self.lockable.put('foo', StringIO(byte_string))
            self.assertEqual(byte_string,
                             self.lockable.controlfile('foo', 'rb').read())
            self.assertEqual(unicode_string,
                             self.lockable.controlfile('foo', 'r').read())
            self.lockable.put_utf8('bar', StringIO(unicode_string))
            self.assertEqual(unicode_string, 
                             self.lockable.controlfile('bar', 'r').read())
            self.assertEqual(byte_string, 
                             self.lockable.controlfile('bar', 'rb').read())
        finally:
            self.lockable.unlock()

    def test_locks(self):
        self.lockable.lock_read()
        self.lockable.unlock()
        self.assertRaises(ReadOnlyError, self.lockable.put, 'foo', 
                          StringIO('bar\u1234'))
