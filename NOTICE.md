# Notices

PES 2021 NX is an independent, unofficial compatibility project. It is not
affiliated with or endorsed by Konami. Product names and trademarks are used
only to identify compatibility targets. No game license, game content, or
right to distribute game files is provided by this repository.

The loader and compatibility-shim structure includes MIT-licensed work by Andy
Nguyen (`TheOfficialFloW`) and `fgsfds`. Their copyright notice is preserved in
[LICENSE](LICENSE) and in the relevant source files.

Porting concepts and ideas that helped shape this project were inspired by
work shared by [NaGaa95](https://github.com/NaGaa95).

The tested compatibility target is the PES 2021 Mobile v5.3.0 offline
modification created by **Nyan Mod**. The modification and its files are not
part of this repository; the name is included for attribution and target
identification only.

This project also builds against separately distributed open-source software,
including devkitPro/libnx, Mesa, SDL2, OpenAL Soft, mpg123, and zlib. Those
projects retain their own licenses and copyrights; they are not vendored here.

`data/silent.bin` is a synthetic silent audio stream included solely as wrapper
compatibility data. `source/font_atlas.h` is a project-authored 5x7 numeric
bitmap and does not embed a third-party font.
