"""Real UIKit state checks and external XCUI taps with an occupied main queue.

Uses only public XCTest/UIKit APIs and contains no private game assets.
Stops only simulators booted by this invocation.
"""
import argparse
import json
from pathlib import Path
import plistlib
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent

def run(*arguments, **kwargs):
    return subprocess.run(arguments, check=True, text=True, **kwargs)

def devices():
    return json.loads(run('xcrun', 'simctl', 'list', 'devices', 'available', '-j',
                         stdout=subprocess.PIPE).stdout)['devices']

def booted():
    return {d['udid'] for group in devices().values() for d in group if d['state'] == 'Booted'}

def pbx(value):
    if isinstance(value, dict):
        return '{ ' + ' '.join(json.dumps(k) + ' = ' + pbx(v) + ';' for k, v in value.items()) + ' }'
    if isinstance(value, list):
        return '( ' + ', '.join(pbx(v) for v in value) + ' )'
    if isinstance(value, str) and value.startswith('@') and len(value) == 25:
        return value[1:]
    return json.dumps(str(value))

def project(directory, baseline):
    objects = {}
    def add(kind, **values):
        key = f'A{len(objects)+1:023X}'
        objects[key] = {'isa': kind, **values}
        return '@' + key
    app_file = add('PBXFileReference', lastKnownFileType='sourcecode.c.objc',
                   path=str(ROOT / 'native-alert-taps-v22.m'), sourceTree='<absolute>')
    ui_file = add('PBXFileReference', lastKnownFileType='sourcecode.swift',
                  path=str(ROOT / 'native-alert-taps-v22.swift'), sourceTree='<absolute>')
    app_product = add('PBXFileReference', explicitFileType='wrapper.application',
                      path='AlertV22.app', sourceTree='BUILT_PRODUCTS_DIR')
    ui_product = add('PBXFileReference', explicitFileType='wrapper.cfbundle',
                     path='AlertTapTests.xctest', sourceTree='BUILT_PRODUCTS_DIR')
    app_build = add('PBXBuildFile', fileRef=app_file)
    ui_build = add('PBXBuildFile', fileRef=ui_file)
    app_sources = add('PBXSourcesBuildPhase', buildActionMask=2147483647, files=[app_build], runOnlyForDeploymentPostprocessing=0)
    ui_sources = add('PBXSourcesBuildPhase', buildActionMask=2147483647, files=[ui_build], runOnlyForDeploymentPostprocessing=0)
    app_frameworks = add('PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    ui_frameworks = add('PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    products = add('PBXGroup', children=[app_product, ui_product], name='Products', sourceTree='<group>')
    main_group = add('PBXGroup', children=[app_file, ui_file, products], sourceTree='<group>')
    common = {'CLANG_ENABLE_MODULES': 'YES', 'CLANG_ENABLE_OBJC_ARC': 'YES',
              'IPHONEOS_DEPLOYMENT_TARGET': '16.0', 'SDKROOT': 'iphonesimulator',
              'CODE_SIGNING_ALLOWED': 'NO', 'SWIFT_VERSION': '5.0',
              'TARGETED_DEVICE_FAMILY': '1', 'SUPPORTED_PLATFORMS': 'iphonesimulator'}
    def configs(settings):
        ids = [add('XCBuildConfiguration', name=n, buildSettings=settings) for n in ['Debug', 'Release']]
        return add('XCConfigurationList', buildConfigurations=ids, defaultConfigurationIsVisible=0, defaultConfigurationName='Debug')
    project_configs = configs(common)
    app_configs = configs({**common, 'PRODUCT_BUNDLE_IDENTIFIER': 'io.github.sloppytaco.alertv22taps',
                           'PRODUCT_NAME': 'AlertV22', 'INFOPLIST_FILE': str(directory / 'Info.plist'),
                           'OTHER_CFLAGS': ['$(inherited)'] + (['-DTOUCHHLE_ALERT_BASELINE=1'] if baseline else []),
                           'OTHER_LDFLAGS': ['$(inherited)', '-framework', 'UIKit', '-framework', 'Foundation', '-framework', 'CoreFoundation']})
    ui_configs = configs({**common, 'PRODUCT_BUNDLE_IDENTIFIER': 'io.github.sloppytaco.alertv22taps.tests',
                          'PRODUCT_NAME': 'AlertTapTests', 'GENERATE_INFOPLIST_FILE': 'YES',
                          'TEST_TARGET_NAME': 'AlertV22', 'ENABLE_TESTING_SEARCH_PATHS': 'YES',
                          'LD_RUNPATH_SEARCH_PATHS': ['$(inherited)', '@executable_path/Frameworks', '@loader_path/Frameworks']})
    app_target = add('PBXNativeTarget', name='AlertV22', productName='AlertV22',
                     productReference=app_product, productType='com.apple.product-type.application',
                     buildConfigurationList=app_configs, buildPhases=[app_sources, app_frameworks], buildRules=[], dependencies=[])
    project_id = '@' + f'A{len(objects)+1:023X}'
    project_object = add('PBXProject', attributes={'LastUpgradeCheck': '2600',
        'TargetAttributes': {}}, buildConfigurationList=project_configs,
        compatibilityVersion='Xcode 14.0', developmentRegion='en', hasScannedForEncodings=0,
        knownRegions=['en', 'Base'], mainGroup=main_group, productRefGroup=products,
        projectDirPath='', projectRoot='', targets=[])
    assert project_object == project_id
    proxy = add('PBXContainerItemProxy', containerPortal=project_id, proxyType=1,
                remoteGlobalIDString=app_target, remoteInfo='AlertV22')
    dependency = add('PBXTargetDependency', target=app_target, targetProxy=proxy)
    ui_target = add('PBXNativeTarget', name='AlertTapTests', productName='AlertTapTests',
                    productReference=ui_product, productType='com.apple.product-type.bundle.ui-testing',
                    buildConfigurationList=ui_configs, buildPhases=[ui_sources, ui_frameworks], buildRules=[], dependencies=[dependency])
    objects[project_id[1:]]['targets'] = [app_target, ui_target]
    objects[project_id[1:]]['attributes']['TargetAttributes'][ui_target[1:]] = {'TestTargetID': app_target}
    proj = directory / 'AlertTaps.xcodeproj'
    proj.mkdir()
    (proj / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + pbx({'archiveVersion': 1, 'classes': {},
        'objectVersion': 56, 'objects': objects, 'rootObject': project_id}) + '\n')
    info = {'CFBundleIdentifier': '$(PRODUCT_BUNDLE_IDENTIFIER)', 'CFBundleName': 'AlertV22',
            'CFBundleExecutable': 'AlertV22', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '1.0', 'MinimumOSVersion': '16.0', 'UIDeviceFamily': [1],
            'UILaunchScreen': {}, 'UISupportedInterfaceOrientations': ['UIInterfaceOrientationPortrait'],
            'UIApplicationSceneManifest': {'UIApplicationSupportsMultipleScenes': False,
                'UISceneConfigurations': {'UIWindowSceneSessionRoleApplication': [{
                    'UISceneConfigurationName': 'Tap', 'UISceneDelegateClassName': 'TouchHLETapScene'}]}}}
    (directory / 'Info.plist').write_bytes(plistlib.dumps(info))
    schemes = proj / 'xcshareddata/xcschemes'
    schemes.mkdir(parents=True)
    def entry(target, name, **flags):
        attrs = ' '.join(k+'="'+v+'"' for k, v in flags.items())
        return f'<BuildActionEntry {attrs}><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target[1:]}" BuildableName="{name}" BlueprintName="{name.split(".")[0]}" ReferencedContainer="container:AlertTaps.xcodeproj"/></BuildActionEntry>'
    testref = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ui_target[1:]}" BuildableName="AlertTapTests.xctest" BlueprintName="AlertTapTests" ReferencedContainer="container:AlertTaps.xcodeproj"/>'
    env = '<EnvironmentVariables><EnvironmentVariable key="TOUCHHLE_BASELINE_EXPECTED" value="1" isEnabled="YES"/></EnvironmentVariables>' if baseline else ''
    scheme = '<Scheme LastUpgradeVersion="2600" version="1.7"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>'
    scheme += entry(app_target, 'AlertV22.app', buildForTesting='YES', buildForRunning='YES', buildForProfiling='NO', buildForArchiving='NO', buildForAnalyzing='YES')
    scheme += entry(ui_target, 'AlertTapTests.xctest', buildForTesting='YES', buildForRunning='NO', buildForProfiling='NO', buildForArchiving='NO', buildForAnalyzing='YES')
    scheme += '</BuildActionEntries></BuildAction><TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="NO"><Testables><TestableReference skipped="NO">' + testref + '</TestableReference></Testables>' + env + '</TestAction></Scheme>'
    (schemes / 'AlertTaps.xcscheme').write_text(scheme)
    return proj

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    previous = booted()
    outputs = []
    args.log.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Retain the four original ownership/queue/cleanup tests, compiled
        # against the NEW bridge. They do not substitute for the taps below.
        with tempfile.TemporaryDirectory(prefix='v22-state-') as folder:
            temp = Path(folder)
            source = (ROOT / 'native-alert-v20.m').read_text()
            source = source.replace('"../patches/async-alert-uikit-v20.inc"',
                                    json.dumps(str(ROOT.parent / 'patches/async-alert-uikit-v22.inc')))
            source = source.replace('state.controller.actions.count', 'state.controller.buttons.count')
            (temp / 'native-alert-v20.m').write_text(source)
            (temp / 'run-native-alert-v20.py').write_bytes((ROOT / 'run-native-alert-v20.py').read_bytes())
            result = run(sys.executable, str(temp / 'run-native-alert-v20.py'), '--log',
                         str(args.log.with_name('native-state-v22.log')), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            outputs.append(result.stdout)
        sdk = run('xcrun', '--sdk', 'iphonesimulator', '--show-sdk-version', stdout=subprocess.PIPE).stdout.strip()
        marker = 'iOS-' + '-'.join(sdk.split('.')[:2])
        selected = next(d for runtime, group in devices().items() if marker in runtime
                        for d in group if d['isAvailable'] and 'iPhone' in d['name'])
        udid = selected['udid']
        for baseline in (True, False):
            label = 'baseline-v20' if baseline else 'fixed-v22'
            with tempfile.TemporaryDirectory(prefix='v22-taps-') as folder:
                folder = Path(folder)
                proj = project(folder, baseline)
                log = args.log.with_name('native-taps-' + label + '-xcode.log')
                with log.open('w') as output:
                    process = subprocess.run(['xcodebuild', 'test', '-project', str(proj),
                        '-scheme', 'AlertTaps', '-destination', 'platform=iOS Simulator,id=' + udid,
                        '-derivedDataPath', str(folder / 'DerivedData'), '-parallel-testing-enabled', 'NO',
                        '-maximum-concurrent-test-simulator-destinations', '1',
                        'CODE_SIGNING_ALLOWED=NO'], text=True, stdout=output, stderr=subprocess.STDOUT, timeout=300)
                container = run('xcrun', 'simctl', 'get_app_container', udid,
                    'io.github.sloppytaco.alertv22taps', 'data', stdout=subprocess.PIPE).stdout.strip()
                fixture = Path(container) / 'Documents/native-taps-v22.log'
                text = fixture.read_text() if fixture.is_file() else ''
                args.log.with_name('native-taps-' + label + '.log').write_text(text)
                outputs.append(text)
                print(text)
                assert process.returncode == 0, log.read_text()[-18000:]
                if baseline:
                    assert '[NATIVE TAP v22] BASELINE pending after external tap' in text
                    assert 'BASELINE handler delivered' not in text
                else:
                    assert '[NATIVE TAP v22] ALL PASS 4 actual taps' in text
                    assert '[NATIVE TAP v22] FAIL' not in text
        print('V22: four native state cases plus four external XCUI taps passed; V20 lost handler reproduced in occupied main GCD context.')
    finally:
        args.log.write_text('\n'.join(outputs))
        for udid in sorted(booted() - previous):
            run('xcrun', 'simctl', 'shutdown', udid)
            print('Shut down only simulator booted by this fixture:', udid)

if __name__ == '__main__':
    main()
