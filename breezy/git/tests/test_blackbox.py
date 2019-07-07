from ...tests.script import TestCaseWithTransportAndScript
    def test_push_without_calculate_revnos(self):
        self.run_bzr(['init', '--git', 'bla'])
        self.run_bzr(['init', '--git', 'foo'])
        self.run_bzr(['commit', '--unchanged', '-m', 'bla', 'foo'])
        output, error = self.run_bzr(
            ['push', '-Ocalculate_revnos=no', '-d', 'foo', 'bla'])
        self.assertEqual("", output)
        self.assertContainsRe(
            error,
            'Pushed up to revision id git(.*).\n')

            'All changes applied successfully.\n'
        self.assertContainsRe(output, 'revno: 1')

    def test_log_without_revno(self):
        # Smoke test for "bzr log -v" in a git repository.
        self.simple_commit()

        # Check that bzr log does not fail and includes the revision.
        output, error = self.run_bzr(['log', '-Ocalculate_revnos=no'])
        self.assertNotContainsRe(output, 'revno: 1')

    def test_commit_without_revno(self):
        repo = GitRepo.init(self.test_dir)
        output, error = self.run_bzr(
            ['commit', '-Ocalculate_revnos=yes', '--unchanged', '-m', 'one'])
        self.assertContainsRe(error, 'Committed revision 1.')
        output, error = self.run_bzr(
            ['commit', '-Ocalculate_revnos=no', '--unchanged', '-m', 'two'])
        self.assertNotContainsRe(error, 'Committed revision 2.')
        self.assertContainsRe(error, 'Committed revid .*.')
        # Some older versions of Dulwich (< 0.19.12) formatted diffs slightly
        # differently.
class SwitchScriptTests(TestCaseWithTransportAndScript):

    def test_switch_preserves(self):
        # See https://bugs.launchpad.net/brz/+bug/1820606
        self.run_script("""
$ brz init --git r
Created a standalone tree (format: git)
$ cd r
$ echo original > file.txt
$ brz add
adding file.txt
$ brz ci -q -m "Initial"
$ echo "entered on master branch" > file.txt
$ brz stat
modified:
  file.txt
$ brz switch -b other
2>Tree is up to date at revision 1.
2>Switched to branch other
$ cat file.txt
entered on master branch
""")

