Requirements

Python 3.6+
requests
pyzstd


Configurations in main()

* repositories
* mirrors


Usage

python mirror_msys2.py 2> err.log

archive/: old package files
corrupt/: checksum mismatch


Using local mirror (example destdir: E:\Software\Develop\msys2)

/etc/pacman.d/mirrorlist.*

Server = file:///e/Software/Develop/msys2/msys/$arch/
Server = file:///e/Software/Develop/msys2/mingw/x86_64/
Server = file:///e/Software/Develop/msys2/mingw/ucrt64/
Server = file:///e/Software/Develop/msys2/mingw/clang64/
