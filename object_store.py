# Copyright (C) 2009 Jelmer Vernooij <jelmer@samba.org>
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

"""Map from Git sha's to Bazaar objects."""

from dulwich.objects import (
    Blob,
    sha_to_hex,
    )
from dulwich.object_store import (
    BaseObjectStore,
    )

from bzrlib import (
    debug,
    errors,
    trace,
    ui,
    urlutils,
    )
from bzrlib.revision import (
    NULL_REVISION,
    )

from bzrlib.plugins.git.mapping import (
    default_mapping,
    directory_to_tree,
    extract_unusual_modes,
    mapping_registry,
    )
from bzrlib.plugins.git.shamap import (
    from_repository as idmap_from_repository,
    )


def get_object_store(repo, mapping=None):
    git = getattr(repo, "_git", None)
    if git is not None:
        return git.object_store
    return BazaarObjectStore(repo, mapping)


class BazaarObjectStore(BaseObjectStore):
    """A Git-style object store backed onto a Bazaar repository."""

    def __init__(self, repository, mapping=None):
        self.repository = repository
        if mapping is None:
            self.mapping = default_mapping
        else:
            self.mapping = mapping
        self._idmap = idmap_from_repository(repository)
        self.start_write_group = self._idmap.start_write_group
        self.abort_write_group = self._idmap.abort_write_group
        self.commit_write_group = self._idmap.commit_write_group

    def _update_sha_map(self, stop_revision=None):
        graph = self.repository.get_graph()
        if stop_revision is None:
            heads = graph.heads(self.repository.all_revision_ids())
        else:
            heads = set([stop_revision])
        missing_revids = self._idmap.missing_revisions(heads)
        while heads:
            parents = graph.get_parent_map(heads)
            todo = set()
            for p in parents.values():
                todo.update([x for x in p if x not in missing_revids])
            heads = self._idmap.missing_revisions(todo)
            missing_revids.update(heads)
        if NULL_REVISION in missing_revids:
            missing_revids.remove(NULL_REVISION)
        missing_revids = self.repository.has_revisions(missing_revids)
        if not missing_revids:
            return
        self.start_write_group()
        try:
            pb = ui.ui_factory.nested_progress_bar()
            try:
                for i, revid in enumerate(graph.iter_topo_order(missing_revids)):
                    trace.mutter('processing %r', revid)
                    pb.update("updating git map", i, len(missing_revids))
                    self._update_sha_map_revision(revid)
            finally:
                pb.finished()
        except:
            self.abort_write_group()
            raise
        else:
            self.commit_write_group()

    def __iter__(self):
        self._update_sha_map()
        return iter(self._idmap.sha1s())

    def _revision_to_commit(self, rev, tree_sha):
        def parent_lookup(revid):
            try:
                return self._lookup_revision_sha1(revid)
            except errors.NoSuchRevision:
                trace.warning("Ignoring ghost parent %s", revid)
                return None
        return self.mapping.export_commit(rev, tree_sha, parent_lookup)

    def _inventory_to_objects(self, inv, parent_invs, parent_invshamaps,
            unusual_modes):
        """Iterate over the objects that were introduced in a revision.

        :param inv: Inventory to process
        :param parent_invs: parent inventory SHA maps
        :param parent_invshamaps: parent inventory SHA Map
        :param unusual_modes: Unusual file modes
        :return: Yields (path, object) entries
        """
        new_trees = {}
        shamap = {}
        for path, ie in inv.entries():
            if ie.kind in ("file", "symlink"):
                for (pinv, pinvshamap) in zip(parent_invs, parent_invshamaps):
                    try:
                        pie = pinv[ie.file_id]
                    except errors.NoSuchId:
                        pass
                    else:
                        if pie.kind == ie.kind and pie.revision == ie.revision:
                            shamap[ie.file_id] = pinvshamap.lookup_blob(ie.file_id, ie.revision)
                            break
                else:
                    obj = self._get_blob(ie.file_id, ie.revision)
                    yield path, obj
                    shamap[ie.file_id] = obj.id
                    new_trees[urlutils.dirname(path)] = ie.parent_id
            elif ie.kind == "directory":
                for pinv in parent_invs:
                    try:
                        pie = pinv[ie.file_id]
                    except errors.NoSuchId:
                        pass
                    else:
                        if (pie.kind == ie.kind and 
                            pie.children.keys() == ie.children.keys()):
                            try:
                                shamap[ie.file_id] = pinvshamap.lookup_tree(ie.file_id)
                            except NotImplementedError:
                                pass
                            else:
                                break
                else:
                    new_trees[path] = ie.file_id
            else:
                raise AssertionError(ie.kind)
        for fid in unusual_modes:
            new_trees[inv.id2path(fid)] = inv[fid].parent_id
        
        trees = {}
        while new_trees:
            items = new_trees.items()
            new_trees = {}
            for path, file_id in items:
                parent_id = inv[file_id].parent_id
                if parent_id is not None:
                    parent_path = urlutils.dirname(path)
                    new_trees[parent_path] = parent_id
                trees[path] = file_id

        for path in sorted(trees.keys(), reverse=True):
            ie = inv[trees[path]]
            assert ie.kind == "directory"
            obj = directory_to_tree(ie, 
                    lambda ie: shamap[ie.file_id], unusual_modes)
            if obj is not None:
                shamap[ie.file_id] = obj.id
                yield path, obj

    def _update_sha_map_revision(self, revid):
        inv = self.repository.get_inventory(revid)
        rev = self.repository.get_revision(revid)
        unusual_modes = extract_unusual_modes(rev)
        parent_invs = self.repository.iter_inventories(rev.parent_ids)
        parent_invshamaps = [self._idmap.get_inventory_sha_map(r) for r in rev.parent_ids]
        entries = []
        tree_sha = None
        for path, obj in self._inventory_to_objects(inv, parent_invs,
                parent_invshamaps, unusual_modes):
            file_id = inv.path2id(path)
            ie = inv[file_id]
            if obj._type == "blob":
                revision = ie.revision
            else:
                revision = revid
            entries.append((file_id, obj._type, obj.id, revision))
            if path == "":
                tree_sha = obj.id
        commit_obj = self._revision_to_commit(rev, tree_sha)
        try:
            foreign_revid, mapping = mapping_registry.parse_revision_id(revid)
        except errors.InvalidRevisionId:
            pass
        else:
            if foreign_revid != commit_obj.id:
                if not "fix-shamap" in debug.debug_flags:
                    raise AssertionError("recreated git commit had different sha1: expected %s, got %s" % (foreign_revid, commit_obj.id))
        self._idmap.add_entries(revid, rev.parent_ids, commit_obj.id, 
            tree_sha, entries)
        return commit_obj.id

    def _check_expected_sha(self, expected_sha, object):
        if expected_sha is None:
            return
        if len(expected_sha) == 40:
            if expected_sha != object.sha().hexdigest():
                raise AssertionError("Invalid sha for %r: %s" % (object, expected_sha))
        elif len(expected_sha) == 20:
            if expected_sha != object.sha().digest():
                raise AssertionError("Invalid sha for %r: %s" % (object, sha_to_hex(expected_sha)))
        else:
            raise AssertionError("Unknown length %d for %r" % (len(expected_sha), expected_sha))

    def _get_ie_object(self, entry, inv, unusual_modes):
        if entry.kind == "directory":
            return self._get_tree(entry.file_id, inv.revision_id, inv,
                unusual_modes)
        elif entry.kind == "symlink":
            return self._get_blob_for_symlink(entry.symlink_target)
        elif entry.kind == "file":
            return self._get_blob_for_file(entry.file_id, entry.revision)
        else:
            raise AssertionError("unknown entry kind '%s'" % entry.kind)

    def _get_blob_for_symlink(self, symlink_target, expected_sha=None):
        """Return a Git Blob object for symlink.

        :param symlink_target: target of symlink.
        """
        if type(symlink_target) == unicode:
            symlink_target = symlink_target.encode('utf-8')
        blob = Blob()
        blob._text = symlink_target
        self._check_expected_sha(expected_sha, blob)
        return blob

    def _get_blob_for_file(self, fileid, revision, expected_sha=None):
        """Return a Git Blob object from a fileid and revision stored in bzr.

        :param fileid: File id of the text
        :param revision: Revision of the text
        """
        blob = Blob()
        chunks = self.repository.iter_files_bytes([(fileid, revision, None)]).next()[1]
        blob._text = "".join(chunks)
        self._check_expected_sha(expected_sha, blob)
        return blob

    def _get_blob(self, fileid, revision, expected_sha=None):
        """Return a Git Blob object from a fileid and revision stored in bzr.

        :param fileid: File id of the text
        :param revision: Revision of the text
        """
        inv = self.repository.get_inventory(revision)
        entry = inv[fileid]

        if entry.kind == 'file':
            return self._get_blob_for_file(entry.file_id, entry.revision,
                                           expected_sha=expected_sha)
        elif entry.kind == 'symlink':
            return self._get_blob_for_symlink(entry.symlink_target,
                                              expected_sha=expected_sha)
        else:
            raise AssertionError

    def _get_tree(self, fileid, revid, inv, unusual_modes, expected_sha=None):
        """Return a Git Tree object from a file id and a revision stored in bzr.

        :param fileid: fileid in the tree.
        :param revision: Revision of the tree.
        """
        invshamap = self._idmap.get_inventory_sha_map(inv.revision_id)
        def get_ie_sha1(entry):
            if entry.kind == "directory":
                return invshamap.lookup_tree(entry.file_id)
            elif entry.kind in ("file", "symlink"):
                return invshamap.lookup_blob(entry.file_id, entry.revision)
            else:
                raise AssertionError("unknown entry kind '%s'" % entry.kind)
        tree = directory_to_tree(inv[fileid], get_ie_sha1, unusual_modes)
        self._check_expected_sha(expected_sha, tree)
        return tree

    def _get_commit(self, rev, tree_sha, expected_sha=None):
        commit = self._revision_to_commit(rev, tree_sha)
        self._check_expected_sha(expected_sha, commit)
        return commit

    def get_parents(self, sha):
        """Retrieve the parents of a Git commit by SHA1.

        :param sha: SHA1 of the commit
        :raises: KeyError, NotCommitError
        """
        return self[sha].parents

    def _lookup_revision_sha1(self, revid):
        """Return the SHA1 matching a Bazaar revision."""
        if revid == NULL_REVISION:
            return "0" * 40
        try:
            return self._idmap.lookup_commit(revid)
        except KeyError:
            try:
                return mapping_registry.parse_revision_id(revid)[0]
            except errors.InvalidRevisionId:
                self._update_sha_map(revid)
                return self._idmap.lookup_commit(revid)

    def get_raw(self, sha):
        """Get the raw representation of a Git object by SHA1.

        :param sha: SHA1 of the git object
        """
        obj = self[sha]
        return (obj.type, obj.as_raw_string())

    def __contains__(self, sha):
        # See if sha is in map
        try:
            (type, type_data) = self._lookup_git_sha(sha)
            if type == "commit":
                return self.repository.has_revision(type_data[0])
            elif type == "blob":
                return self.repository.texts.has_version(type_data)
            elif type == "tree":
                return self.repository.has_revision(type_data[1])
            else:
                raise AssertionError("Unknown object type '%s'" % type)
        except KeyError:
            return False

    def _lookup_git_sha(self, sha):
        # See if sha is in map
        try:
            return self._idmap.lookup_git_sha(sha)
        except KeyError:
            # if not, see if there are any unconverted revisions and add them
            # to the map, search for sha in map again
            self._update_sha_map()
            return self._idmap.lookup_git_sha(sha)

    def __getitem__(self, sha):
        (type, type_data) = self._lookup_git_sha(sha)
        # convert object to git object
        if type == "commit":
            try:
                rev = self.repository.get_revision(type_data[0])
            except errors.NoSuchRevision:
                trace.mutter('entry for %s %s in shamap: %r, but not found in repository', type, sha, type_data)
                raise KeyError(sha)
            return self._get_commit(rev, type_data[1], expected_sha=sha)
        elif type == "blob":
            return self._get_blob(type_data[0], type_data[1], expected_sha=sha)
        elif type == "tree":
            try:
                inv = self.repository.get_inventory(type_data[1])
                rev = self.repository.get_revision(type_data[1])
            except errors.NoSuchRevision:
                trace.mutter('entry for %s %s in shamap: %r, but not found in repository', type, sha, type_data)
                raise KeyError(sha)
            unusual_modes = extract_unusual_modes(rev)
            try:
                return self._get_tree(type_data[0], type_data[1], inv,
                    unusual_modes, expected_sha=sha)
            except errors.NoSuchRevision:
                raise KeyError(sha)
        else:
            raise AssertionError("Unknown object type '%s'" % type)
