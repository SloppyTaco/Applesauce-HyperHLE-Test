"""Change only the native launch entry; retain the complete working V22 core."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
host = ROOT / 'applesauce/platform/ios/Sources/NativeHost.swift'
snippet = (ROOT / 'patches/main-run-loop-launch-v23.swift').read_text()
source = host.read_text()
assert 'class TouchHLEMainRunLoopLaunch' not in source
anchor = '@MainActor\nprivate final class GameLibrary: ObservableObject {'
assert source.count(anchor) == 1
source = source.replace(anchor, snippet + '\n' + anchor, 1)

original = '''            ) { [weak self] in
                guard let self else { return }
                let result = EmulatorCore.withRunning(core) {
                    game.url.path.withCString { path in
                        touchhle_ios_launch_game(
                            core.runGame,
                            path,
                            Int32(scaleHack),
                            Int32(launchOrientation),
                            networkAccess ? 1 : 0,
                            analogTilt ? 1 : 0
                        )
                    }
                }

                TouchHLENativeHost.hideGameControls()
                TouchHLENativeHost.restoreHostWindow()
                self.isLaunching = false
                if result != 0 {
                    self.launchError = "\\(core.kind.displayName) could not start this game. The diagnostic log has been saved in Files."
                }
            }
'''
assert source.count(original) == 1, 'Exact V22 native launch block required'
lines = original.splitlines(keepends=True)
# Leave the preparation callback lightweight on every completion path. The
# actual emulator call is deferred once to the native timer on the main thread.
replacement = (lines[0] + '                TouchHLEMainRunLoopLaunch.schedule { [weak self] in\n'
               + ''.join('    ' + line if line.strip() else line for line in lines[1:-1])
               + '                }\n' + lines[-1])
source = source.replace(original, replacement, 1)
# The existing library refresh guard prevents newly-serviceable scene-phase
# callbacks from re-entering metadata parsing while the game is active.
assert 'func reload() {\n        guard !isLaunching, !isImporting else { return }' in source
host.write_text(source)
print('V23: native timer launch installed; main thread, existing reload guard, background GL pause, V22 core and saves retained.')
