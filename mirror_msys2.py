import typing as ty
import contextlib
import sys
import subprocess
import os
import os.path as osp
import tarfile
import datetime
import urllib.parse as urlp
import email.utils
import hashlib
import argparse

import requests


def joinpath(path: str, *paths: str):
    return osp.join(path, *paths).replace('\\', '/')


def joinurl(path: str, *paths: str):
    return urlp.urljoin(path + '/', '/'.join(paths))


# MSYS2_ARCH = os.environ['MSYSTEM_CARCH']
MSYS2_ARCH = 'x86_64'

# MSYS2_ROOT = osp.dirname(osp.dirname(osp.dirname(
#     shutil.which('sh')))).replace('\\', '/')
MSYS2_ROOT = 'C:/msys64'

MINGW_REPO = 'mingw64'


# convert absolute paths for MSYS2
def cygpath(winpath):
    if not winpath:
        return winpath
    # strip newline at the end
    return subprocess.run(
        [joinpath(MSYS2_ROOT, 'usr/bin/cygpath.exe'), winpath],
        capture_output=True).stdout.decode('utf-8')[:-1]


GPG_BIN = joinpath(MSYS2_ROOT, 'usr/bin/gpg.exe')

GPG_HOME = cygpath(joinpath(MSYS2_ROOT, 'etc/pacman.d/gnupg'))


class Error(Exception):
    pass


