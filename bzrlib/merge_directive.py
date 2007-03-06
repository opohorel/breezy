from email import Message
from StringIO import StringIO

from bzrlib import (
    branch as _mod_branch,
    diff,
    errors,
    gpg,
    revision as _mod_revision,
    rio,
    testament,
    timestamp,
    )
from bzrlib.bundle import serializer as bundle_serializer


class MergeDirective(object):

    _format_string = 'Bazaar merge directive format experimental-1'

    def __init__(self, revision_id, testament_sha1, time, timezone,
                 target_branch, patch=None, patch_type=None,
                 source_branch=None, message=None):
        assert patch_type in (None, 'diff', 'bundle')
        if patch_type != 'bundle' and source_branch is None:
            raise errors.NoMergeSource()
        if patch_type is not None and patch is None:
            raise errors.PatchMissing(patch_type)
        self.revision_id = revision_id
        self.testament_sha1 = testament_sha1
        self.time = time
        self.timezone = timezone
        self.target_branch = target_branch
        self.patch = patch
        self.patch_type = patch_type
        self.source_branch = source_branch
        self.message = message

    @classmethod
    def from_lines(klass, lines):
        assert lines[0].startswith('# ' + klass._format_string + '\n')
        line_iter = iter(lines[1:])
        stanza = rio.read_patch_stanza(line_iter)
        patch_lines = list(line_iter)
        if len(patch_lines) == 0:
            patch = None
        else:
            patch = ''.join(patch_lines)
        try:
            bundle_serializer.read_bundle(StringIO(patch))
        except errors.NotABundle:
            patch_type = 'diff'
        else:
            patch_type = 'bundle'
        time, timezone = timestamp.parse_patch_date(stanza.get('timestamp'))
        kwargs = {}
        for key in ('revision_id', 'testament_sha1', 'target_branch',
                    'source_branch', 'message'):
            try:
                kwargs[key] = stanza.get(key)
            except KeyError:
                pass
        return MergeDirective(time=time, timezone=timezone,
                              patch_type=patch_type, patch=patch, **kwargs)

    def to_lines(self):
        time_str = timestamp.format_patch_date(self.time, self.timezone)
        stanza = rio.Stanza(revision_id=self.revision_id, timestamp=time_str,
                            target_branch=self.target_branch,
                            testament_sha1=self.testament_sha1)
        for key in ('source_branch', 'message'):
            if self.__dict__[key] is not None:
                stanza.add(key, self.__dict__[key])
        lines = ['# ' + self._format_string + '\n']
        lines.extend(rio.to_patch_lines(stanza))
        lines.append('# \n')
        if self.patch is not None:
            lines.extend(self.patch.splitlines(True))
        return lines

    def to_signed(self, branch):
        my_gpg = gpg.GPGStrategy(branch.get_config())
        return my_gpg.sign(''.join(self.to_lines()))

    def to_email(self, mail_to, branch, sign=False):
        mail_from = branch.get_config().username()
        message = Message.Message()
        message['To'] = mail_to
        message['From'] = mail_from
        if self.message is not None:
            message['Subject'] = self.message
        else:
            revision = branch.repository.get_revision(self.revision_id)
            message['Subject'] = revision.message
        if sign:
            body = self.to_signed(branch)
        else:
            body = ''.join(self.to_lines())
        message.set_payload(body)
        return message

    @classmethod
    def from_objects(klass, repository, revision_id, time, timezone,
                 target_branch, patch_type='bundle',
                 local_target_branch=None, public_branch=None, message=None):
        t = testament.StrictTestament3.from_revision(repository, revision_id)
        if patch_type is None:
            patch = None
        else:
            submit_branch = _mod_branch.Branch.open(target_branch)
            submit_revision_id = submit_branch.last_revision()
            repository.fetch(submit_branch.repository, submit_revision_id)
            ancestor_id = _mod_revision.common_ancestor(revision_id,
                                                        submit_revision_id,
                                                        repository)
            if patch_type == 'bundle':
                s = StringIO()
                bundle_serializer.write_bundle(repository, revision_id,
                                               ancestor_id, s)
                patch = s.getvalue()
            elif patch_type == 'diff':
                patch = klass._generate_diff(repository, revision_id,
                                             ancestor_id)

            if public_branch is not None and patch_type != 'bundle':
                public_branch_obj = _mod_branch.Branch.open(public_branch)
                if not public_branch_obj.repository.has_revision(revision_id):
                    raise errors.PublicBranchOutOfDate(public_branch,
                                                       revision_id)

        return MergeDirective(revision_id, t.as_sha1(), time, timezone,
                              target_branch, patch, patch_type, public_branch,
                              message)

    @staticmethod
    def _generate_diff(repository, revision_id, ancestor_id):
        tree_1 = repository.revision_tree(ancestor_id)
        tree_2 = repository.revision_tree(revision_id)
        s = StringIO()
        diff.show_diff_trees(tree_1, tree_2, s)
        return s.getvalue()
