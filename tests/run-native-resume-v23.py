"""Native queue-availability and external interruption/input regression.

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
    app_file = add('PBXFileReference', lastKnownFileType='sourcecode.swift',
                   path=str(ROOT / 'native-resume-v23.swift'), sourceTree='<absolute>')
    ui_file = add('PBXFileReference', lastKnownFileType='sourcecode.swift',
                  path=str(ROOT / 'native-resume-taps-v23.swift'), sourceTree='<absolute>')
    app_product = add('PBXFileReference', explicitFileType='wrapper.application',
                      path='ResumeV23.app', sourceTree='BUILT_PRODUCTS_DIR')
    ui_product = add('PBXFileReference', explicitFileType='wrapper.cfbundle',
                     path='ResumeTapTests.xctest', sourceTree='BUILT_PRODUCTS_DIR')
    snippet = (ROOT.parent / 'patches/main-run-loop-launch-v23.swift').read_text()
    helper = directory / 'ProductionRunLoopLaunch.swift'
    helper.write_text('import Foundation\nimport UIKit\n' + snippet)
    helper_file = add('PBXFileReference', lastKnownFileType='sourcecode.swift', path=str(helper), sourceTree='<absolute>')
    app_build = add('PBXBuildFile', fileRef=app_file)
    helper_build = add('PBXBuildFile', fileRef=helper_file)
    ui_build = add('PBXBuildFile', fileRef=ui_file)
    app_sources = add('PBXSourcesBuildPhase', buildActionMask=2147483647, files=[app_build, helper_build], runOnlyForDeploymentPostprocessing=0)
    ui_sources = add('PBXSourcesBuildPhase', buildActionMask=2147483647, files=[ui_build], runOnlyForDeploymentPostprocessing=0)
    app_frameworks = add('PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    ui_frameworks = add('PBXFrameworksBuildPhase', buildActionMask=2147483647, files=[], runOnlyForDeploymentPostprocessing=0)
    products = add('PBXGroup', children=[app_product, ui_product], name='Products', sourceTree='<group>')
    main_group = add('PBXGroup', children=[app_file, helper_file, ui_file, products], sourceTree='<group>')
    common = {'CLANG_ENABLE_MODULES': 'YES', 'CLANG_ENABLE_OBJC_ARC': 'YES',
              'IPHONEOS_DEPLOYMENT_TARGET': '16.0', 'SDKROOT': 'iphonesimulator',
              'CODE_SIGNING_ALLOWED': 'NO', 'SWIFT_VERSION': '5.0',
              'TARGETED_DEVICE_FAMILY': '1', 'SUPPORTED_PLATFORMS': 'iphonesimulator'}
    def configs(settings):
        ids = [add('XCBuildConfiguration', name=n, buildSettings=settings) for n in ['Debug', 'Release']]
        return add('XCConfigurationList', buildConfigurations=ids, defaultConfigurationIsVisible=0, defaultConfigurationName='Debug')
    project_configs = configs(common)
    app_configs = configs({**common, 'PRODUCT_BUNDLE_IDENTIFIER': 'io.github.sloppytaco.resumev23',
                           'PRODUCT_NAME': 'ResumeV23', 'INFOPLIST_FILE': str(directory / 'Info.plist'),
                           'SWIFT_STRICT_CONCURRENCY': 'complete',
                           'OTHER_LDFLAGS': ['$(inherited)', '-framework', 'UIKit', '-framework', 'Foundation', '-framework', 'CoreFoundation']})
    ui_configs = configs({**common, 'PRODUCT_BUNDLE_IDENTIFIER': 'io.github.sloppytaco.resumev23.tests',
                          'PRODUCT_NAME': 'ResumeTapTests', 'GENERATE_INFOPLIST_FILE': 'YES',
                          'TEST_TARGET_NAME': 'ResumeV23', 'ENABLE_TESTING_SEARCH_PATHS': 'YES',
                          'LD_RUNPATH_SEARCH_PATHS': ['$(inherited)', '@executable_path/Frameworks', '@loader_path/Frameworks']})
    app_target = add('PBXNativeTarget', name='ResumeV23', productName='ResumeV23',
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
                remoteGlobalIDString=app_target, remoteInfo='ResumeV23')
    dependency = add('PBXTargetDependency', target=app_target, targetProxy=proxy)
    ui_target = add('PBXNativeTarget', name='ResumeTapTests', productName='ResumeTapTests',
                    productReference=ui_product, productType='com.apple.product-type.bundle.ui-testing',
                    buildConfigurationList=ui_configs, buildPhases=[ui_sources, ui_frameworks], buildRules=[], dependencies=[dependency])
    objects[project_id[1:]]['targets'] = [app_target, ui_target]
    objects[project_id[1:]]['attributes']['TargetAttributes'][ui_target[1:]] = {'TestTargetID': app_target}
    proj = directory / 'ResumeTaps.xcodeproj'
    proj.mkdir()
    (proj / 'project.pbxproj').write_text('// !$*UTF8*$!\n' + pbx({'archiveVersion': 1, 'classes': {},
        'objectVersion': 56, 'objects': objects, 'rootObject': project_id}) + '\n')
    info = {'CFBundleIdentifier': '$(PRODUCT_BUNDLE_IDENTIFIER)', 'CFBundleName': 'ResumeV23',
            'CFBundleExecutable': 'ResumeV23', 'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '1.0', 'MinimumOSVersion': '16.0', 'UIDeviceFamily': [1],
            'UILaunchScreen': {}, 'UISupportedInterfaceOrientations': ['UIInterfaceOrientationLandscapeLeft'],
            'UIApplicationSceneManifest': {'UIApplicationSupportsMultipleScenes': False,
                'UISceneConfigurations': {'UIWindowSceneSessionRoleApplication': [{
                    'UISceneConfigurationName': 'Tap', 'UISceneDelegateClassName': 'ResumeScene'}]}}}
    (directory / 'Info.plist').write_bytes(plistlib.dumps(info))
    schemes = proj / 'xcshareddata/xcschemes'
    schemes.mkdir(parents=True)
    def entry(target, name, **flags):
        attrs = ' '.join(k+'="'+v+'"' for k, v in flags.items())
        return f'<BuildActionEntry {attrs}><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target[1:]}" BuildableName="{name}" BlueprintName="{name.split(".")[0]}" ReferencedContainer="container:ResumeTaps.xcodeproj"/></BuildActionEntry>'
    testref = f'<BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ui_target[1:]}" BuildableName="ResumeTapTests.xctest" BlueprintName="ResumeTapTests" ReferencedContainer="container:ResumeTaps.xcodeproj"/>'
    env = '<EnvironmentVariables><EnvironmentVariable key="RESUME_BASELINE_EXPECTED" value="1" isEnabled="YES"/></EnvironmentVariables>' if baseline else ''
    scheme = '<Scheme LastUpgradeVersion="2600" version="1.7"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries>'
    scheme += entry(app_target, 'ResumeV23.app', buildForTesting='YES', buildForRunning='YES', buildForProfiling='NO', buildForArchiving='NO', buildForAnalyzing='YES')
    scheme += entry(ui_target, 'ResumeTapTests.xctest', buildForTesting='YES', buildForRunning='NO', buildForProfiling='NO', buildForArchiving='NO', buildForAnalyzing='YES')
    scheme += '</BuildActionEntries></BuildAction><TestAction buildConfiguration="Debug" selectedDebuggerIdentifier="Xcode.DebuggerFoundation.Debugger.LLDB" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.LLDB" shouldUseLaunchSchemeArgsEnv="NO"><Testables><TestableReference skipped="NO">' + testref + '</TestableReference></Testables>' + env + '</TestAction></Scheme>'
    (schemes / 'ResumeTaps.xcscheme').write_text(scheme)
    return proj

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', type=Path, required=True)
    args = parser.parse_args()
    previous = booted()
    outputs = []
    args.log.parent.mkdir(parents=True, exist_ok=True)
    try:
        sdk = run('xcrun', '--sdk', 'iphonesimulator', '--show-sdk-version', stdout=subprocess.PIPE).stdout.strip()
        marker = 'iOS-' + '-'.join(sdk.split('.')[:2])
        selected = next(d for runtime, group in devices().items() if marker in runtime
                        for d in group if d['isAvailable'] and 'iPhone' in d['name'])
        udid = selected['udid']
        for baseline in (True, False):
            label = 'baseline-dispatch-v22' if baseline else 'fixed-runloop-v23'
            with tempfile.TemporaryDirectory(prefix='v23-resume-') as folder:
                folder = Path(folder)
                proj = project(folder, baseline)
                log = args.log.with_name('native-resume-' + label + '-xcode.log')
                with log.open('w') as output:
                    process = subprocess.run(['xcodebuild', 'test', '-project', str(proj),
                        '-scheme', 'ResumeTaps', '-destination', 'platform=iOS Simulator,id=' + udid,
                        '-derivedDataPath', str(folder / 'DerivedData'), '-parallel-testing-enabled', 'NO',
                        '-maximum-concurrent-test-simulator-destinations', '1',
                        'CODE_SIGNING_ALLOWED=NO'], text=True, stdout=output, stderr=subprocess.STDOUT, timeout=360)
                container = run('xcrun', 'simctl', 'get_app_container', udid,
                    'io.github.sloppytaco.resumev23', 'data', stdout=subprocess.PIPE).stdout.strip()
                fixture = Path(container) / 'Documents/native-resume-v23.log'
                content = fixture.read_text() if fixture.is_file() else ''
                args.log.with_name('native-resume-' + label + '.log').write_text(content)
                outputs.append(content)
                print(content)
                assert process.returncode == 0, log.read_text()[-20000:]
                if baseline:
                    assert 'BASELINE queue blocked while heartbeat advances' in content
                    assert 'PASS main dispatch completion serviced inside core' not in content
                else:
                    assert 'PASS main dispatch completion serviced inside core' in content
                    assert 'ALL PASS 5 actual taps, 3 interruptions, one main-thread core entry' in content
                    assert 'RETURN core; entry count 1; main thread true' in content
                    assert '[NATIVE RESUME v23] FAIL' not in content
        print('V23: main-dispatch starvation reproduced; production timer services queued completions and five actual taps across Home/Control Center/Home.')
    finally:
        args.log.write_text('\n'.join(outputs))
        for udid in sorted(booted() - previous):
            run('xcrun', 'simctl', 'shutdown', udid)
            print('Shut down only simulator booted by this fixture:', udid)

if __name__ == '__main__':
    main()
