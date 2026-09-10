#!/usr/bin/env python3
"""Generate syzkaller syzlang descriptions for the Linux ppdev (parallel port) driver.

This script produces:
  - dev_ppdev.txt: Syzlang syscall/ioctl descriptions
  - dev_ppdev.txt.const: Architecture-specific constant values for amd64 and 386

Key references:
  - linux/uapi/linux/ppdev.h: ioctl definitions, ppdev_frob_struct, PP_* flags
  - linux/uapi/linux/parport.h: IEEE1284_MODE_* constants
  - Syzkaller docs: docs/syscall_descriptions.md, docs/syscall_descriptions_syntax.md
"""

import os
import sys


# =============================================================================
# IOCTL number computation (x86 _IOC encoding)
# =============================================================================
# On x86 (both amd64 and 386):
#   _IOC(dir, type, nr, size) = (dir << 30) | (size << 16) | (type << 8) | nr
# Direction bits: _IOC_NONE=0, _IOC_WRITE=1, _IOC_READ=2

def compute_IO(type_char, nr):
    """Compute _IO(type, nr) — no direction, no size."""
    return (ord(type_char) << 8) | nr


def compute_IOR(type_char, nr, size):
    """Compute _IOR(type, nr, size) — kernel reads out to user."""
    return (2 << 30) | (size << 16) | (ord(type_char) << 8) | nr


def compute_IOW(type_char, nr, size):
    """Compute _IOW(type, nr, size) — user writes in to kernel."""
    return (1 << 30) | (size << 16) | (ord(type_char) << 8) | nr


def compute_ioctl_value(macro, nr, size):
    """Compute the 32-bit ioctl command number for ppdev (type='p'=0x70)."""
    TYPE_CHAR = 'p'  # ppdev magic character
    if macro == '_IO':
        return compute_IO(TYPE_CHAR, nr)
    elif macro == '_IOR':
        return compute_IOR(TYPE_CHAR, nr, size)
    elif macro == '_IOW':
        return compute_IOW(TYPE_CHAR, nr, size)
    else:
        raise ValueError(f"Unknown ioctl macro type: {macro}")


# =============================================================================
# IOCTL definitions — all 28 ppdev ioctls
# =============================================================================
# Each entry: (name, macro_type, sequence_nr, c_arg_type_description, size_amd64, size_386)
# size_amd64 and size_386 differ only for struct timeval:
#   amd64: sizeof(struct timeval) = 16 (two 8-byte longs)
#   386:   sizeof(struct timeval) = 8  (two 4-byte longs)

# Type sizes (in bytes)
INT = 4
UCHAR = 1
UINT = 4
FROB = 2  # struct ppdev_frob_struct: two unsigned chars
TIMEVAL_AMD64 = 16
TIMEVAL_386 = 8


