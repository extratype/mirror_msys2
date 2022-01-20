# https://wiki.archlinux.org/index.php/Category:Package_management
# https://www.archlinux.org/pacman/pacman.8.html
# https://wiki.archlinux.org/index.php/Category:Arch_package_guidelines
# https://packages.msys2.org/

import typing as ty
import operator
import re
import os
import os.path as osp
import subprocess
import urllib.parse as urlp

import requests


MSYS2_ARCH = 'x86_64'

REPO_URL = 'http://repo.msys2.org'

REPO_PATHS = {
    'msys': 'msys/' + MSYS2_ARCH,
    'mingw32': 'mingw/i686',
    'mingw64': 'mingw/x86_64'}


def joinurl(path, *paths):
    return urlp.urljoin(path + '/', '/'.join(paths))


def get_pkginfo(dbpath=None):
    """
    ``LC_ALL=en_US.utf8 pacman -Si``

    Run ``pacman -Syu`` before calling this function.
    """
    args = ['pacman', '-Sii']
    if dbpath is not None:
        args += ['--dbpath', osp.abspath(dbpath).replace('\\', '/')]
    env = os.environ.copy()
    env['LC_ALL'] = 'en_US.utf8'

    cproc = subprocess.run(args, capture_output=True, check=True, env=env)
    output: str = cproc.stdout.decode('utf-8')
    return output.splitlines(keepends=True)


def read_pkginfo(pacman_si: ty.Iterable[str]):
    """Read packages information from a pacman command output."""
    it = iter(pacman_si)
    try:
        while True:
            d: ty.Dict[str, ty.Any] = {}
            k = None
            while True:
                line = next(it)
                line = line.rstrip()
                if not line:
                    # next package
                    break
                m = re.fullmatch(r'([a-zA-Z ]+?) *: (.*)', line)
                if m is not None:
                    # Name            : vim
                    # k, v = 'Name', 'vim'
                    k, v = m.groups()
                    if v == 'None':
                        v = None
                    operator.setitem(d, k, v)
                else:
                    # Optional Deps   : mingw-w64-i686-dumb: allegro_audio
                    #                   mingw-w64-i686-flac: allegro_audio
                    # v = ['mingw-w64-i686-dumb: allegro_audio',
                    #      'mingw-w64-i686-flac: allegro_audio']
                    lastv = d[k]
                    if isinstance(lastv, str):
                        d[k] = [lastv, line.strip()]
                    else:
                        lastv.append(line.strip())
            yield d
    except StopIteration:
        return


def read_index(repo):
    """read list of files in the repository"""
    dirpath = REPO_PATHS[repo]
    index_url = joinurl(REPO_URL, dirpath)
    resp = requests.get(index_url + '/', stream=True)
    resp.raise_for_status()

    for line in resp.iter_lines():
        # <a href="x86_64/">x86_64/</a>  14-Oct-2019 06:43  -
        # <a href="vim-8.1.2104-1-x86_64.pkg.tar.xz">
        # vim-8.1.2104-1-x86_64.pkg.tar.xz</a>  01-Oct-2019 05:38  7316076
        line = line.decode('utf-8').strip()
        m = re.fullmatch(
            r'<a href="(.+?)">.+?</a>\s*(.+? .+?)\s*(-|[0-9]+)', line)
        if m is None:
            continue
        link, date, size = m.groups()
        if size == '-':
            size = None
        yield joinurl(dirpath, urlp.unquote(link)), date, size


# simple way to cache all packages:
# pacman -Syu
# pacman -Sl
# pacman --dbpath ... -Sddw --needed - < ...
