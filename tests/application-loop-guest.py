"""Original ARMv7 UIApplicationMain lifecycle regression; no game data.

Shows an asynchronous startup popup, then stops the current main run loop
from a guest timer. UIApplicationMain must keep dispatching later timers,
not return a stale timer pointer to the guest startup routine.
"""
import argparse
import importlib.util
from pathlib import Path
import plistlib
import struct
import subprocess

spec = importlib.util.spec_from_file_location(
    'wide_guest', Path(__file__).with_name('wide-string-guest.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.IMPORTS = ['_objc_getClass', '_sel_registerName', '_objc_msgSend',
                '_class_addMethod', '_write', '_exit', '_UIApplicationMain',
                '_CFRunLoopGetCurrent', '_CFRunLoopStop', '_CFRunLoopRun']


def generate(destination, genuine_exit=False, direct_stop=False, nested_stop=False):
    g = base.Guest()
    cells = {name: g.blob(base.u32(0)) for name in (
        'class', 'delegate_name', 'delegate', 'timerclass', 'title', 'button',
        'alert', 'stopped')}
    names, imps = {}, []

    def cstring(value):
        if value not in names:
            names[value] = g.blob(value.encode() + b'\0')
        return names[value]

    def save(register, name):
        g.literal(12, cells[name])
        g.code.append(0xe58c0000 | register << 12)

    def load(register, name):
        g.literal(register, cells[name])
        g.code.append(0xe5900000 | register << 16 | register << 12)

    def selector(value):
        g.literal(0, cstring(value))
        g.call('_sel_registerName')
        g.code.append(0xe1a01000)

    def message(target, value, argument=0):
        selector(value)
        load(0, target)
        g.literal(2, argument)
        g.literal(3, 0)
        g.call('_objc_msgSend')

    def timer(value, interval):
        selector(value)
        g.code.append(0xe58d1004)
        load(12, 'delegate')
        g.code.append(0xe58dc000)
        g.literal(12, 0)
        g.code.extend([0xe58dc008, 0xe58dc00c])
        selector('scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:')
        load(0, 'timerclass')
        lo, hi = struct.unpack('<2I', struct.pack('<d', interval))
        g.literal(2, lo)
        g.literal(3, hi)
        g.call('_objc_msgSend')

    g.code.append(0xe24dd020)
    g.message('[APPLICATION LOOP REGRESSION] START ARMv7\n')
    g.literal(0, cstring('NSObject'))
    g.call('_objc_getClass')
    save(0, 'class')
    for name, label, encoding in [
            ('application:didFinishLaunchingWithOptions:', 'launch_imp', 'B16@0:4@8@12'),
            ('stopCurrentLoop:', 'stop_imp', 'v12@0:4@8'),
            ('stopNestedLoop:', 'nested_imp', 'v12@0:4@8'),
            ('verifyContinuedDispatch:', 'verify_imp', 'v12@0:4@8')]:
        selector(name)
        load(0, 'class')
        g.literal(2, 0)
        imps.append((len(g.code) - 1, label))
        g.literal(3, cstring(encoding))
        g.call('_class_addMethod')
        g.compare(1, 'fail_setup')
    for name, cell in [('NSTimer', 'timerclass'), ('NSString', 'class')]:
        g.literal(0, cstring(name))
        g.call('_objc_getClass')
        save(0, cell)
    message('class', 'stringWithUTF8String:', cstring('NSObject'))
    save(0, 'delegate_name')
    message('delegate_name', 'retain')
    message('class', 'stringWithUTF8String:', cstring('Startup promotion popup'))
    save(0, 'title')
    message('title', 'retain')
    message('class', 'stringWithUTF8String:', cstring('OK'))
    save(0, 'button')
    message('button', 'retain')
    if direct_stop:
        g.literal(0, cstring('NSObject'))
        g.call('_objc_getClass')
        save(0, 'class')
        message('class', 'new')
        save(0, 'delegate')
        message('delegate', 'application:didFinishLaunchingWithOptions:')
        g.call('_CFRunLoopRun')
        load(0, 'stopped')
        g.compare(1, 'fail_timer')
        g.message('[APPLICATION LOOP REGRESSION] PASS direct CFRunLoopRun returns after stop\n')
        g.message('[APPLICATION LOOP REGRESSION] ALL PASS 1\n')
        g.literal(0, 0)
        g.call('_exit')
    else:
        g.literal(0, 0)
        g.literal(1, 0)
        g.literal(2, 0)
        load(3, 'delegate_name')
        g.call('_UIApplicationMain')
    save(0, 'stopped')
    g.message('[APPLICATION LOOP REGRESSION] FAIL UIApplicationMain returned\n')
    g.literal(0, 74)
    g.call('_exit')
    g.code.append(0xeafffffe)

    g.labels['launch_imp'] = len(g.code)
    g.code.extend([0xe92d40b0, 0xe24dd010])
    save(0, 'delegate')
    timer('stopCurrentLoop:', 0.02)
    timer('verifyContinuedDispatch:', 0.20)
    g.literal(0, 1)
    g.code.extend([0xe28dd010, 0xe8bd80b0])

    g.labels['stop_imp'] = len(g.code)
    g.code.extend([0xe92d40b0, 0xe24dd010])
    if genuine_exit:
        g.message('[APPLICATION LOOP REGRESSION] GENUINE_EXIT 73\n')
        g.literal(0, 73)
        g.call('_exit')
        g.code.append(0xeafffffe)
    else:
        g.literal(0, cstring('UIAlertView'))
        g.call('_objc_getClass')
        save(0, 'class')
        message('class', 'alloc')
        save(0, 'alert')
        selector('initWithTitle:message:delegate:cancelButtonTitle:otherButtonTitles:')
        load(0, 'alert')
        load(2, 'title')
        g.literal(3, 0)
        g.literal(12, 0)
        g.code.extend([0xe58dc000, 0xe58dc008, 0xe58dc00c])
        load(12, 'button')
        g.code.append(0xe58dc004)
        g.call('_objc_msgSend')
        save(0, 'alert')
        message('alert', 'show')
        message('alert', 'release')
        if nested_stop:
            timer('stopNestedLoop:', 0.02)
            g.call('_CFRunLoopRun')
            g.message('[APPLICATION LOOP REGRESSION] NESTED_ACTIVATION_RETURNED\n')
        else:
            g.call('_CFRunLoopGetCurrent')
            g.call('_CFRunLoopStop')
        g.literal(0, 1)
        save(0, 'stopped')
        g.message('[APPLICATION LOOP REGRESSION] CURRENT_ACTIVATION_STOPPED\n')
        g.code.extend([0xe28dd010, 0xe8bd80b0])

    g.labels['nested_imp'] = len(g.code)
    g.code.append(0xe92d40b0)
    g.call('_CFRunLoopGetCurrent')
    g.call('_CFRunLoopStop')
    g.code.append(0xe8bd80b0)

    g.labels['verify_imp'] = len(g.code)
    g.code.append(0xe92d40b0)
    load(0, 'stopped')
    g.compare(1, 'fail_timer')
    message('alert', 'isVisible')
    g.compare(1, 'fail_timer')
    message('alert', 'dismissWithClickedButtonIndex:animated:', -1)
    g.message('[APPLICATION LOOP REGRESSION] PASS application dispatch survives stopped activation\n')
    g.message('[APPLICATION LOOP REGRESSION] ALL PASS 1\n')
    g.literal(0, 0)
    g.call('_exit')
    g.code.append(0xeafffffe)
    for label, detail in [('fail_setup', 'guest delegate setup'),
                          ('fail_timer', 'later timer or popup state')]:
        g.labels[label] = len(g.code)
        g.message('[APPLICATION LOOP REGRESSION] FAIL ' + detail + '\n')
        g.literal(0, 75)
        g.call('_exit')
        g.code.append(0xeafffffe)
    for position, label in imps:
        g.code[position] = base.TEXT_BASE + base.ENTRY_OFFSET + g.labels[label] * 4
    for position, label, condition in g.branches:
        g.code[position] = (condition << 28 | 0x0a000000 |
                            (g.labels[label] - position - 2) & 0xffffff)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'ApplicationLoopRegression').write_bytes(
        base.executable(g, base.u32(*g.code)))
    (destination / 'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'io.github.sloppytaco.applicationloopregression',
        'CFBundleName': 'ApplicationLoopRegression',
        'CFBundleExecutable': 'ApplicationLoopRegression',
        'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1.0',
        'MinimumOSVersion': '3.0', 'UIDeviceFamily': [1]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--emulator', type=Path)
    parser.add_argument('--log', type=Path)
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--genuine-exit', action='store_true')
    parser.add_argument('--direct-stop', action='store_true')
    parser.add_argument('--nested-stop', action='store_true')
    parser.add_argument('--require-v21', action='store_true')
    args = parser.parse_args()
    assert sum((args.genuine_exit, args.direct_stop, args.nested_stop)) <= 1
    generate(args.app, args.genuine_exit, args.direct_stop, args.nested_stop)
    if args.emulator is None:
        return
    result = subprocess.run([str(args.emulator.resolve()), str(args.app.resolve()),
                             '--headless'], capture_output=True, text=True, timeout=10)
    output = result.stdout + result.stderr
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(output)
    print('\n'.join(line for line in output.splitlines()
                    if 'APPLICATION LOOP' in line or 'App called exit' in line
                    or 'ALERT ASYNC v20' in line or 'panicked' in line))
    expected = 73 if args.genuine_exit else 74 if args.baseline else 0
    marker = ('GENUINE_EXIT 73' if args.genuine_exit else
              'FAIL UIApplicationMain returned' if args.baseline else 'ALL PASS 1')
    assert result.returncode == expected and marker in output, (
        f'Unexpected lifecycle result {result.returncode}, expected {expected}\n' + output[-7000:])
    if args.require_v21:
        assert not args.baseline
        if args.genuine_exit:
            assert '[GUEST EXIT v21]' in output
        elif not args.direct_stop and not args.nested_stop:
            assert '[APPLICATION LOOP v21]' in output


if __name__ == '__main__':
    main()
