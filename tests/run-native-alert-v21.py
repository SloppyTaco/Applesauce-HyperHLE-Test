"""Run the unchanged V20 UIKit fixture; stop only a simulator we booted.

CI's dedicated simulator is released before building the iPhone Rust core.
Already-running simulators are never shut down by this wrapper.
"""
import importlib.util
import json
from pathlib import Path
import subprocess


def booted_devices():
    result = subprocess.run(['xcrun', 'simctl', 'list', 'devices', 'available', '-j'],
                            check=True, capture_output=True, text=True)
    groups = json.loads(result.stdout)['devices']
    return {device['udid'] for group in groups.values() for device in group
            if device['state'] == 'Booted'}


def main():
    previously_booted = booted_devices()
    spec = importlib.util.spec_from_file_location(
        'native_alert_v20', Path(__file__).with_name('run-native-alert-v20.py'))
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    try:
        fixture.main()
    finally:
        for udid in sorted(booted_devices() - previously_booted):
            subprocess.run(['xcrun', 'simctl', 'shutdown', udid], check=True)
            print('Shut down isolated UIKit regression simulator:', udid)


if __name__ == '__main__':
    main()
