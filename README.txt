Requirements

Python 3.6+
requests


Set mirrors in main()

* mirror for database
* mirror for package files


Usage

python mirror_msys2.py 2> err.log

archive/: old package files
corrupt/: checksum mismatch


Set local mirror

/etc/pacman.d/mirrorlist.*

Server = file:///e/Software/Develop/msys2/msys/$arch/
Server = file:///e/Software/Develop/msys2/mingw/x86_64/
