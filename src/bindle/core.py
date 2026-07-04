#!/usr/bin/env python3
import argparse
import subprocess
import shutil
import sys
import os
from pathlib import Path

# Blacklist of core system libraries to avoid copying.
# These will be loaded from the target system natively.
CORE_BLACKLIST = {
    'libc.so', 'libm.so', 'libpthread.so', 'libdl.so',
    'librt.so', 'libgcc_s.so', 'libstdc++.so', 'ld-linux'
}


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
        with open(file_path, 'rb') as f:
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


def patch_rpath(file_path: Path, rpath: str) -> None:
    """Set the RPATH of an ELF file using patchelf."""
    try:
        subprocess.run(
            ['patchelf', '--set-rpath', rpath, str(file_path)],
            check=True,
            capture_output=True,
            text=True
        )
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to patch RPATH for {file_path}. Error: {e.stderr}", file=sys.stderr)
    except FileNotFoundError:
        print("Error: 'patchelf' command not found. Please install it.", file=sys.stderr)
        sys.exit(1)


def build_distribution(executables: list[str], dest_dir: str) -> None:
    """Package executables and their shared libraries into bin/ and lib/ dirs."""
    base_dest = Path(dest_dir)
    bin_dir = base_dest / 'bin'
    lib_dir = base_dest / 'lib'

    # Create output directory structure
    bin_dir.mkdir(parents=True, exist_ok=True)
    lib_dir.mkdir(parents=True, exist_ok=True)

    copied_libs: set[str] = set()

    for exe_path_str in executables:
        exe_path = Path(exe_path_str)
        if not exe_path.exists():
            print(f"Warning: {exe_path} not found. Skipping.", file=sys.stderr)
            continue

        # 1. Copy the executable to the bin/ directory
        dest_exe = bin_dir / exe_path.name
        shutil.copy2(exe_path, dest_exe)
        print(f"Copied executable: {exe_path.name}")

        # Check if this is a PEX archive — patchelf would corrupt it
        if is_pex(dest_exe):
            print(f"  -> Skipped patching: {exe_path.name} is a PEX archive (deps are self-contained)")
            continue

        # Patch executable RPATH to point to the adjacent lib/ folder ($ORIGIN/../lib)
        patch_rpath(dest_exe, '$ORIGIN/../lib')

        # 2. Extract dependencies using ldd
        try:
            result = subprocess.run(['ldd', exe_path_str], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError:
            print(f"Warning: ldd failed on {exe_path_str}. Is it a valid dynamic executable?", file=sys.stderr)
            continue

        for line in result.stdout.splitlines():
            if '=>' not in line:
                continue

            parts = line.split('=>')
            lib_path_str = parts[1].split('(')[0].strip()

            # Skip if empty or path does not exist
            if not lib_path_str or not os.path.exists(lib_path_str):
                continue

            lib_path = Path(lib_path_str)
            lib_name = lib_path.name

            # Filter via blacklist and check for duplicates to optimize
            if is_blacklisted(lib_name, CORE_BLACKLIST) or lib_name in copied_libs:
                continue

            # 3. Copy the library to lib/ and mark as copied
            dest_lib = lib_dir / lib_name
            shutil.copy2(lib_path, dest_lib)
            copied_libs.add(lib_name)

            # Patch library RPATH to point to its own directory ($ORIGIN)
            # This ensures transitive dependencies are found locally.
            patch_rpath(dest_lib, '$ORIGIN')
            print(f"  -> Copied and patched library: {lib_name}")


def main() -> None:
    """Entry point for the CLI application."""
    parser = argparse.ArgumentParser(
        description="Package executables and their dynamically linked libraries for distribution."
    )

    # Accept one or multiple positional arguments for executables
    parser.add_argument(
        "executables",
        nargs="+",
        help="List of executable files to package."
    )

    # Output directory via -o or --output
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Destination directory path (will be created if it does not exist)."
    )

    args = parser.parse_args()

    print(f"Building distribution in '{args.output}'...")
    build_distribution(args.executables, args.output)
    print("\nPackaging complete!")


if __name__ == "__main__":
    main()