def get_ioctl_definitions():
    """Return all 28 ppdev ioctl definitions including 5 obsolete ones.

    Returns list of tuples:
        (name, macro, nr, c_type_desc, size_amd64, size_386)

    The 5 obsolete ioctls (PPWSTATUS, PPRECONTROL, PPWECONTROL, PPRFIFO, PPWFIFO)
    use OBSOLETE__IOW / OBSOLETE__IOR in the kernel header but compute identically
    to standard _IOW/_IOR. They must be included for complete fuzzing coverage.
    """
    return [
        # name            macro   nr    c_type                      sz_amd64  sz_386
        ('PPSETMODE',     '_IOW', 0x80, 'int',                      INT,      INT),
        ('PPRSTATUS',     '_IOR', 0x81, 'unsigned char',             UCHAR,    UCHAR),
        ('PPWSTATUS',     '_IOW', 0x82, 'unsigned char',             UCHAR,    UCHAR),      # obsolete
        ('PPRCONTROL',    '_IOR', 0x83, 'unsigned char',             UCHAR,    UCHAR),
        ('PPWCONTROL',    '_IOW', 0x84, 'unsigned char',             UCHAR,    UCHAR),
        ('PPRDATA',       '_IOR', 0x85, 'unsigned char',             UCHAR,    UCHAR),
        ('PPWDATA',       '_IOW', 0x86, 'unsigned char',             UCHAR,    UCHAR),
        ('PPRECONTROL',   '_IOR', 0x87, 'unsigned char',             UCHAR,    UCHAR),      # obsolete
        ('PPWECONTROL',   '_IOW', 0x88, 'unsigned char',             UCHAR,    UCHAR),      # obsolete
        ('PPRFIFO',       '_IOR', 0x89, 'unsigned char',             UCHAR,    UCHAR),      # obsolete
        ('PPWFIFO',       '_IOW', 0x8a, 'unsigned char',             UCHAR,    UCHAR),      # obsolete
        ('PPCLAIM',       '_IO',  0x8b, None,                        0,        0),
        ('PPRELEASE',     '_IO',  0x8c, None,                        0,        0),
        ('PPYIELD',       '_IO',  0x8d, None,                        0,        0),
        ('PPFCONTROL',    '_IOW', 0x8e, 'struct ppdev_frob_struct',  FROB,     FROB),
        ('PPEXCL',        '_IO',  0x8f, None,                        0,        0),
        ('PPDATADIR',     '_IOW', 0x90, 'int',                       INT,      INT),
        ('PPNEGOT',       '_IOW', 0x91, 'int',                       INT,      INT),
        ('PPWCTLONIRQ',   '_IOW', 0x92, 'unsigned char',             UCHAR,    UCHAR),
        ('PPCLRIRQ',      '_IOR', 0x93, 'int',                       INT,      INT),
        ('PPSETPHASE',    '_IOW', 0x94, 'int',                       INT,      INT),
        ('PPGETTIME',     '_IOR', 0x95, 'struct timeval',            TIMEVAL_AMD64, TIMEVAL_386),
        ('PPSETTIME',     '_IOW', 0x96, 'struct timeval',            TIMEVAL_AMD64, TIMEVAL_386),
        ('PPGETMODES',    '_IOR', 0x97, 'unsigned int',              UINT,     UINT),
        ('PPGETMODE',     '_IOR', 0x98, 'int',                       INT,      INT),
        ('PPGETPHASE',    '_IOR', 0x99, 'int',                       INT,      INT),
        ('PPGETFLAGS',    '_IOR', 0x9a, 'int',                       INT,      INT),
        ('PPSETFLAGS',    '_IOW', 0x9b, 'int',                       INT,      INT),
    ]


# =============================================================================
# Flag / constant definitions
# =============================================================================

def get_ieee1284_flags():
    """IEEE 1284 mode constants from linux/parport.h.

    These are used by PPSETMODE, PPNEGOT, PPGETMODE, PPGETMODES ioctls.
    """
    return [
        ('IEEE1284_MODE_NIBBLE',  0),
        ('IEEE1284_MODE_BYTE',    1 << 0),    # 1
        ('IEEE1284_MODE_COMPAT',  1 << 8),    # 256
        ('IEEE1284_MODE_BECP',    1 << 9),    # 512
        ('IEEE1284_MODE_ECP',     1 << 4),    # 16
        ('IEEE1284_MODE_ECPRLE',  (1 << 4) | (1 << 5)),  # 48
        ('IEEE1284_MODE_ECPSWE',  1 << 10),   # 1024
        ('IEEE1284_MODE_EPP',     1 << 6),    # 64
        ('IEEE1284_MODE_EPPSL',   1 << 11),   # 2048
        ('IEEE1284_MODE_EPPSWE',  1 << 12),   # 4096
        ('IEEE1284_DEVICEID',     1 << 2),    # 4
        ('IEEE1284_EXT_LINK',     1 << 14),   # 16384
    ]


def get_ppdev_flags():
    """PP driver flags from linux/ppdev.h, used by PPSETFLAGS/PPGETFLAGS."""
    return [
        ('PP_FASTWRITE',  1 << 2),   # 4
        ('PP_FASTREAD',   1 << 3),   # 8
        ('PP_W91284PIC',  1 << 4),   # 16
    ]


# =============================================================================
# Syzlang type mapping
# =============================================================================

def get_syz_type(ioctl_name, c_type, direction):
    """Map a C argument type to the appropriate syzlang type expression.

    Args:
        ioctl_name: The ioctl constant name (e.g., 'PPSETMODE')
        c_type: The C type string (e.g., 'int', 'unsigned char')
        direction: 'in' or 'out'

    Returns:
        Syzlang type string to use inside ptr[direction, <type>]
    """
    if c_type in ('int', 'unsigned int'):
        # Use flag groups for mode-related ioctls to improve fuzzing quality
        if ioctl_name in ('PPSETMODE', 'PPNEGOT'):
            return 'flags[ieee1284_modes, int32]'
        # Output mode ioctls: use flags so syzkaller understands the value space
        if ioctl_name in ('PPGETMODE', 'PPGETMODES'):
            return 'flags[ieee1284_modes, int32]'
        if ioctl_name in ('PPSETFLAGS',):
            return 'flags[ppdev_flags, int32]'
        if ioctl_name in ('PPGETFLAGS',):
            return 'flags[ppdev_flags, int32]'
        # Plain int32 for PPDATADIR, PPCLRIRQ, PPSETPHASE, PPGETPHASE
        return 'int32'
    elif c_type == 'unsigned char':
        return 'int8'
    elif c_type == 'struct ppdev_frob_struct':
        return 'ppdev_frob_struct'
    elif c_type == 'struct timeval':
        return 'timeval'
    else:
        # Fallback — should not happen with known ppdev ioctls
        return 'int32'