class Repository:
    DESC_FIELDS_LIST = {
        'ARCH', 'CHECKDEPENDS', 'CONFLICTS', 'DEPENDS', 'GROUPS', 'LICENSE',
        'MAKEDEPENDS', 'OPTDEPENDS', 'PROVIDES', 'REPLACES'}

    DESC_FIELDS_INT = {
        'CSIZE', 'ISIZE', 'BUILDDATE'}

    def __init__(self, name: str, meta_urls: ty.List[str],
                 pkg_urls: ty.List[str], destdir: str):
        """
        :param name: Repository (database) name
        :param meta_urls: mirror URLs for the database and signatures
        :param pkg_urls: mirror URLs for the packages
        :param destdir: local directory for all the files
        """
        self.name = name
        self.meta_urls = meta_urls
        self.pkg_urls = pkg_urls
        self.destdir = destdir
        self.pkgs: ty.Optional[ty.Dict[str, ty.Dict[str, ty.Any]]] = None
        """{dirname: {key: value}} from desc files in the database"""
        self.session = requests.Session()

        os.makedirs(destdir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(self.corrupt_dir, exist_ok=True)

    @property
    def destdir(self):
        return self._destdir

    @destdir.setter
    def destdir(self, value):
        self._destdir = value
        self._destdir_cyg = cygpath(self._destdir)

    @property
    def archive_dir(self):
        return joinpath(self.destdir, 'archive')

    @property
    def corrupt_dir(self):
        return joinpath(self.destdir, 'corrupt')

    def _process_file(self, basename: str, dir_urls: ty.List[str] = None,
                      cb: ty.Callable[[ty.Optional[bytes]], None] = None):
        """
        Download/check a file *basename*. It is local if *dir_urls* is ``None``.
        Initially ``cb(None)`` then ``cb(chunk)`` for each chunk of the file.
        """
        path = joinpath(self.destdir, basename)

        if dir_urls is None:
            # check local file
            print(f'{basename} (local)', flush=True)

            with open(path, 'rb') as f:
                if cb is not None:
                    cb(None)
                    while True:
                        chunk = f.read(1048576)
                        if not chunk:
                            break
                        cb(chunk)
            return

        # download remote file
        for i, dir_url in enumerate(dir_urls):
            print(basename, end='', flush=True)
            end = '\n'
            url = joinurl(dir_url, basename)

            try:
                with contextlib.closing(self.session.get(
                        url, stream=True, timeout=30)) as resp:
                    resp.raise_for_status()

                    length = resp.headers.get('Content-Length')
                    if length is not None:
                        print(f' ({length} bytes)', flush=True)
                    if i > 0:
                        # current mirror
                        print(f' ({i+1})', flush=True)
                    end = ''

                    with open(path, 'wb') as f:
                        cb and cb(None)
                        for chunk in resp.iter_content(65536):
                            f.write(chunk)
                            cb and cb(chunk)

                    # set file date from resp
                    date = resp.headers.get('Last-Modified')
                    if date is not None:
                        # noinspection PyArgumentList
                        os.utime(path, ns=(
                            os.stat(path).st_atime_ns,
                            int(email.utils.parsedate_to_datetime(
                                date).timestamp())*(10**9)))
                    break
            except (requests.exceptions.RequestException, ConnectionError) as e:
                # retry with the next mirror
                print(end, end='', flush=True)
                print(e, file=sys.stderr, flush=True)
                continue
        else:
            raise Error(f'{basename} is unavailable in mirrors')

    def _gpg_verify(self, signame, basename, sig=None):
        """
        Verify signature *signame* for file *basename*. If *signame* is
        ``'-'`` then *sig* should be the signature in bytes.
        """
        if signame != '-':
            sigpath = joinpath(self._destdir_cyg, signame)
            gpg_input = None
        else:
            sigpath = signame
            gpg_input = sig
        path = joinpath(self._destdir_cyg, basename)

        proc = subprocess.run([
            GPG_BIN, '--homedir', GPG_HOME,
            '--verify', sigpath, path], capture_output=True,
            input=gpg_input, check=True)
        stderr = proc.stderr.decode()
        print(stderr, end='', file=sys.stderr, flush=True)
        return stderr

    @staticmethod
    def _gpg_parse_date(stderr):
        line = stderr.split('\n', maxsplit=1)[0].rstrip()
        # format depends on locale (assume default)
        return datetime.datetime.strptime(
            line, 'gpg: Signature made %a %b %d %H:%M:%S %Y').astimezone()

    def _get_file_checked(self, basename, dir_urls):
        """
        Get the file *basename* and its signature. Verify the file and check
        the timestamp in the signature.
        """
        signame = basename + '.sig'
        path = joinpath(self.destdir, basename)
        sigpath = joinpath(self.destdir, signame)

        # check the existing file, save its timestamp
        try:
            ts_old = os.stat(path).st_mtime
        except FileNotFoundError:
            ts_old = None
        else:
            # backup
            path_old = path + '.old'
            sigpath_old = sigpath + '.old'
            os.rename(path, path_old)
            os.rename(sigpath, sigpath_old)

        # get new files and verify
        self._process_file(basename, dir_urls)
        self._process_file(signame, dir_urls)

        ts = self._gpg_parse_date(self._gpg_verify(
            signame, basename)).timestamp()
        if ts_old is not None:
            if ts < ts_old:
                raise Error(f'{basename} is older than the existing file')
            else:
                # done checking
                # noinspection PyUnboundLocalVariable
                os.remove(path_old)
                # noinspection PyUnboundLocalVariable
                os.remove(sigpath_old)

    @classmethod
    def read_desc(cls, text: str):
        """parse a desc file content *text*"""
        it = iter(text.splitlines(keepends=True))
        desc = {}
        try:
            while True:
                # %KEY%
                key = next(it).rstrip()
                if not key:
                    break
                key = key[1:-1]

                # values...
                value = []
                while True:
                    v = next(it).rstrip()
                    if not v:
                        break
                    value.append(v)

                if key not in cls.DESC_FIELDS_LIST:
                    value = '\n'.join(value)
                    if key in cls.DESC_FIELDS_INT:
                        value = int(value)
                desc[key] = value
        except StopIteration:
            pass
        return desc

    def read_db(self, basename):
        """Read the repository database in .tar.gz format."""
        pkgs = {}
        with tarfile.open(joinpath(self.destdir, basename), 'r:gz') as dbfile:
            for info in dbfile:
                info: tarfile.TarInfo
                if not info.isfile():
                    continue
                dirname, basename = osp.split(info.name)
                if not basename == 'desc':
                    continue
                pkgs[dirname] = self.read_desc(
                    dbfile.extractfile(info).read().decode('utf-8'))
        return pkgs

    def refresh(self, local=False):
        """
        update :attr:`pkgs`. The remote database is downloaded if not *local*
        else the local files are used.
        """
        db = self.name + '.db'
        dbsig = db + '.sig'
        if not local:
            self._get_file_checked(db, self.meta_urls)
            self._get_file_checked(self.name + '.files', self.meta_urls)
        else:
            self._process_file(db)
            self._process_file(dbsig)
            self._gpg_verify(dbsig, db)
        self.pkgs = self.read_db(db)

    def cache(self, local=False):
        """
        Cache the package files.
        Old files are moved to ``self.destdir / archive``.
        Corrupt files are moved to ``self.destdir / corrupt``.
        If *local*, missing files are not fetched.
        """
        remote_pkgs = {desc['FILENAME']: desc for desc in self.pkgs.values()}
        local_pkgs: ty.Set[str] = set(
            entry.name for entry in os.scandir(self.destdir)
            if entry.is_file() and entry.name.endswith('.tar.xz'))

        # remove old files
        for file in local_pkgs:
            if file not in remote_pkgs:
                filesig = file + '.sig'
                os.rename(joinpath(self.destdir, file),
                          joinpath(self.archive_dir, file))
                try:
                    os.rename(joinpath(self.destdir, filesig),
                              joinpath(self.archive_dir, filesig))
                except FileNotFoundError:
                    pass

        # update and verify files
        for file, desc in remote_pkgs.items():
            # check file not in local_files
            sha256 = None

            def update(chunk):
                nonlocal sha256
                if chunk is None:
                    sha256 = hashlib.sha256()
                else:
                    sha256.update(chunk)

            try:
                self._process_file(
                    file,
                    None if local or file in local_pkgs else self.pkg_urls,
                    update)
            except (OSError, Error) as e:
                print(e, file=sys.stderr, flush=True)
                continue

            filesig = file + '.sig'
            for _ in range(1):
                if sha256.hexdigest() == desc['SHA256SUM']:
                    break

                # desc['PGPSIG'] (.sig encoded in base64) may be incorrect,
                # fetch .sig file and verify it
                try:
                    self._process_file(
                        filesig,
                        None if local or osp.exists(joinpath(self.destdir,
                                                             filesig))
                        else self.meta_urls)
                except (OSError, Error) as e:
                    print(e, file=sys.stderr, flush=True)
                    print(f'{file} could not be verified', file=sys.stderr,
                          flush=True)
                    # treat as corrupted
                    continue

                ts = self._gpg_parse_date(self._gpg_verify(
                    filesig, file)).timestamp()
                if ts >= desc['BUILDDATE']:
                    # at least later the build date
                    break
                else:
                    print(f'{file} is older than expected as in the database',
                          file=sys.stderr, flush=True)
            else:
                # corrupt
                # move fails if already exists
                os.rename(joinpath(self.destdir, file),
                          joinpath(self.corrupt_dir, file))
                try:
                    os.rename(joinpath(self.destdir, filesig),
                              joinpath(self.archive_dir, filesig))
                except FileNotFoundError:
                    pass
                print(f'{file} is corrupt', file=sys.stderr, flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Mirror MSYS2 repositories locally.')
    parser.add_argument('-l', '--local', action='store_true', default=False,
                        help='don\'t fetch missing files')
    parser.add_argument('destdir', default='.', nargs='?',
                        help='directory for repository files (default: .)')

    args = parser.parse_args()
    destdir = args.destdir
    local = args.local

    msys = Repository(
        'msys',
        ['https://sourceforge.net/projects/msys2/files/REPOS/MSYS2/'
            + MSYS2_ARCH,
         f'http://repo.msys2.org/msys/{MSYS2_ARCH}'],
        [f'https://mirror.tuna.tsinghua.edu.cn/msys2/msys/{MSYS2_ARCH}',
         f'https://mirror.yandex.ru/mirrors/msys2/msys/{MSYS2_ARCH}'],
        joinpath(destdir, f'msys/{MSYS2_ARCH}'))
    msys.pkg_urls += msys.meta_urls
    msys.refresh(local)
    msys.cache(local)

    mingw = Repository(
        MINGW_REPO,
        ['https://sourceforge.net/projects/msys2/files/REPOS/MINGW/'
            + MSYS2_ARCH,
         f'http://repo.msys2.org/mingw/{MSYS2_ARCH}'],
        [f'https://mirror.tuna.tsinghua.edu.cn/msys2/mingw/{MSYS2_ARCH}',
         f'https://mirror.yandex.ru/mirrors/msys2/mingw/{MSYS2_ARCH}'],
        joinpath(destdir, f'mingw/{MSYS2_ARCH}'))
    mingw.pkg_urls += mingw.meta_urls
    mingw.refresh(local)
    mingw.cache(local)


if __name__ == '__main__':
    main()
