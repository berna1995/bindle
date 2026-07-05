import argparse
import subprocess
import shutil
import sys
import os
from pathlib import Path

# Blacklist of core system libraries to avoid copying.
# These will be loaded from the target system natively.
CORE_BLACKLIST = {
    "libc.so",
    "libm.so",
    "libpthread.so",
    "libdl.so",
    "librt.so",
    "libgcc_s.so",
    "libstdc++.so",
    "ld-linux",
}


def resolve_library(lib_spec: str) -> Path | None:
    """Resolve a library name or path to an actual file on the system.

    If *lib_spec* is already a full path and exists, return it directly.
    Otherwise, consult ``ldconfig -p`` and fall back to searching common
    system library directories.
    """
    lib_path = Path(lib_spec)

    # If it looks like a path (absolute or contains a slash), use as-is
    if lib_path.is_absolute() or lib_path.parent != Path("."):
        return lib_path.resolve() if lib_path.exists() else None

    # Try ldconfig -p to resolve the soname
    try:
        result = subprocess.run(
            ["ldconfig", "-p"], capture_output=True, text=True, check=True
        )
        for line in result.stdout.splitlines():
            if "=>" not in line:
                continue
            parts = line.split("=>")
            path_part = parts[1].strip()
            candidate = Path(path_part)
            if candidate.name == lib_spec and candidate.exists():
                return candidate
    except subprocess.CalledProcessError:
        pass

    # Fallback: search common library paths
    for base in [
        "/usr/lib",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib/aarch64-linux-gnu",
        "/lib",
        "/lib/x86_64-linux-gnu",
        "/lib/aarch64-linux-gnu",
        "/usr/local/lib",
    ]:
        candidate = Path(base) / lib_spec
        if candidate.exists():
            return candidate

    return None


def is_pex(file_path: Path) -> bool:
    """Check if a file is a PEX (Python EXecutable) archive.

    Modern PEX files built with the 'scie' framework embed their manifest
    JSON (containing ``"scie"`` and ``"lift"`` keys) at the very end of
    the executable.  Running patchelf on such files would corrupt the
    embedded archive by modifying ELF section headers that the runtime
    uses to locate the appended zip payload.

    Detection reads at most the last 4 KiB of the file and checks for
    the presence of both ``"scie"`` and ``"lift"`` — strings that are
    unique to the scie manifest format and do not appear in regular ELFs.
    This is both O(1) in time and memory.
    """
    try:
        with open(file_path, "rb") as f:
            size = f.seek(0, os.SEEK_END)  # seek to end, get file size
            chunk_size = min(size, 4096)
            f.seek(-chunk_size, os.SEEK_END)
            tail = f.read()
            return b'"scie"' in tail and b'"lift"' in tail
    except (IOError, OSError):
        return False


def is_blacklisted(lib_name: str, blacklist: set[str]) -> bool:
    """Check if a library name starts with any string in the blacklist."""
    for item in blacklist:
        if lib_name.startswith(item):
            return True
    return False


