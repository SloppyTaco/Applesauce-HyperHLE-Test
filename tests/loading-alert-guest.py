#!/usr/bin/env python3
"""Original ARMv7 loading-alert guest; no SDK or game assets required.

The graphical V18 baseline either blocks in the native message box or, when
SDL cannot open it, invents a click and incorrectly dismisses the alert.
V19 must return from show, run a real NSTimer and deliver one programmatic dismissal.
The same guest also checks repeated show and asynchronous object ownership.
"""
import argparse
import importlib.util
import json
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
        'class', 'delegate', 'alert', 'title', 'timerclass', 'dateclass',
        'loop', 'date', 'clicked', 'will', 'did', 'finished')}
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
        for name in ('clicked', 'will', 'did', 'finished'):
            save(0, name)

    def new_alert(message_only=False):
        reset()
        g.literal(0, cstring('UIAlertView'))
        g.call('_objc_getClass')
        save(0, 'class')
        message('class', 'alloc')
        save(0, 'alert')
        selector('initWithTitle:message:delegate:cancelButtonTitle:otherButtonTitles:')
        load(0, 'alert')
        if message_only:
            g.literal(2, 0)
            load(3, 'title')
        else:
            load(2, 'title')
            g.literal(3, 0)
        load(12, 'delegate')
        g.code.append(0xe58dc000)
        g.literal(12, 0)
        g.code.extend([0xe58dc004, 0xe58dc008, 0xe58dc00c])
        g.call('_objc_msgSend')
        save(0, 'alert')

    def finish_with_timer(failure):
        selector('finishLoading:')
        g.code.append(0xe58d1004)
        load(12, 'delegate')
        g.code.append(0xe58dc000)
        g.literal(12, 0)
        g.code.extend([0xe58dc008, 0xe58dc00c])
        selector('scheduledTimerWithTimeInterval:target:selector:userInfo:repeats:')
        load(0, 'timerclass')
        lo, hi = struct.unpack('<2I', struct.pack('<d', 0.01))
        g.literal(2, lo)
        g.literal(3, hi)
        g.call('_objc_msgSend')
        selector('dateWithTimeIntervalSinceNow:')
        load(0, 'dateclass')
        lo, hi = struct.unpack('<2I', struct.pack('<d', 0.15))
        g.literal(2, lo)
        g.literal(3, hi)
        g.call('_objc_msgSend')
        save(0, 'date')
        selector('runUntilDate:')
        load(0, 'loop')
        load(2, 'date')
        g.call('_objc_msgSend')
        check('finished', 1, failure)
        check('clicked', 0, failure)
        check('will', 1, failure)
        check('did', 1, failure)

    cases = [('fail_timer', 'loading alert returns and timer dismisses it'),
             ('fail_repeat', 'repeated show retains one presentation only'),
             ('fail_owner', 'caller release is safe until asynchronous dismissal'),
             ('fail_message', 'message-only loading alert has no invented click')]
    g.code.append(0xe24dd020)
    g.message('[LOADING REGRESSION] START ARMv7\n')
    g.literal(0, cstring('NSObject'))
    g.call('_objc_getClass')
    save(0, 'class')
    imps = []
    for name, label, encoding in [
            ('alertView:clickedButtonAtIndex:', 'clicked_imp', 'v16@0:4@8i12'),
            ('alertView:willDismissWithButtonIndex:', 'will_imp', 'v16@0:4@8i12'),
            ('alertView:didDismissWithButtonIndex:', 'did_imp', 'v16@0:4@8i12'),
            ('finishLoading:', 'finish_imp', 'v12@0:4@8')]:
        selector(name)
        load(0, 'class')
        g.literal(2, 0)
        imps.append((len(g.code) - 1, label))
        g.literal(3, cstring(encoding))
        g.call('_class_addMethod')
        g.compare(1, 'fail_setup')
    message('class', 'new')
    save(0, 'delegate')
    for name, cell in [('NSTimer', 'timerclass'), ('NSDate', 'dateclass'),
                       ('NSRunLoop', 'class'), ('NSString', 'class')]:
        g.literal(0, cstring(name))
        g.call('_objc_getClass')
        save(0, cell)
        if name == 'NSRunLoop':
            message('class', 'currentRunLoop')
            save(0, 'loop')
        if name == 'NSString':
            message('class', 'stringWithUTF8String:',
                    cstring('Loading for the first time. Please wait...'))
            save(0, 'title')

    new_alert()
    g.message('[LOADING REGRESSION] BEFORE_SHOW\n')
    message('alert', 'show')
    g.message('[LOADING REGRESSION] AFTER_SHOW\n')
    message('alert', 'isVisible')
    g.compare(1, 'fail_timer')
    finish_with_timer('fail_timer')
    message('alert', 'isVisible')
    g.compare(0, 'fail_timer')
    message('alert', 'release')
    g.message('[LOADING REGRESSION] PASS 01 ' + cases[0][1] + '\n')

    new_alert()
    message('alert', 'show')
    message('alert', 'show')
    message('alert', 'retainCount')
    g.compare(2, 'fail_repeat')
    message('alert', 'dismissWithClickedButtonIndex:animated:', -1)
    message('alert', 'dismissWithClickedButtonIndex:animated:', -1)
    message('alert', 'retainCount')
    g.compare(1, 'fail_repeat')
    check('clicked', 0, 'fail_repeat')
    check('will', 1, 'fail_repeat')
    check('did', 1, 'fail_repeat')
    message('alert', 'release')
    g.message('[LOADING REGRESSION] PASS 02 ' + cases[1][1] + '\n')

    new_alert()
    message('alert', 'show')
    message('alert', 'release')
    message('alert', 'retainCount')
    g.compare(1, 'fail_owner')
    finish_with_timer('fail_owner')
    g.message('[LOADING REGRESSION] PASS 03 ' + cases[2][1] + '\n')

    new_alert(message_only=True)
    message('alert', 'show')
    finish_with_timer('fail_message')
    message('alert', 'isVisible')
    g.compare(0, 'fail_message')
    message('alert', 'release')
    g.message('[LOADING REGRESSION] PASS 04 ' + cases[3][1] + '\n')
    g.message('[LOADING REGRESSION] ALL PASS 4\n')
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
        if field == 'will':
            selector('dismissWithClickedButtonIndex:animated:')
            g.code.append(0xe1a00004)
            g.literal(2, -1)
            g.literal(3, 0)
            g.call('_objc_msgSend')
        g.code.append(0xe8bd80b0)
    g.labels['finish_imp'] = len(g.code)
    g.code.append(0xe92d40b0)
    load(0, 'finished')
    g.code.append(0xe2800001)
    save(0, 'finished')
    message('alert', 'dismissWithClickedButtonIndex:animated:', -1)
    g.code.append(0xe8bd80b0)
    for index, (label, name) in enumerate(
            [('fail_setup', 'guest delegate setup'), *cases], 1):
        g.labels[label] = len(g.code)
        g.message('[LOADING REGRESSION] FAIL ' + name + '\n')
        g.literal(0, index)
        g.call('_exit')
        g.code.append(0xeafffffe)
    for position, label in imps:
        g.code[position] = base.TEXT_BASE + base.ENTRY_OFFSET + g.labels[label] * 4
    for position, label, condition in g.branches:
        g.code[position] = (condition << 28 | 0x0a000000 |
                            (g.labels[label] - position - 2) & 0xffffff)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'LoadingAlertRegression').write_bytes(
        base.executable(g, base.u32(*g.code)))
    (destination / 'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': 'io.github.sloppytaco.loadingalertregression',
        'CFBundleName': 'LoadingAlertRegression',
        'CFBundleExecutable': 'LoadingAlertRegression',
        'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1.0',
        'MinimumOSVersion': '2.0', 'UIDeviceFamily': [1]}))
    return len(cases)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, required=True)
    parser.add_argument('--emulator', type=Path)
    parser.add_argument('--log', type=Path)
    parser.add_argument('--graphical', action='store_true')
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    count = generate(args.app)
    if args.emulator is None:
        print(json.dumps({'cases': count, 'app': str(args.app)}))
        return
    command = [str(args.emulator.resolve()), str(args.app.resolve())]
    if not args.graphical:
        command.append('--headless')
    try:
        run = subprocess.run(command, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,
                             timeout=8 if args.baseline else 30)
        output = run.stdout.decode(errors='replace')
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b'').decode(errors='replace')
        if args.log:
            args.log.write_text(output)
        assert args.baseline and args.graphical, output[-5000:]
        assert '[LOADING REGRESSION] BEFORE_SHOW' in output, output[-5000:]
        assert 'UIAlertView show (SDL2 dialog)' in output, output[-5000:]
        assert '[LOADING REGRESSION] AFTER_SHOW' not in output, output[-5000:]
        assert 'panicked at' not in output, output[-5000:]
        print('V18 reproduced the native buttonless-alert blocking path.')
        return
    if args.log:
        args.log.write_text(output)
    if args.baseline:
        assert args.graphical, 'A native baseline needs a graphical run.'
        assert run.returncode == 2, output[-5000:]
        assert '[LOADING REGRESSION] BEFORE_SHOW' in output, output[-5000:]
        assert 'UIAlertView show (SDL2 dialog)' in output, output[-5000:]
        assert '[ALERT CALLBACK v18] Native button 0 returned; dispatching one user click' in output, output[-5000:]
        assert '[LOADING REGRESSION] FAIL loading alert returns and timer dismisses it' in output, output[-5000:]
        assert 'panicked at' not in output, output[-5000:]
        print('V18 native-dialog fallback incorrectly synthesized a click and hid the loading alert.')
        return
    for line in output.splitlines():
        if '[LOADING REGRESSION]' in line or '[ALERT LOADING v19]' in line:
            print(line)
    assert run.returncode == 0, output[-5000:]
    assert '[LOADING REGRESSION] ALL PASS 4' in output, output[-5000:]
    assert '[ALERT LOADING v19] Buttonless loading alert is nonblocking' in output
    assert '[LOADING REGRESSION] FAIL' not in output
    assert '[ALERT CALLBACK v18] Native button' not in output
    print('All four real guest loading-alert cases passed.')


if __name__ == '__main__':
    main()
