# Packager

**Packager** is a Linux CLI tool that bundles ELF executables together with all their dynamically-linked shared library dependencies into a portable directory structure. It resolves library paths via `ldd`, copies only the necessary `.so` files (excluding core system libraries), and patches RPATH entries using `patchelf` so the resulting bundle is self-contained and relocatable.

## How it works

1. **Copy** the given executables into `<output>/bin/`.
2. **Resolve** dependencies via `ldd` for each executable.
3. **Filter** out core system libraries (`libc.so`, `libm.so`, `libpthread.so`, etc.) — these are expected to be provided by the target system.
4. **Copy** the remaining shared libraries into `<output>/lib/`.
5. **Patch** the RPATH of each executable to `$ORIGIN/../lib` and each library to `$ORIGIN`, so the bundle is fully relocatable.

## Requirements

- **Linux** (uses `ldd` and ELF semantics)
- **Python 3.13+**
- **patchelf** — install via your system package manager:
  ```bash
  # Debian / Ubuntu
  sudo apt install patchelf

  # Fedora
  sudo dnf install patchelf

  # Arch
  sudo pacman -S patchelf
  ```

## Installation

```bash
uv tool install .
# or
pip install .
```

## Usage

```bash
packager /usr/bin/ffmpeg /usr/bin/ffprobe -o ./ffmpeg-bundle
```

This creates:

```
ffmpeg-bundle/
├── bin/
│   ├── ffmpeg
│   └── ffprobe
└── lib/
    ├── libavcodec.so.60
    ├── libavformat.so.60
    ├── libavutil.so.58
    └── ...
```

You can then copy the `ffmpeg-bundle` directory to another machine and run the executables directly — all libraries are resolved relative to the bundle.

## CLI

```
usage: packager [-h] -o OUTPUT executables [executables ...]

Package executables and their dynamically linked libraries for distribution.

positional arguments:
  executables           List of executable files to package.

options:
  -h, --help            show this help message and exit
  -o, --output OUTPUT   Destination directory path (will be created if it does not exist).
```

## Development

```bash
# Run directly via uv
uv run packager <executables> -o <output>
```

## License

MIT