def patch_rpath(file_path: Path, rpath: str, *, hard_fail: bool = True) -> None:
    """Set the RPATH of an ELF file using patchelf.

    When *hard_fail* is True, failures are raised as RuntimeError instead of
    emitting a warning.
    """
    try:
        subprocess.run(
            ["patchelf", "--set-rpath", rpath, str(file_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Failed to patch RPATH for {file_path}. Error: {e.stderr}"
        if hard_fail:
            raise RuntimeError(msg) from e
        print(f"Warning: {msg}", file=sys.stderr)
    except FileNotFoundError:
        print(
            "Error: 'patchelf' command not found. Please install it.", file=sys.stderr
        )
        sys.exit(1)


def _resolve_lib_dependencies(
    file_path: Path,
    lib_dir: Path,
    copied_libs: set[str],
    *,
    ld_library_path: str | None = None,
    hard_fail: bool = True,
) -> None:
    """Run ldd on *file_path* and copy its non-blacklisted dependencies.

    When *ld_library_path* is given, it is set as the ``LD_LIBRARY_PATH``
    environment variable for the ldd invocation.  This is important for
    libraries loaded via ``dlopen`` whose own dependencies may not be
    resolvable through standard system paths or RPATH.

    Already-copied names in *copied_libs* are skipped; newly copied
    libraries are added to the set and their RPATH is patched to
    ``$ORIGIN``.
    """
    env = os.environ.copy()
    if ld_library_path:
        env["LD_LIBRARY_PATH"] = ld_library_path

    try:
        result = subprocess.run(
            ["ldd", str(file_path)],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
    except subprocess.CalledProcessError:
        msg = f"ldd failed on {file_path}. Is it a valid dynamic executable?"
        if hard_fail:
            raise RuntimeError(msg)
        print(f"Warning: {msg}", file=sys.stderr)
        return

    for line in result.stdout.splitlines():
        if "=>" not in line:
            continue

        parts = line.split("=>")
        lib_path_str = parts[1].split("(")[0].strip()

        if not lib_path_str or not os.path.exists(lib_path_str):
            continue

        lib_path = Path(lib_path_str)
        lib_name = lib_path.name

        if is_blacklisted(lib_name, CORE_BLACKLIST) or lib_name in copied_libs:
            continue

        dest_lib = lib_dir / lib_name
        shutil.copy2(lib_path, dest_lib)
        copied_libs.add(lib_name)
        patch_rpath(dest_lib, "$ORIGIN", hard_fail=hard_fail)
        print(f"  -> Copied and patched library: {lib_name}")


def build_distribution(
    executables: list[str],
    dest_dir: str,
    *,
    custom_libs: list[str] | None = None,
    hard_fail: bool = True,
) -> None:
    """Package executables and their shared libraries into bin/ and lib/ dirs.

    When *hard_fail* is True, any non-fatal warning (missing executable, ldd
    failure, RPATH patching failure) is promoted to a RuntimeError and the
    command aborts immediately.
    """
    base_dest = Path(dest_dir)
    bin_dir = base_dest / "bin"
    lib_dir = base_dest / "lib"

    # Create output directory structure
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)

    copied_libs: set[str] = set()

    # --- Process custom libraries (dlopen'd at runtime) ---
    if custom_libs:
        for lib_spec in custom_libs:
            lib_path = resolve_library(lib_spec)
            if lib_path is None:
                msg = f"Custom library '{lib_spec}' not found on the system."
                if hard_fail:
                    raise RuntimeError(msg)
                print(f"Warning: {msg} Skipping.", file=sys.stderr)
                continue

            lib_name = lib_path.name

            if lib_name in copied_libs:
                continue

            # Warn if the user explicitly asked for a blacklisted lib
            if is_blacklisted(lib_name, CORE_BLACKLIST):
                print(
                    f"  -> Warning: '{lib_name}' is a core system library; "
                    f"bundling it may cause conflicts on the target system.",
                    file=sys.stderr,
                )

            dest_lib = lib_dir / lib_name
            shutil.copy2(lib_path, dest_lib)
            copied_libs.add(lib_name)
            patch_rpath(dest_lib, "$ORIGIN", hard_fail=hard_fail)
            print(f"Copied custom library: {lib_name}")

            # Also resolve and copy the custom library's own dependencies.
            # Pass the original library's directory as LD_LIBRARY_PATH so
            # sibling dependencies (not yet in the bundle) can be found.
            _resolve_lib_dependencies(
                dest_lib,
                lib_dir,
                copied_libs,
                ld_library_path=str(lib_path.parent),
                hard_fail=hard_fail,
            )

    for exe_path_str in executables:
        exe_path = Path(exe_path_str)
        if not exe_path.exists():
            msg = f"{exe_path} not found."
            if hard_fail:
                raise RuntimeError(msg)
            print(f"Warning: {msg} Skipping.", file=sys.stderr)
            continue

        # 1. Copy the executable to the bin/ directory
        dest_exe = bin_dir / exe_path.name
        shutil.copy2(exe_path, dest_exe)
        print(f"Copied executable: {exe_path.name}")

        # Check if this is a PEX archive — patchelf would corrupt it
        if is_pex(dest_exe):
            print(
                f"  -> Skipped patching: {exe_path.name} is a PEX archive (deps are self-contained)"
            )
            continue

        # Patch executable RPATH to point to the adjacent lib/ folder ($ORIGIN/../lib)
        patch_rpath(dest_exe, "$ORIGIN/../lib", hard_fail=hard_fail)

        # 2. Extract dependencies using ldd
        _resolve_lib_dependencies(dest_exe, lib_dir, copied_libs, hard_fail=hard_fail)


def main() -> None:
    """Entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Package executables and their dynamically linked libraries for distribution."
    )

    # Accept one or multiple positional arguments for executables
    parser.add_argument(
        "executables", nargs="+", help="List of executable files to package."
    )

    # Output directory via -o or --output
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Destination directory path (will be created if it does not exist).",
    )

    # Custom libraries loaded at runtime via dlopen
    parser.add_argument(
        "-l",
        "--lib",
        dest="custom_libs",
        nargs="+",
        action="extend",
        default=[],
        help="Additional shared library to include (name or path). "
        "Accepts multiple values, e.g. -l libfoo.so libbar.so. "
        "Useful for libraries loaded via dlopen at runtime. ",
    )

    # Hard-fail mode: promote all warnings to errors (default: on)
    parser.add_argument(
        "--hard-fail",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit with a non-zero status if any operation fails (missing executable, lld failure, RPATH patching error).",
    )

    args = parser.parse_args()

    print(f"Building distribution in '{args.output}'...")
    try:
        build_distribution(
            args.executables,
            args.output,
            custom_libs=args.custom_libs,
            hard_fail=args.hard_fail,
        )
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    print("\nPackaging complete!")


if __name__ == "__main__":
    main()
