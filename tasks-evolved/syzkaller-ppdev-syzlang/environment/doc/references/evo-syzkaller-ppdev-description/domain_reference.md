# Domain Reference for evo-syzkaller-ppdev-description

**Responsibility**: Generate dev_ppdev.txt (syzlang descriptions with includes, resource, opener, ioctl variants, structs, flags) and dev_ppdev.txt.const (architecture-specific constant values) that pass syzkaller's make descriptions and make all verification steps.

**Key functions to implement**: generate_ppdev_syzlang_txt, generate_ppdev_const_file, compute_ioctl_number, validate_ioctl_directions

---

### Introduction

Syzkaller is a coverage-guided kernel fuzzer that targets system calls to uncover vulnerabilities within operating system kernels [cite: 1]. Unlike rudimentary fuzzers that mutate raw byte streams blindly, Syzkaller utilizes a domain-specific language (DSL) called Syzlang to describe the exact syntax, semantics, and resource dependencies of kernel interfaces [cite: 2, 3]. This declarative approach ensures that the fuzzer generates valid structured data, enabling it to penetrate deeply into kernel state machines without being prematurely rejected by basic error-handling code [cite: 1]. This report provides an exhaustive syntax reference and semantic guide for writing device driver syscall descriptions in Syzlang, with a specific focus on characterizing the Linux `ppdev` (parallel port device) interface.

### The Role of Syzlang in Kernel Fuzzing

Syzlang descriptions are authored in plaintext `.txt` files, typically located in `sys/linux/` [cite: 3, 4]. The language dictates how system calls are invoked, how arguments are typed, and how data structures map to memory [cite: 2, 3]. Because the Linux kernel exposes a vast and heterogeneous attack surface through pseudo-filesystems and character devices, Syzlang provides specialized constructs such as pseudo-syscalls (e.g., `syz_open_dev`) and resource trackers to manage file descriptors [cite: 1, 5]. By accurately defining these constraints, Syzkaller can automatically infer how to chain multiple system calls together, utilizing the output of one call (like an opened file descriptor) as the input for subsequent operations (like an ioctl) [cite: 2, 5].

---

## 1. Syzlang Syntax for Device File Descriptions


When interacting with character devices, fuzzers must first obtain a valid file descriptor. In standard C programs, this is achieved via the `open()` or `openat()` syscalls. However, device nodes in Linux often feature dynamic numeric suffixes (e.g., `/dev/loop0`, `/dev/loop1`, `/dev/parport0`). To effectively model this variability, Syzkaller implements a specialized pseudo-syscall named `syz_open_dev` [cite: 1].

## 2. Syzlang IOCTL Description Syntax


The `ioctl` system call is a multiplexer, routing requests based on a 32-bit command number. In Syzlang, each distinct ioctl operation is modeled as a separate system call variant using the `ioctl$VARIANT_NAME` syntax [cite: 3]. This allows the fuzzer to understand the specific data structures and pointer directions associated with every individual command [cite: 3, 5].

## 3. Syzlang Struct Definitions


Data structures in Syzlang must reflect the exact memory layout expected by the kernel, respecting architectures' alignment and padding rules [cite: 3, 5]. Syzlang structs are defined by providing a name, followed by a set of curly braces containing the field names and their corresponding types [cite: 3, 8].

## 4. Syzlang Flags and Constants


Constants that form enumerations or bitwise flag fields must be grouped logically so the fuzzer can choose valid combinations. In Syzlang, flag groups are defined simply by declaring a group name and assigning it a comma-separated list of constant names [cite: 3, 4].

## 5. The `.txt.const` File Format


Because kernel constants, macros, and ioctl numbers can vary dramatically between architectures (e.g., `amd64`, `386`, `arm64`), Syzlang separates structural descriptions from numerical values. The raw numbers are stored in a corresponding `.txt.const` file [cite: 6, 14].

## 6. Linux `ppdev` Driver IOCTL Interface Analysis


The `ppdev` driver provides user-space applications with direct control over parallel port hardware, enabling functions ranging from reading the status pins to full IEEE 1284 protocol negotiation [cite: 19, 20]. The interface defines 28 distinct ioctl macros across `uapi/linux/ppdev.h` and `uapi/linux/parport.h` [cite: 10, 19].

