#!/usr/bin/env python3
"""Run an original ARMv7 formatter regression guest, without an iOS SDK.

The generated Mach-O imports the emulator's real C entry points. It contains
only the test instructions/data authored here; no game binary or game assets.
"""
import argparse
import json
from pathlib import Path
import plistlib
import struct
import subprocess

TEXT_BASE, TEXT_SIZE, ENTRY_OFFSET = 0x1000, 0x4000, 0x400
DATA_BASE, DATA_SIZE = TEXT_BASE + TEXT_SIZE, 0x4000
IMPORTS = ['_swprintf', '_snprintf', '_memcmp', '_write', '_exit', '_wprintf', '_vwprintf']


def u32(*values):
    return struct.pack('<' + 'I' * len(values), *(v & 0xffffffff for v in values))


def wide(value, terminated=True):
    return u32(*(ord(c) for c in value), *([0] if terminated else []))


class Guest:
    def __init__(self):
        self.data = bytearray(4 * len(IMPORTS))
        self.code = []
        self.labels = {}
        self.branches = []
        self.tests = []

    def blob(self, value):
        while len(self.data) % 4:
            self.data.append(0)
        address = DATA_BASE + len(self.data)
        self.data.extend(value)
        return address

    def literal(self, register, value):
        # LDR rN,[pc,#0]; B next; .word value
        self.code.extend([0xe59f0000 | register << 12, 0xea000000, value])

    def call(self, name):
        self.literal(12, DATA_BASE + 4 * IMPORTS.index(name))
        self.code.extend([0xe59cc000, 0xe12fff3c])

    def branch(self, label, condition=14):
        self.branches.append((len(self.code), label, condition))
        self.code.append(0)

    def compare(self, expected, failure):
        self.literal(1, expected)
        self.code.append(0xe1500001)  # CMP r0,r1
        self.branch(failure, 1)  # BNE

    def compare_memory(self, address, expected, failure):
        expected_address = self.blob(expected)
        self.literal(0, address)
        self.literal(1, expected_address)
        self.literal(2, len(expected))
        self.call('_memcmp')
        self.compare(0, failure)

    def message(self, value):
        encoded = value.encode()
        address = self.blob(encoded)
        self.literal(0, 1)
        self.literal(1, address)
        self.literal(2, len(encoded))
        self.call('_write')

    def formatter(self, name, fmt, argument, expected, *, narrow=False,
                  cap=None, extra=None, arg_bytes=False, unterminated=False,
                  return_value=None, prefix_only=False):
        number = len(self.tests) + 1
        failure = f'fail_{number}'
        self.tests.append((failure, name))
        unit = 1 if narrow else 4
        encoded = expected.encode() if narrow else wide(expected, False)
        if cap is None:
            cap = len(expected.encode()) + 1 if narrow else len(expected) + 1
        buffer = self.blob(bytes([0xcd]) * (256 * unit))
        format_pointer = self.blob(fmt.encode() + b'\0' if narrow else wide(fmt))
        if argument is None:
            arg_pointer = 0
        else:
            arg_pointer = self.blob(argument.encode() + b'\0' if arg_bytes else wide(argument, not unterminated))
        if extra is not None:
            self.literal(3, extra)
            self.code.append(0xe58d3000)  # STR r3,[sp,#0]
        self.literal(0, buffer)
        self.literal(1, cap)
        self.literal(2, format_pointer)
        self.literal(3, arg_pointer)
        self.call('_snprintf' if narrow else '_swprintf')
        result = len(encoded) if narrow else len(expected)
        self.compare(result if return_value is None else return_value, failure)
        if not prefix_only:
            encoded += bytes(unit)
        self.compare_memory(buffer, encoded, failure)
        # Nothing beyond the caller-provided capacity may be written.
        self.compare_memory(buffer + cap * unit, bytes([0xcd]) * unit, failure)
        self.message(f'[WIDE-STRING REGRESSION] PASS {number:02d} {name}\n')

    def output_count(self, name, function):
        number = len(self.tests) + 1
        failure = f'fail_{number}'
        self.tests.append((failure, name))
        argument = self.blob(wide('Café 🍔'))
        self.literal(0, self.blob(wide('[%ls]\n')))
        if function == '_wprintf':
            self.literal(1, argument)
        else:
            self.literal(1, self.blob(u32(argument)))
        self.call(function)
        self.compare(len('[Café 🍔]\n'), failure)
        self.message(f'[WIDE-STRING REGRESSION] PASS {number:02d} {name}\n')

    def finish(self):
        self.message(f'[WIDE-STRING REGRESSION] ALL PASS {len(self.tests)}\n')
        self.literal(0, 0)
        self.call('_exit')
        self.code.append(0xeafffffe)
        for index, (label, name) in enumerate(self.tests, 1):
            self.labels[label] = len(self.code)
            self.message(f'[WIDE-STRING REGRESSION] FAIL {index:02d} {name}\n')
            self.literal(0, index)
            self.call('_exit')
            self.code.append(0xeafffffe)
        for index, label, condition in self.branches:
            displacement = self.labels[label] - index - 2
            assert -(1 << 23) <= displacement < (1 << 23)
            self.code[index] = condition << 28 | 0x0a000000 | displacement & 0xffffff
        return u32(*self.code)


