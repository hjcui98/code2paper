"""Standalone stdlib inventory shared by isolated CLI and composition owner.

No package initialization or third-party dependency is needed by the launcher.
The development inventory wire stays byte-compatible with its original owner.
"""
import hashlib
import os
import stat
from pathlib import Path


def runtime_inventory(root: Path, *, linked_roots: tuple[Path,...] = ()) -> dict[str,dict[str,str|int]]:
    root=root.resolve(strict=True)
    allowed=tuple(path.resolve(strict=True) for path in linked_roots)
    result={}
    prefix=str(root).rstrip(os.sep)+os.sep
    for here,dirs,files in os.walk(root,followlinks=False):
        for name in sorted(dirs+files):
            # os.walk already yields absolute descendants of the resolved
            # root. Avoid reparsing each path through pathlib's relative_to.
            location=os.path.join(here,name)
            relative=location[len(prefix):]
            before=os.lstat(location)
            if stat.S_ISLNK(before.st_mode):
                target=os.readlink(location)
                resolved=Path(location).resolve(strict=True)
                local=not os.path.isabs(target) and resolved.is_relative_to(root)
                scoped=any(resolved.is_relative_to(allowed_root) for allowed_root in allowed)
                if not local and not scoped:
                    raise ValueError(f"external_or_absolute_symlink:{relative}")
                result[relative]={"link":target}
                if not local:
                    result[relative]["resolved_path"]=str(resolved)
            elif stat.S_ISREG(before.st_mode):
                with open(location,"rb") as stream: digest=hashlib.file_digest(stream,"sha256").hexdigest()
                after=os.stat(location)
                if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns) != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
                    raise ValueError(f"composition_source_unstable:{relative}")
                result[relative]={"sha256":digest,"size":after.st_size}
    return result