# =============================================================================
# .txt file generation (syzlang descriptions)
# =============================================================================

def generate_txt():
    """Generate the complete dev_ppdev.txt syzlang description file content."""
    lines = []

    # Header
    lines.append('# Copyright 2024 syzkaller project authors. All rights reserved.')
    lines.append('# Use of this source code is governed by Apache 2 LICENSE that can be found in the LICENSE file.')
    lines.append('')

    # Includes — use the uapi headers that define ppdev ioctls and parport constants
    # Note: syzkaller's include paths resolve <linux/...> to <uapi/linux/...> automatically
    lines.append('include <linux/ppdev.h>')
    lines.append('include <linux/parport.h>')
    lines.append('')

    # Resource definition: typed file descriptor for ppdev
    lines.append('resource fd_ppdev[fd]')
    lines.append('')

    # Device opener using syz_open_dev pseudo-syscall
    # The '#' placeholder is replaced by the id argument at runtime
    lines.append('syz_open_dev$ppdev(dev ptr[in, string["/dev/parport#"]], id intptr, flags flags[open_flags]) fd_ppdev')
    lines.append('')

    # Generate ioctl descriptions grouped by type for readability
    ioctls = get_ioctl_definitions()

    for name, macro, nr, c_type, sz_amd64, sz_386 in ioctls:
        if macro == '_IO':
            # No-argument ioctls: omit the third arg entirely
            lines.append(f'ioctl${name}(fd fd_ppdev, cmd const[{name}])')
        elif macro == '_IOR':
            syz_type = get_syz_type(name, c_type, 'out')
            lines.append(f'ioctl${name}(fd fd_ppdev, cmd const[{name}], arg ptr[out, {syz_type}])')
        elif macro == '_IOW':
            syz_type = get_syz_type(name, c_type, 'in')
            lines.append(f'ioctl${name}(fd fd_ppdev, cmd const[{name}], arg ptr[in, {syz_type}])')

    lines.append('')

    # Struct definition: ppdev_frob_struct used by PPFCONTROL
    # Kernel definition: struct ppdev_frob_struct { unsigned char mask; unsigned char val; };
    lines.append('ppdev_frob_struct {')
    lines.append('\tmask\tint8')
    lines.append('\tval\tint8')
    lines.append('}')
    lines.append('')

    # Flag group: IEEE 1284 mode constants for PPSETMODE/PPNEGOT/PPGETMODE/PPGETMODES
    ieee_flags = get_ieee1284_flags()
    lines.append('ieee1284_modes = ' + ', '.join(f[0] for f in ieee_flags))
    lines.append('')

    # Flag group: ppdev-specific flags for PPSETFLAGS/PPGETFLAGS
    pp_flags = get_ppdev_flags()
    lines.append('ppdev_flags = ' + ', '.join(f[0] for f in pp_flags))
    lines.append('')

    return '\n'.join(lines)


# =============================================================================
# .txt.const file generation (architecture-specific constants)
# =============================================================================

def generate_const():
    """Generate the dev_ppdev.txt.const file with arch-qualified constant values.

    The const file uses the format:
        CONSTANT_NAME = 386:value, amd64:value

    PPGETTIME and PPSETTIME have different values on 386 vs amd64 because
    sizeof(struct timeval) differs (8 vs 16 bytes).
    """
    # Collect all constants as {name: {arch: value}}
    constants = {}

    ioctls = get_ioctl_definitions()
    for name, macro, nr, c_type, sz_amd64, sz_386 in ioctls:
        val_amd64 = compute_ioctl_value(macro, nr, sz_amd64)
        val_386 = compute_ioctl_value(macro, nr, sz_386)
        constants[name] = {'amd64': val_amd64, '386': val_386}

    for name, val in get_ieee1284_flags():
        constants[name] = {'amd64': val, '386': val}

    for name, val in get_ppdev_flags():
        constants[name] = {'amd64': val, '386': val}

    # Build output lines
    lines = []
    lines.append('# Code generated by syz-sysgen. DO NOT EDIT.')
    lines.append('arches = 386, amd64')

    # Sort constants alphabetically (syzkaller convention)
    for name in sorted(constants.keys()):
        vals = constants[name]
        val_386 = vals['386']
        val_amd64 = vals['amd64']
        # Use arch-qualified format: NAME = 386:val, amd64:val
        lines.append(f'{name} = 386:{val_386}, amd64:{val_amd64}')

    lines.append('')
    return '\n'.join(lines)