def fixed_name(value):
    return value.encode().ljust(16, b'\0')


def section(name, segment, address, size, offset, flags):
    return struct.pack('<16s16s9I', fixed_name(name), fixed_name(segment), address,
                       size, offset, 2, 0, 0, flags, 0, 0)


def segment(name, address, size, offset, file_size, protection, sections=()):
    body = b''.join(sections)
    return struct.pack('<II16s8I', 1, 56 + len(body), fixed_name(name), address,
                       size, offset, file_size, protection, protection, len(sections), 0) + body


def uleb(value):
    output = bytearray()
    while value >= 128:
        output.append(value & 127 | 128)
        value >>= 7
    output.append(value)
    return output


def executable(guest, code):
    assert ENTRY_OFFSET + len(code) < TEXT_SIZE
    assert len(guest.data) < DATA_SIZE
    binds = bytearray([0x3e, 0x51])  # flat lookup (-2), pointer bind type
    for index, name in enumerate(IMPORTS):
        binds.extend(b'\x40' + name.encode() + b'\0')
        binds.append(0x72)  # __DATA is segment 2 after __PAGEZERO and __TEXT
        binds.extend(uleb(index * 4))
        binds.append(0x90)
    binds.append(0)
    commands = [
        segment('__PAGEZERO', 0, TEXT_BASE, 0, 0, 0),
        segment('__TEXT', TEXT_BASE, TEXT_SIZE, 0, TEXT_SIZE, 5,
                [section('__text', '__TEXT', TEXT_BASE + ENTRY_OFFSET, len(code), ENTRY_OFFSET, 0x80000400)]),
        segment('__DATA', DATA_BASE, DATA_SIZE, TEXT_SIZE, DATA_SIZE, 3,
                [section('__data', '__DATA', DATA_BASE, len(guest.data), TEXT_SIZE, 0)]),
        u32(5, 84, 1, 17, *([0] * 15), TEXT_BASE + ENTRY_OFFSET, 0),
        u32(0x80000022, 48, 0, 0, TEXT_SIZE + DATA_SIZE, len(binds), 0, 0, 0, 0, 0, 0),
    ]
    command_data = b''.join(commands)
    header = u32(0xfeedface, 12, 9, 2, len(commands), len(command_data), 4)
    assert len(header + command_data) <= ENTRY_OFFSET
    text = (header + command_data).ljust(ENTRY_OFFSET, b'\0') + code
    return text.ljust(TEXT_SIZE, b'\0') + guest.data.ljust(DATA_SIZE, b'\0') + binds


