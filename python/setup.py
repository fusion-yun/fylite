"""Shim that makes the wheel PLATFORM-TAGGED, and nothing else.

Everything declarative lives in `pyproject.toml`; this file exists for one
fact that PEP 621 metadata cannot state.

★The package ships a PRE-COMPILED `_lib/libfylite.so` as package data — pip
never builds it.  setuptools therefore sees no extension module, calls the
distribution pure, and stamps the wheel `py3-none-any`: a wheel that installs
happily on macOS, Windows and aarch64 and then fails at the first
`kernel.load()` with a missing-symbol or wrong-format error, i.e. AFTER the
user believes the install succeeded.  The two overrides below make the wheel
say what it actually is (`py3-none-<platform>`), so the wrong platform is a
refusal at install time — which is the whole point of a tag.

`py3-none-<plat>` rather than `cpXY-cpXY-<plat>`: the library is reached
through ctypes, so it is bound to the OS and the architecture but NOT to a
CPython ABI.  Claiming an ABI it does not have would split one usable wheel
into one per interpreter version, each a copy of the same bytes.

The concrete platform (`linux_x86_64` vs a `manylinux_2_XX_x86_64` that says
which glibc the binary really needs) is decided at build time, by
`tools/build-wheel.sh`, which reads the floor out of the `.so` instead of
asserting one here.
"""
from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.dist import Distribution


class BinaryDistribution(Distribution):
    """A distribution that carries a compiled artifact it did not compile.

    ★It is `has_ext_modules`, not `bdist_wheel.root_is_pure`, that has to
    say so.  Setting only the latter tags the wheel correctly but leaves
    `install` computing paths as pure, so every file lands under
    `<name>.data/purelib/` instead of at the wheel root — installable, but
    an unusual layout that depends on the installer handling the data tree,
    and one nobody would recognise while debugging.  Answering here makes
    the root platlib and the layout ordinary; the tag then follows for free.
    """

    def has_ext_modules(self) -> bool:
        return True


class bdist_wheel(_bdist_wheel):
    def get_tag(self):
        _python, _abi, plat = _bdist_wheel.get_tag(self)
        #: ctypes: bound to the platform, free of the CPython ABI
        return "py3", "none", plat


setup(distclass=BinaryDistribution, cmdclass={"bdist_wheel": bdist_wheel})