The ioctls use the magic character `'p'` (`0x70`) [cite: 10, 19].

## 8. The `ppdev_frob_struct` Definition


The `PPFCONTROL` ioctl allows user-space programs to atomically toggle specific control lines without risking race conditions typical of read-modify-write sequences [cite: 19, 22]. It achieves this by accepting a pointer to a `ppdev_frob_struct`.

**C Definition in `linux/ppdev.h`:**
```c
struct ppdev_frob_struct {
    unsigned char mask;
    unsigned char val;
};
```
*   **`mask`**: A 1-byte field dictating which control lines should be modified [cite: 19, 22].
*   **`val`**: A 1-byte field specifying the new bit values for the lines designated in the mask [cite: 19, 22].

**Syzlang Translation:**
```text
ppdev_frob_struct {
    mask int8
    val  int8
}
```

---

## 9. IEEE 1284 Mode Flags and PP Flags


To fuzz `ppdev` appropriately, Syzlang needs access to the logical flag definitions used by `PPNEGOT`, `PPSETMODE`, and `PPSETFLAGS` [cite: 19, 20]. These constants reside primarily in `linux/parport.h` [cite: 29].

## 10. How Syzkaller Computes IOCTL Numbers


Syzkaller does not guess IOCTL numbers; it fundamentally relies on the same C preprocessor logic that the Linux kernel uses [cite: 6, 24]. The ioctl command number is a 32-bit integer packed with semantic information via the `_IOC` macro [cite: 24, 26].

**Bit Layout on `amd64` and `386`:**
*   **NR (Sequence Number)**: Bits 0-7 (8 bits).
*   **TYPE (Magic Character)**: Bits 8-15 (8 bits).
*   **SIZE (Argument Size)**: Bits 16-29 (14 bits). Defines the byte size of the argument payload [cite: 26].
*   **DIR (Direction)**: Bits 30-31 (2 bits). Specifies the read/write nature [cite: 26].

**Direction Encodings on x86:**
*   `_IOC_NONE` (`_IO`): `0` (0b00) [cite: 26]
*   `_IOC_WRITE` (`_IOW`): `1` (0b01) [cite: 26]
*   `_IOC_READ` (`_IOR`): `2` (0b10) [cite: 26]
*   `_IOC_READ | _IOC_WRITE` (`_IOWR`): `3` (0b11) [cite: 26]

*Note: On platforms like PowerPC or MIPS, the size and direction bits may differ (e.g., `_IOC_WRITE` might equal `4U`, and `IOC_SIZEBITS` might be 13) [cite: 26]. The `syz-extract` tool elegantly bypasses cross-platform math inconsistencies by invoking the target architecture's cross-compiler to print the final 32-bit integer evaluated directly by the kernel's own headers [cite: 6, 14].*

---

## 11. Common Pitfalls in Syzlang Descriptions


When authoring new syscall descriptions, developers frequently encounter errors flagged by the `syz-extract` and `syz-sysgen` compilation stages [cite: 13, 14].

## 12. Existing Syzkaller Device Description Examples


To contextualize the syntax, one can look at standard Syzkaller definitions for character devices. The `/dev/snd/midi` subsystem serves as a prime archetype [cite: 8].

**Excerpt from `dev_snd_midi.txt`:**
```text

# Struct definitions

snd_rawmidi_info {
    device       int32
    subdevice    int32
    stream       flags[sndrv_rawmidi_stream, int32]
    card         const[0, int32]
    flags        const[0, int32]
    id           array[const[0, int8], 64]
    name         array[const[0, int8], 80]
}
```
In this snippet, `snd_rawmidi_info` uses strict alignments and constants (e.g., `const[0, int32]`) to force the fuzzer to ignore fields that do not contribute to state exploration [cite: 8].

---

## 13. Practical Synthesis: A Complete Syzlang Description for `ppdev`


Based on the research and syntax rules defined in the preceding sections, a functional and complete `dev_ppdev.txt` file is synthesized below.

# Struct definition

ppdev_frob_struct {
    mask int8
    val  int8
}