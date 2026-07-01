import sys
import os
import warnings

import setuptools
from setuptools.command.build_ext import build_ext


class OptionalBuildExt(build_ext):
    def run(self):
        try:
            super().run()
        except Exception:
            pass  # warning already issued in build_extension

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as e:
            warnings.warn(
                f"\nC extension build failed: {e}\n"
                "dbdreader will fall back to the pure Python implementation, which is slower.\n",
                stacklevel=2,
            )
            # Remove the extension so the post-build copy step does not look
            # for a .so that was never created.
            self.extensions = [x for x in self.extensions if x != ext]


sources = ["extension/py_dbdreader.c",
           "extension/dbdreader.c",
           "extension/decompress.c"]
include_dirs = ['extension/include']
libraries = []


def _check_header_version(p):
    version = dict(MAJOR=0, MINOR=0, RELEASE=0)
    counter = 0
    with open(p) as fp:
        for line in fp:
            if line.startswith("#define LZ4_VERSION"):
                fields = line.strip().split()
                for k in version.keys():
                    if k in fields[1]:
                        version[k] = fields[2]
                        counter += 1
            if counter == 3:
                break
    if counter == 3:
        return ".".join((version["MAJOR"], version["MINOR"], version["RELEASE"]))
    return ""


def _version_as_int(s):
    major, minor, release = map(int, s.split('.'))
    return release + minor * 1000 + major * 1000000


def _has_lz4_header(required_version='1.7.5'):
    for d in ('/usr/include', '/usr/local/include'):
        p = os.path.join(d, 'lz4.h')
        if os.path.exists(p):
            v = _check_header_version(p)
            return v and _version_as_int(v) >= _version_as_int(required_version)
    return False


if sys.platform.startswith('linux'):
    import ctypes
    try:
        ctypes.CDLL("liblz4.so.1")
        liblz4_found = _has_lz4_header()
    except OSError:
        liblz4_found = False
else:
    liblz4_found = False

if liblz4_found:
    libraries = ['lz4']
else:
    sources += ["lz4/lz4.c"]
    include_dirs += ['lz4/include']

setuptools.setup(
    cmdclass={'build_ext': OptionalBuildExt},
    ext_modules=[
        setuptools.Extension("_dbdreader",
                             sources=sources,
                             libraries=libraries,
                             include_dirs=include_dirs,
                             library_dirs=[])
    ],
)