# =============================================================================
# File writing
# =============================================================================

def write_files(txt_path, const_path):
    """Write both dev_ppdev.txt and dev_ppdev.txt.const files.

    Args:
        txt_path: Full path for the .txt syzlang description file
        const_path: Full path for the .txt.const constants file
    """
    txt_content = generate_txt()
    const_content = generate_const()

    # Ensure output directory exists
    out_dir = os.path.dirname(txt_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(txt_path, 'w') as f:
        f.write(txt_content)
    print(f"Written {txt_path} ({len(txt_content)} bytes)")

    with open(const_path, 'w') as f:
        f.write(const_content)
    print(f"Written {const_path} ({len(const_content)} bytes)")

    # Validation: verify expected counts
    ioctls = get_ioctl_definitions()
    print(f"Total ioctls described: {len(ioctls)}")
    io_count = sum(1 for _, m, *_ in ioctls if m == '_IO')
    iow_count = sum(1 for _, m, *_ in ioctls if m == '_IOW')
    ior_count = sum(1 for _, m, *_ in ioctls if m == '_IOR')
    print(f"  _IO: {io_count}, _IOW: {iow_count}, _IOR: {ior_count}")

    ieee_count = len(get_ieee1284_flags())
    pp_count = len(get_ppdev_flags())
    print(f"IEEE 1284 mode flags: {ieee_count}")
    print(f"PP device flags: {pp_count}")
    print(f"Total constants in .const file: {len(ioctls) + ieee_count + pp_count}")


def validate_ioctl_numbers():
    """Validate computed ioctl numbers against known reference values.

    Cross-checks a subset of ioctl values against the deep research document
    to catch computation errors early.
    """
    # Reference values from kernel header analysis (hex)
    reference = {
        'PPSETMODE':    (0x40047080, 0x40047080),   # (amd64, 386)
        'PPRSTATUS':    (0x80017081, 0x80017081),
        'PPWSTATUS':    (0x40017082, 0x40017082),
        'PPCLAIM':      (0x0000708b, 0x0000708b),
        'PPFCONTROL':   (0x4002708e, 0x4002708e),
        'PPEXCL':       (0x0000708f, 0x0000708f),
        'PPGETTIME':    (0x80107095, 0x80087095),    # differs: timeval size
        'PPSETTIME':    (0x40107096, 0x40087096),    # differs: timeval size
        'PPGETMODES':   (0x80047097, 0x80047097),
        'PPSETFLAGS':   (0x4004709b, 0x4004709b),
        'PPCLRIRQ':     (0x80047093, 0x80047093),
        'PPRDATA':      (0x80017085, 0x80017085),
        'PPWDATA':      (0x40017086, 0x40017086),
        'PPRECONTROL':  (0x80017087, 0x80017087),
        'PPWECONTROL':  (0x40017088, 0x40017088),
        'PPRFIFO':      (0x80017089, 0x80017089),
        'PPWFIFO':      (0x4001708a, 0x4001708a),
    }

    ioctls = get_ioctl_definitions()
    errors = []
    for name, macro, nr, c_type, sz_amd64, sz_386 in ioctls:
        if name in reference:
            expected_amd64, expected_386 = reference[name]
            actual_amd64 = compute_ioctl_value(macro, nr, sz_amd64)
            actual_386 = compute_ioctl_value(macro, nr, sz_386)
            if actual_amd64 != expected_amd64:
                errors.append(f"{name} amd64: expected {hex(expected_amd64)}, got {hex(actual_amd64)}")
            if actual_386 != expected_386:
                errors.append(f"{name} 386: expected {hex(expected_386)}, got {hex(actual_386)}")

    if errors:
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        raise ValueError(f"Ioctl number validation failed with {len(errors)} error(s)")
    else:
        print("All ioctl number validations passed.")


if __name__ == '__main__':
    # Run validation first to catch any computation errors
    validate_ioctl_numbers()

    txt_path = '/opt/syzkaller/sys/linux/dev_ppdev.txt'
    const_path = '/opt/syzkaller/sys/linux/dev_ppdev.txt.const'
    write_files(txt_path, const_path)