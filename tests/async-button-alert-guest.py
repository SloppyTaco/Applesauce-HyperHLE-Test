"""Original ARMv7 guest for async button-alert ownership and callbacks.

Real guest IMPs/NSTimers are used. Headless test events use the same existing
user-event entry point as the native bridge; this is not a hardware-touch test.
No SDK, private game executable or game assets are required.
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
                '_class_addMethod', '_write', '_exit']


def generate(destination):
    g = base.Guest()
    cells = {name: g.blob(base.u32(0)) for name in (
        'class', 'delegate', 'alert', 'title', 'button', 'timerclass', 'dateclass',
        'pool', 'loop', 'date', 'clicked', 'will', 'did', 'finished', 'click',
        'release_in_click', 'owners')}
    names = {}

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

    def check(name, value, failure):
        load(0, name)
        g.compare(value, failure)

    def reset():
        g.literal(0, 0)
        for name in ('clicked', 'will', 'did', 'finished', 'release_in_click'):
            save(0, name)

    def new_alert():
        reset()
        g.literal(0, cstring('UIAlertView'))
        g.call('_objc_getClass')
        save(0, 'class')
        message('class', 'alloc')
        save(0, 'alert')
        selector('initWithTitle:message:delegate:cancelButtonTitle:otherButtonTitles:')
        load(0, 'alert')
        load(2, 'title')
        g.literal(3, 0)
        load(12, 'delegate')
        g.code.append(0xe58dc000)
        load(12, 'button')
        g.code.append(0xe58dc004)
        g.literal(12, 0)
        g.code.extend([0xe58dc008, 0xe58dc00c])
        g.call('_objc_msgSend')
        save(0, 'alert')

    def complete_with_timer(click, failure):
        g.literal(0, click)
        save(0, 'click')
        selector('finishWork:')
        g.code.append(0xe58d1004)
        load(12, 'delegate')
        g.code.append(0xe58dc000)
        g.literal(12, 0)
        g.code.extend([0xe58dc008, 0xe58dc00c])
        selector('scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:')
        load(0, 'timerclass')
        lo, hi = struct.unpack('<2I', struct.pack('<d', 0.08))
        g.literal(2, lo)
        g.literal(3, hi)
        g.call('_objc_msgSend')
        selector('dateWithTimeIntervalSinceNow:')
        load(0, 'dateclass')
        lo, hi = struct.unpack('<2I', struct.pack('<d', 0.16))
        g.literal(2, lo)
        g.literal(3, hi)
        g.call('_objc_msgSend')
        save(0, 'date')
        selector('runUntilDate:')
        load(0, 'loop')
        load(2, 'date')
        g.call('_objc_msgSend')
        check('finished', 1, failure)
        check('clicked', click, failure)
        check('will', 1, failure)
        check('did', 1, failure)

    tests = [('fail_return', 'button alert returns and guest timers continue'),
             ('fail_program', 'programmatic dismissal has no synthetic click'),
             ('fail_owner', 'caller release is safe until user event'),
             ('fail_repeat', 'duplicate show and stale events are ignored'),
             ('fail_reuse', 'reused alert does not inherit its old poll timer'),
             ('fail_callback_owner', 'delegate release during click remains safe')]
    g.code.append(0xe24dd020)
    g.message('[ASYNC ALERT REGRESSION] START ARMv7\n')
    g.literal(0, cstring('NSObject'))
    g.call('_objc_getClass')
    save(0, 'class')
    imps = []
    for name, label, encoding in [
            ('alertView:clickedButtonAtIndex:', 'clicked_imp', 'v16@0:4@8i12'),
            ('alertView:willDismissWithButtonIndex:', 'will_imp', 'v16@0:4@8i12'),
            ('alertView:didDismissWithButtonIndex:', 'did_imp', 'v16@0:4@8i12'),
            ('finishWork:', 'finish_imp', 'v12@0:4@8')]:
        selector(name)
        load(0, 'class')
        g.literal(2, 0)
        imps.append((len(g.code) - 1, label))
        g.literal(3, cstring(encoding))
        g.call('_class_addMethod')
        g.compare(1, 'fail_setup')
    message('class', 'new')
    save(0, 'delegate')
    for name, cell in [('NSAutoreleasePool', 'class'), ('NSTimer', 'timerclass'),
                       ('NSDate', 'dateclass'), ('NSRunLoop', 'class'), ('NSString', 'class')]:
        g.literal(0, cstring(name))
        g.call('_objc_getClass')
        save(0, cell)
        if name == 'NSAutoreleasePool':
            message('class', 'new')
            save(0, 'pool')
        if name == 'NSRunLoop':
            message('class', 'currentRunLoop')
            save(0, 'loop')
        if name == 'NSString':
            message('class', 'stringWithUTF8String:', cstring('Startup promotion popup'))
            save(0, 'title')
            message('class', 'stringWithUTF8String:', cstring('OK'))
            save(0, 'button')

    for number, (failure, description) in enumerate(tests, 1):
        new_alert()
        message('alert', 'show')
        message('alert', 'isVisible')
        g.compare(1, failure)
        message('alert', 'numberOfButtons')
        g.compare(1, failure)
        check('clicked', 0, failure)
        if number == 3:
            message('alert', 'release')
        if number == 4:
            message('alert', 'retainCount')
            save(0, 'owners')
            message('alert', 'show')
            message('alert', 'retainCount')
            load(1, 'owners')
            g.code.append(0xe1500001)
            g.branch(failure, 1)
        if number == 6:
            g.literal(0, 1)
            save(0, 'release_in_click')
        complete_with_timer(0 if number == 2 else 1, failure)
        if number not in (3, 6):
            message('alert', 'isVisible')
            g.compare(0, failure)
        if number == 4:
            message('alert', '_touchHLE_userClickedButton:', 0)
            message('alert', 'dismissWithClickedButtonIndex:animated:', 0)
            check('clicked', 1, failure)
            check('will', 1, failure)
            check('did', 1, failure)
        if number == 5:
            reset()
            message('alert', 'show')
            message('alert', '_touchHLE_pollNativeAlert:', 0)
            complete_with_timer(0, failure)
        if number not in (3, 6):
            message('alert', 'release')
        g.message(f'[ASYNC ALERT REGRESSION] PASS {number:02d} {description}\n')
    message('pool', 'release')
    g.message('[ASYNC ALERT REGRESSION] ALL PASS 6\n')
    g.literal(0, 0)
    g.call('_exit')
    g.code.append(0xeafffffe)

    for field in ('clicked', 'will', 'did'):
        g.labels[field + '_imp'] = len(g.code)
        g.code.append(0xe92d40b0)
        g.code.append(0xe1a04002)
        load(0, field)
        g.code.append(0xe2800001)
        save(0, field)
        if field == 'clicked':
            load(0, 'release_in_click')
            g.code.append(0xe3500001)
            g.branch('after_click_release', 1)
            message('alert', 'release')
            g.labels['after_click_release'] = len(g.code)
        if field in ('clicked', 'will'):
            selector('dismissWithClickedButtonIndex:animated:')
            g.code.append(0xe1a00004)
            g.literal(2, 0)
            g.literal(3, 0)
            g.call('_objc_msgSend')
        g.code.append(0xe8bd80b0)
    g.labels['finish_imp'] = len(g.code)
    g.code.append(0xe92d40b0)
    load(0, 'finished')
    g.code.append(0xe2800001)
    save(0, 'finished')
    load(0, 'click')
    g.code.append(0xe3500001)
    g.branch('finish_programmatically', 1)
    message('alert', '_touchHLE_userClickedButton:', 0)
    g.code.append(0xe8bd80b0)
    g.labels['finish_programmatically'] = len(g.code)
    message('alert', 'dismissWithClickedButtonIndex:animated:', -1)
    g.code.append(0xe8bd80b0)
    for index, (label, description) in enumerate([('fail_setup', 'guest delegate setup'), *tests], 1):
        g.labels[label] = len(g.code)
        g.message('[ASYNC ALERT REGRESSION] FAIL ' + description + '\n')
        g.literal(0, index)
        g.call('_exit')
        g.code.append(0xeafffffe)
    for position, label in imps:
        g.code[position] = base.TEXT_BASE + base.ENTRY_OFFSET + g.labels[label] * 4
    for position, label, condition in g.branches:
        g.code[position] = condition << 28 | 0x0a000000 | (g.labels[label] - position - 2) & 0xffffff
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'AsyncButtonAlertRegression').write_bytes(base.executable(g, base.u32(*g.code)))
    (destination / 'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'io.github.sloppytaco.asyncbuttonalertregression',
        'CFBundleName': 'AsyncButtonAlertRegression', 'CFBundleExecutable': 'AsyncButtonAlertRegression',
        'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1.0',
        'MinimumOSVersion': '2.0', 'UIDeviceFamily': [1]}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--emulator', type=Path)
    parser.add_argument('--log', type=Path)
    args = parser.parse_args()
    generate(args.app)
    if args.emulator is None:
        print('Generated six original ARMv7 async button-alert cases.')
        return
    result = subprocess.run([str(args.emulator.resolve()), str(args.app.resolve()), '--headless'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=45)
    output = result.stdout.decode(errors='replace')
    if args.log:
        args.log.write_text(output)
    for line in output.splitlines():
        if '[ASYNC ALERT REGRESSION]' in line:
            print(line)
    assert result.returncode == 0, output[-6500:]
    assert '[ASYNC ALERT REGRESSION] ALL PASS 6' in output, output[-6500:]
    assert '[ASYNC ALERT REGRESSION] FAIL' not in output
    assert output.count('Guest run loop continues while popup is visible') >= 6, output[-6500:]
    print('All six actual ARMv7 guest timer/ownership/callback cases passed.')


if __name__ == '__main__':
    main()
