"""Compile/run the actual UIKit bridge on an iOS simulator (no private assets)."""
import argparse
import json
from pathlib import Path
import platform
import plistlib
import subprocess
import tempfile


def run(*arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    devices = json.loads(run('xcrun', 'simctl', 'list', 'devices', 'available', '-j',
                             stdout=subprocess.PIPE).stdout)['devices']
    options = [device for runtime, group in devices.items() if 'iOS' in runtime
               for device in group if device['isAvailable'] and 'iPhone' in device['name']]
    assert options, 'No available iOS simulator'
    device = options[0]
    udid = device['udid']
    if device['state'] != 'Booted':
        run('xcrun', 'simctl', 'boot', udid)
    run('xcrun', 'simctl', 'bootstatus', udid, '-b', timeout=180)
    with tempfile.TemporaryDirectory(prefix='alert-v20-') as directory:
        app = Path(directory) / 'AlertV20.app'
        app.mkdir()
        info = {
            'CFBundleIdentifier': 'io.github.sloppytaco.alertv20regression',
            'CFBundleName': 'AlertV20', 'CFBundleExecutable': 'AlertV20',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '1.0', 'MinimumOSVersion': '16.0',
            'UIDeviceFamily': [1], 'UILaunchScreen': {},
            'UISupportedInterfaceOrientations': ['UIInterfaceOrientationPortrait'],
            'UIApplicationSceneManifest': {
                'UIApplicationSupportsMultipleScenes': False,
                'UISceneConfigurations': {'UIWindowSceneSessionRoleApplication': [{
                    'UISceneConfigurationName': 'Regression',
                    'UISceneDelegateClassName': 'TouchHLETestSceneDelegate'}]}}}
        (app / 'Info.plist').write_bytes(plistlib.dumps(info))
        sdk = run('xcrun', '--sdk', 'iphonesimulator', '--show-sdk-path',
                  stdout=subprocess.PIPE).stdout.strip()
        run('xcrun', '--sdk', 'iphonesimulator', 'clang', '-fobjc-arc', '-fblocks',
            '-arch', platform.machine(), '-isysroot', sdk,
            '-mios-simulator-version-min=16.0', '-framework', 'UIKit',
            '-framework', 'Foundation', '-framework', 'CoreFoundation',
            str(Path(__file__).with_name('native-alert-v20.m')), '-o', str(app / 'AlertV20'))
        run('codesign', '--force', '--sign', '-', str(app))
        run('xcrun', 'simctl', 'install', udid, str(app))
        launched = subprocess.run(['xcrun', 'simctl', 'launch', '--console', udid,
            info['CFBundleIdentifier']], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=90)
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(launched.stdout)
        for line in launched.stdout.splitlines():
            if '[NATIVE ALERT REGRESSION]' in line: print(line)
        assert '[NATIVE ALERT REGRESSION] ALL PASS 4' in launched.stdout, launched.stdout[-6000:]
        assert '[NATIVE ALERT REGRESSION] FAIL' not in launched.stdout
        print('Four actual UIKit simulator state/event-boundary cases passed; hardware tap still needs phone verification.')


if __name__ == '__main__':
    main()