def generate(destination):
    guest = Guest()
    guest.code.append(0xe24dd020)  # SUB sp,sp,#32; maintain 8-byte alignment
    guest.message('[WIDE-STRING REGRESSION] START ARMv7\n')
    guest.formatter('wide purchase message', '%ls has been purchased!', 'Gravy Chug',
                    'Gravy Chug has been purchased!')
    guest.formatter('wide string and stack vararg', '%ls for %d COIN(s)?', 'Gravy Chug',
                    'Gravy Chug for 250 COIN(s)?', extra=250)
    guest.formatter('wide precision', '%.5ls', 'Gravy Chug', 'Gravy')
    guest.formatter('wide right padding', '%12ls', 'Gravy Chug', '  Gravy Chug')
    guest.formatter('wide left padding', '%-12ls', 'Gravy Chug', 'Gravy Chug  ')
    guest.formatter('Unicode wide exact capacity and count', '[%ls]', 'Café 🍔', '[Café 🍔]')
    guest.formatter('narrow wide-string conversion', '%ls', 'Café 🍔', 'Café 🍔', narrow=True)
    guest.formatter('narrow precision never splits Unicode', '%.4ls', 'Café', 'Caf', narrow=True)
    guest.formatter('plain narrow string preserved', '%s%d', 'Narrow', 'Narrow17',
                    narrow=True, arg_bytes=True, extra=17)
    guest.formatter('bounded nonterminated wide argument', '%.3ls', 'ABC', 'ABC', unterminated=True)
    guest.formatter('wide insufficient capacity and guard', '%ls', 'Gravy Chug', 'Gra',
                    cap=3, return_value=-1, prefix_only=True)
    guest.formatter('wide empty output capacity one', '', None, '', cap=1)
    guest.formatter('null wide argument', '%ls', None, '(null)')
    # Capacity zero must not dereference a null output pointer.
    failure = 'fail_zero'
    guest.tests.append((failure, 'wide zero capacity null output'))
    guest.literal(0, 0)
    guest.literal(1, 0)
    guest.literal(2, guest.blob(wide('')))
    guest.literal(3, 0)
    guest.call('_swprintf')
    guest.compare(-1, failure)
    guest.message('[WIDE-STRING REGRESSION] PASS 14 wide zero capacity null output\n')
    guest.output_count('wprintf Unicode count', '_wprintf')
    guest.output_count('vwprintf Unicode count', '_vwprintf')
    code = guest.finish()
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'WideStringRegression').write_bytes(executable(guest, code))
    (destination/'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'io.github.sloppytaco.widestringregression',
        'CFBundleName': 'WideStringRegression', 'CFBundleDisplayName': 'WideStringRegression',
        'CFBundleExecutable': 'WideStringRegression', 'CFBundlePackageType': 'APPL',
        'CFBundleVersion': '1.0', 'MinimumOSVersion': '2.0', 'UIDeviceFamily': [1],
    }))
    return len(guest.tests)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--emulator', type=Path)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--log', type=Path)
    args = parser.parse_args()
    count = generate(args.app)
    if args.emulator is None:
        print(json.dumps({'cases': count, 'app': str(args.app)}))
        return
    run = subprocess.run([str(args.emulator.resolve()), str(args.app.resolve()), '--headless'],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    output = run.stdout.decode('utf-8', errors='replace')
    if args.log:
        args.log.write_text(output)
    for line in output.splitlines():
        if '[WIDE-STRING REGRESSION]' in line:
            print(line)
    if args.baseline:
        assert '[WIDE-STRING REGRESSION] START ARMv7' in output, output[-4000:]
        assert '[WIDE-STRING REGRESSION] FAIL 01 wide purchase message' in output, output[-4000:]
        assert run.returncode != 0, 'V15 unexpectedly passed the confirmed regression'
        print('Baseline V15 reproduces the wide-string purchase-name regression.')
    else:
        assert run.returncode == 0, output[-4000:]
        assert f'[WIDE-STRING REGRESSION] ALL PASS {count}' in output, output[-4000:]
        assert '[WIDE-STRING REGRESSION] FAIL' not in output
        print(f'All {count} guest formatter cases passed through the real emulator ABI.')


if __name__ == '__main__':
    main()
