# mirror_msys2

Mirror MSYS2 repositories locally

## Requirements

* Python 3.6+
* `pip install requests pyzstd`
* MSYS2 installation at `C:\msys64`

## Configurations

Fork and modify `main()`:

* Repositories
* Mirrors

## Usage

Only `mirror_msys2.py` is necessary to run.

`python mirror_msys2.py [destdir] 2> err.log`

Package files and metadata are downloaded in the *destdir*. By default it is the working directory.

Invoke with the same command to verify and update all.

Extra subdirectories:

* `archive/`: old package files
* `corrupt/`: package files with checksum error

## Using local mirror

Comment unused repositories like `[mingw32]` in `/etc/pacman.conf` in MSYS2.

Modify `/etc/pacman.d/mirrorlist.*`. If the *destdir* is `E:\Software\Develop\msys2` for example,

```
# mirrorlist.msys
Server = file:///e/Software/Develop/msys2/msys/$arch/

# mirrorlist.mingw
Server = file:///e/Software/Develop/msys2/mingw/$repo/
```

Replace each whitespace in a path by `%20`. Network locations can be used as well: `file:////localhost/...`.
