#!/usr/bin/env python3
"""Original ARMv7 guest reproducing the real nested UIAlertView dismissal.

No iOS SDK, original game code, or copyrighted game assets are required.
The callbacks are genuine guest IMPs installed with class_addMethod, not mocks.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess

spec=importlib.util.spec_from_file_location('wide_guest',Path(__file__).with_name('wide-string-guest.py'))
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
base.IMPORTS=['_objc_getClass','_sel_registerName','_objc_msgSend',
              '_class_addMethod','_write','_exit','_memcmp']


def generate(destination):
    g=base.Guest()
    cells={name:g.blob(base.u32(0)) for name in ('class','delegate','alert','title','clicked','will','did')}
    names={}
    def cstring(text):
        if text not in names:names[text]=g.blob(text.encode()+b'\0')
        return names[text]
    def save(reg,name):
        g.literal(12,cells[name]);g.code.append(0xe58c0000|reg<<12)
    def load(reg,name):
        g.literal(reg,cells[name]);g.code.append(0xe5900000|reg<<16|reg<<12)
    def selector(text):
        g.literal(0,cstring(text));g.call('_sel_registerName');g.code.append(0xe1a01000)
    def message(target,text,arg=0):
        selector(text);load(0,target);g.literal(2,arg);g.literal(3,0);g.call('_objc_msgSend')
    def check(name,expected,label):
        load(0,name);g.compare(expected,label)
    def counts(clicked,will,did,label):
        check('clicked',clicked,label);check('will',will,label);check('did',did,label)
    def reset():
        g.literal(0,0)
        for name in ('clicked','will','did'):save(0,name)
    def passed(n,name):g.message(f'[ALERT REGRESSION] PASS {n:02d} {name}\n')
    tests=[('fail_empty','empty placeholder has no synthetic click'),
           ('fail_click','one native user click with nested programmatic dismissal'),
           ('fail_duplicate','duplicate dismissal and stale click are ignored'),
           ('fail_program','programmatic dismissal never invokes clicked callback')]
    g.code.append(0xe24dd020)
    g.message('[ALERT REGRESSION] START ARMv7\n')
    # Attach the test-only guest IMPs to NSObject in this isolated test app.
    # The base emulator's dynamic-class allocator is only a placeholder;
    # class_addMethod on a genuine registered class is fully implemented.
    g.literal(0,cstring('NSObject'));g.call('_objc_getClass');save(0,'class')
    imps=[]
    for sel,label in [('alertView:clickedButtonAtIndex:','clicked_imp'),
                      ('alertView:willDismissWithButtonIndex:','will_imp'),
                      ('alertView:didDismissWithButtonIndex:','did_imp')]:
        selector(sel);load(0,'class')
        g.literal(2,0);imps.append((len(g.code)-1,label))
        g.literal(3,cstring('v16@0:4@8i12'));g.call('_class_addMethod')
        g.compare(1,'fail_setup')
    message('class','new');save(0,'delegate')
    g.literal(0,cstring('UIAlertView'));g.call('_objc_getClass');save(0,'class')
    message('class','alloc');save(0,'alert')
    selector('initWithTitle:message:delegate:cancelButtonTitle:otherButtonTitles:')
    load(0,'alert');g.literal(2,0);g.literal(3,0)
    load(12,'delegate');g.code.append(0xe58dc000)
    g.literal(12,0);g.code.extend([0xe58dc004,0xe58dc008,0xe58dc00c])
    g.call('_objc_msgSend');save(0,'alert')
    message('alert','show')
    counts(0,1,1,'fail_empty')
    message('alert','isVisible');g.compare(0,'fail_empty')
    passed(1,tests[0][1])

    g.literal(0,cstring('NSString'));g.call('_objc_getClass');save(0,'class')
    message('class','stringWithUTF8String:',cstring('Regression alert'));save(0,'title')
    selector('setTitle:');load(0,'alert');load(2,'title');g.call('_objc_msgSend')
    reset();message('alert','show')
    message('alert','isVisible');g.compare(1,'fail_click')
    message('alert','_touchHLE_userClickedButton:',1)
    counts(1,1,1,'fail_click')
    message('alert','isVisible');g.compare(0,'fail_click')
    passed(2,tests[1][1])

    message('alert','dismissWithClickedButtonIndex:animated:',0)
    message('alert','_touchHLE_userClickedButton:',1)
    counts(1,1,1,'fail_duplicate')
    passed(3,tests[2][1])

    reset();message('alert','show')
    message('alert','dismissWithClickedButtonIndex:animated:',-1)
    counts(0,1,1,'fail_program')
    message('alert','isVisible');g.compare(0,'fail_program')
    passed(4,tests[3][1])
    g.message('[ALERT REGRESSION] ALL PASS 4\n');g.literal(0,0);g.call('_exit')
    g.code.append(0xeafffffe)

    for field in ('clicked','will','did'):
        g.labels[field+'_imp']=len(g.code)
        g.code.append(0xe92d40b0) # push r4,r5,r7,lr, keeping 8-byte alignment
        g.code.append(0xe1a04002) # preserve alert argument in callee-saved r4
        load(0,field);g.code.append(0xe2800001);save(0,field)
        if field=='clicked':
            g.code.append(0xe3500001);g.branch('recursion_confirmed',8)
        if field in ('clicked','will'):
            selector('dismissWithClickedButtonIndex:animated:')
            g.code.append(0xe1a00004);g.literal(2,0);g.literal(3,0);g.call('_objc_msgSend')
        g.code.append(0xe8bd80b0)
    g.labels['recursion_confirmed']=len(g.code)
    g.message('[ALERT REGRESSION] BASELINE recursive clicked callback reproduced\n')
    g.literal(0,71);g.call('_exit');g.code.append(0xeafffffe)
    for n,(label,name) in enumerate([('fail_setup','dynamic guest delegate setup'),*tests],1):
        g.labels[label]=len(g.code)
        g.message(f'[ALERT REGRESSION] FAIL {name}\n')
        g.literal(0,n);g.call('_exit');g.code.append(0xeafffffe)
    for pos,label in imps:
        g.code[pos]=base.TEXT_BASE+base.ENTRY_OFFSET+g.labels[label]*4
    for pos,label,condition in g.branches:
        g.code[pos]=condition<<28|0x0a000000|(g.labels[label]-pos-2)&0xffffff
    destination.mkdir(parents=True,exist_ok=True)
    (destination/'AlertDismissalRegression').write_bytes(base.executable(g,base.u32(*g.code)))
    (destination/'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier':'io.github.sloppytaco.alertdismissalregression',
        'CFBundleName':'AlertDismissalRegression','CFBundleExecutable':'AlertDismissalRegression',
        'CFBundlePackageType':'APPL','CFBundleVersion':'1.0','MinimumOSVersion':'2.0','UIDeviceFamily':[1]}))
    return 4


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--app',type=Path,required=True)
    p.add_argument('--emulator',type=Path)
    p.add_argument('--log',type=Path)
    p.add_argument('--baseline',action='store_true')
    args=p.parse_args();count=generate(args.app)
    if args.emulator is None:
        print(json.dumps({'cases':count,'app':str(args.app)}));return
    run=subprocess.run([str(args.emulator.resolve()),str(args.app.resolve()),'--headless'],
                       stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=45)
    output=run.stdout.decode(errors='replace')
    if args.log:args.log.write_text(output)
    for line in output.splitlines():
        if '[ALERT REGRESSION]' in line:print(line)
    if args.baseline:
        assert run.returncode==71,output[-5000:]
        assert '[ALERT REGRESSION] BASELINE recursive clicked callback reproduced' in output,output[-5000:]
        print('V17 reproduced the original nested-dismissal freeze path.')
    else:
        assert run.returncode==0,output[-5000:]
        assert '[ALERT REGRESSION] ALL PASS 4' in output,output[-5000:]
        assert '[ALERT REGRESSION] FAIL' not in output
        print('All 4 real guest alert callback tests passed.')


if __name__=='__main__':main()
