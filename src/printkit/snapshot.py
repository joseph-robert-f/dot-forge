"""Bounded Linux source snapshots without following links or special files.

Every path component is opened relative to an already-open directory descriptor
with O_NOFOLLOW. A prior lstat/resolve check alone would permit link-swap races.
"""
from contextlib import contextmanager
import fnmatch
import hashlib
import os
from pathlib import Path
import stat
from .common import ForgeError

DIRECTORIES = ('src', 'schemas', 'examples', 'profiles', 'scripts', 'docs', 'tests', 'benchmarks')
ROOT_FILES = ('pyproject.toml', 'README.md', 'AGENTS.md', 'SECURITY.md', 'CONTRIBUTING.md',
              'LICENSE', 'ASSET_LICENSE.md', 'THIRD_PARTY_NOTICES.md', 'dependency-lock.json',
              'runtime-lock.json', 'upstream.lock.json')
IGNORED = ('__pycache__', '*.pyc', '*.egg-info', '*.dist-info')
MAX_BYTES = 32 * 1024 * 1024
MAX_ENTRIES = 5000
MAX_DEPTH = 64
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _reject(message):
    raise ForgeError(message, 4, 'unsafe_source_snapshot')


@contextmanager
def _directory(path):
    """Open even the root's ancestors without dereferencing a symbolic link."""
    absolute = Path(path).absolute()
    if '..' in absolute.parts:
        _reject('Source snapshot paths cannot contain parent traversal')
    fd = os.open('/', DIR_FLAGS)
    try:
        for component in absolute.parts[1:]:
            child = os.open(component, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _names(directory_fd, processed):
    names = []
    with os.scandir(directory_fd) as entries:
        for entry in entries:
            if len(names) + processed >= MAX_ENTRIES:
                _reject('Source snapshot exceeds directory enumeration budget')
            names.append(entry.name)
    return sorted(names)


def python_source_hashes(root):
    """Hash package Python source without dereferencing links before snapshotting."""
    result = {}
    counts = {'entries': 0, 'bytes': 0}
    def visit(directory_fd, prefix, depth):
        if depth > MAX_DEPTH:
            _reject('Source identity exceeds nesting budget')
        for name in _names(directory_fd, counts['entries']):
            counts['entries'] += 1
            if counts['entries'] > MAX_ENTRIES:
                _reject('Source identity exceeds entry budget')
            info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                _reject('Source identity contains a symbolic link')
            if any(fnmatch.fnmatchcase(name, pattern) for pattern in IGNORED):
                continue
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, DIR_FLAGS, dir_fd=directory_fd)
                try:
                    opened = os.fstat(child)
                    if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                        _reject('Source identity directory changed')
                    visit(child, prefix + name + '/', depth + 1)
                finally:
                    os.close(child)
            elif name.endswith('.py'):
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    _reject('Source identity contains a special or multiply-linked file')
                if counts['bytes'] + info.st_size > MAX_BYTES:
                    _reject('Source identity exceeds byte budget')
                source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=directory_fd)
                try:
                    if _identity(os.fstat(source)) != _identity(info):
                        _reject('Source identity file changed before read')
                    digest = hashlib.sha256()
                    copied = 0
                    while data := os.read(source, min(1024 * 1024, MAX_BYTES - counts['bytes'] + 1)):
                        copied += len(data); counts['bytes'] += len(data)
                        if copied > info.st_size or counts['bytes'] > MAX_BYTES:
                            _reject('Source identity file changed or exceeded budget')
                        digest.update(data)
                    if copied != info.st_size or _identity(os.fstat(source)) != _identity(info):
                        _reject('Source identity file changed during read')
                    if _identity(os.stat(name, dir_fd=directory_fd, follow_symlinks=False)) != _identity(info):
                        _reject('Source identity path changed during read')
                    result[prefix + name] = digest.hexdigest()
                finally:
                    os.close(source)
    try:
        with _directory(root) as source_fd:
            visit(source_fd, '', 0)
    except OSError as exc:
        raise ForgeError(f'Source identity refused unsafe filesystem input (errno {exc.errno})',
                         4, 'unsafe_source_snapshot') from exc
    return result


