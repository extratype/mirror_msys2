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

Modify `/etc/pacman.d/mirrorlist.*` in MSYS2. If the *destdir* is `E:\Software\Develop\msys2` for example,

```
Server = file:///e/Software/Develop/msys2/msys/$arch/
Server = file:///e/Software/Develop/msys2/mingw/$repo/
Server = file:///e/Software/Develop/msys2/mingw/x86_64/
Server = file:///e/Software/Develop/msys2/mingw/ucrt64/
Server = file:///e/Software/Develop/msys2/mingw/clang64/
```

Each line corresponds to one of the `mirrorlist.*` file. Replace each whitespace in a path by `%20`. Network locations can be used as well: `file:////localhost/...`.
