"""Wrappers for the dependency configuration files."""

import os
import logging

import yorm

from . import common
from .shell import ShellMixin, GitMixin

log = logging.getLogger(__name__)


@yorm.attr(repo=yorm.converters.String)
@yorm.attr(dir=yorm.converters.String)
@yorm.attr(rev=yorm.converters.String)
@yorm.attr(link=yorm.converters.String)
class Source(yorm.converters.AttributeDictionary, ShellMixin, GitMixin):
    """A dictionary of `git` and `ln` arguments."""

    def __init__(self, repo, name, rev='master', link=None):
        super().__init__()
        self.repo = repo
        self.dir = name
        self.rev = rev
        self.link = link
        if not self.repo:
            raise ValueError("'repo' missing on {}".format(repr(self)))
        if not self.dir:
            raise ValueError("'dir' missing on {}".format(repr(self)))

    def __repr__(self):
        return "<source {}>".format(self)

    def __str__(self):
        fmt = "'{r}' @ '{v}' in '{d}'"
        if self.link:
            fmt += " <- '{s}'"
        return fmt.format(r=self.repo, v=self.rev, d=self.dir, s=self.link)

    def __eq__(self, other):
        return self.dir == other.dir

    def __ne__(self, other):
        return self.dir != other.dir

    def __lt__(self, other):
        return self.dir < other.dir

    def update_files(self, force=False, fetch=False, clean=True):
        """Ensure the source matches the specified revision."""
        log.info("Updating source files...")

        # Enter the working tree
        if not os.path.exists(self.dir):
            log.debug("Creating a new repository...")
            self.git_clone(self.repo, self.dir)
        self.cd(self.dir)

        # Check for uncommitted changes
        if not force:
            log.debug("Confirming there are no uncommitted changes...")
            if self.git_changes():
                common.show()
                msg = "Uncommitted changes: {}".format(os.getcwd())
                raise RuntimeError(msg)

        # Fetch the desired revision
        if fetch or self.rev not in (self.git_get_branch(),
                                     self.git_get_hash(),
                                     self.git_get_tag()):
            self.git_fetch(self.repo, self.rev)

        # Update the working tree to the desired revision
        self.git_update(self.rev, fetch=fetch, clean=clean)

    def create_link(self, root, force=False):
        """Create a link from the target name to the current directory."""
        if self.link:
            log.info("Creating a symbolic link...")
            target = os.path.join(root, self.link)
            source = os.path.relpath(os.getcwd(), os.path.dirname(target))
            if os.path.islink(target):
                os.remove(target)
            elif os.path.exists(target):
                if force:
                    self.rm(target)
                else:
                    common.show()
                    msg = "Preexisting link location: {}".format(target)
                    raise RuntimeError(msg)
            self.ln(source, target)

    def identify(self, allow_dirty=True):
        """Get the path and current repository URL and hash."""
        if os.path.isdir(self.dir):

            self.cd(self.dir)

            path = os.getcwd()
            url = self.git_get_url()
            if self.git_changes(visible=True):
                revision = '<dirty>'
                if not allow_dirty:
                    common.show()
                    msg = "Uncommitted changes: {}".format(os.getcwd())
                    raise RuntimeError(msg)
            else:
                revision = self.git_get_hash(visible=True)
            common.show(revision, log=False)

            return path, url, revision

        else:

            return os.getcwd(), '<missing>', '<unknown>'

    def lock(self):
        """Return a locked version of the current source."""
        _, _, revision = self.identify()
        source = self.__class__(self.repo, self.dir, revision, self.link)
        return source