def copy_source_snapshot(root, target):
    """Copy the curated source trees; reject links before reading their bytes.

    Multi-linked regular files are conservatively rejected too, since their
    second name might be outside the reviewed source tree. Runtime caches and
    installation metadata are omitted, and nothing in the source is modified.
    """
    counts = {'entries': 0, 'bytes': 0}

    def copy_entry(source_fd, dest_fd, name, depth):
        counts['entries'] += 1
        if counts['entries'] > MAX_ENTRIES or depth > MAX_DEPTH:
            _reject('Source snapshot exceeds entry or nesting budget')
        before = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
        if stat.S_ISLNK(before.st_mode):
            _reject('Source snapshot contains a symbolic link')
        if not (stat.S_ISDIR(before.st_mode) or stat.S_ISREG(before.st_mode)):
            _reject('Source snapshot contains a special file')
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in IGNORED):
            return
        if stat.S_ISDIR(before.st_mode):
            child_fd = os.open(name, DIR_FLAGS, dir_fd=source_fd)
            try:
                opened = os.fstat(child_fd)
                if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                    _reject('Source directory changed during snapshot')
                os.mkdir(name, mode=0o755, dir_fd=dest_fd)
                target_fd = os.open(name, DIR_FLAGS, dir_fd=dest_fd)
                try:
                    for child in _names(child_fd, counts['entries']):
                        copy_entry(child_fd, target_fd, child, depth + 1)
                    after = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
                    if (after.st_dev, after.st_ino, after.st_mode) != (before.st_dev, before.st_ino, before.st_mode):
                        _reject('Source directory changed during snapshot')
                finally:
                    os.close(target_fd)
            finally:
                os.close(child_fd)
            return
        if before.st_nlink != 1:
            _reject('Source snapshot contains a multiply-linked file')
        if counts['bytes'] + before.st_size > MAX_BYTES:
            _reject('Source snapshot exceeds byte budget')
        source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=source_fd)
        try:
            if _identity(os.fstat(source)) != _identity(before):
                _reject('Source file changed before snapshot read')
            destination = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  0o755 if before.st_mode & 0o111 else 0o644, dir_fd=dest_fd)
            try:
                copied = 0
                while data := os.read(source, min(1024 * 1024, MAX_BYTES - counts['bytes'] + 1)):
                    copied += len(data)
                    counts['bytes'] += len(data)
                    if counts['bytes'] > MAX_BYTES or copied > before.st_size:
                        _reject('Source file grew beyond snapshot budget')
                    view = memoryview(data)
                    while view:
                        view = view[os.write(destination, view):]
                if copied != before.st_size or _identity(os.fstat(source)) != _identity(before):
                    _reject('Source file changed during snapshot read')
                if _identity(os.stat(name, dir_fd=source_fd, follow_symlinks=False)) != _identity(before):
                    _reject('Source file path changed during snapshot read')
            finally:
                os.close(destination)
        finally:
            os.close(source)

    try:
        with _directory(root) as source_fd, _directory(Path(target).parent) as parent_fd:
            os.mkdir(Path(target).name, mode=0o755, dir_fd=parent_fd)
            destination_fd = os.open(Path(target).name, DIR_FLAGS, dir_fd=parent_fd)
            try:
                for name in (*DIRECTORIES, *ROOT_FILES):
                    try:
                        info = os.stat(name, dir_fd=source_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        continue
                    expected = stat.S_ISDIR if name in DIRECTORIES else stat.S_ISREG
                    if not expected(info.st_mode):
                        _reject('Selected source entry has an unsafe type')
                    copy_entry(source_fd, destination_fd, name, 1)
            finally:
                os.close(destination_fd)
    except OSError as exc:
        # Do not include external path names or target contents in diagnostics.
        raise ForgeError(f'Source snapshot refused unsafe or changing filesystem input (errno {exc.errno})',
                         4, 'unsafe_source_snapshot') from exc
