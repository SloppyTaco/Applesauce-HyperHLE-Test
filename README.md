# V23: native interruption/input recovery

V22 is confirmed working by the user, including the private Farmers Market and assistant content. The remaining report is lost touch input after dismissing iOS system UI while rendering/audio continue. The attached log records successful foreground resumes at about 30 FPS; the original guest pause alone is not the failure.

This version changes only the native launch entry: preparation returns to the main dispatch queue, then the core starts from a native main-run-loop timer. SDL can then service queued UIKit restoration/completion work while emulation remains on the main thread. The existing library refresh guard, background GL pause, V21 application loop, V22 direct alerts, content checks, bundle identity and game saves are retained. New native checks compare blocked dispatch with the production timer and exercise actual landscape Home/return and Control Center/dismiss taps. CI and physical iPhone verification must confirm the change; source preparation alone is not a finished IPA.

Private content is copied byte-for-byte from the user's verified V22 IPA locally. No private game bytes are included in this repository or public CI artifacts.

# Order Up!! V22: native buttons and private 1.41 DLC

The user confirmed V21 fully loads 1.41. Their next phone log continues
rendering while a native Download prompt disappears without a selected-button
record or guest callback. The previous native state fixture called the recording
helper directly and did not cover the real UIKit action/dismissal path while
the emulator occupies a main GCD block.

V22 uses ordinary public UIButton target/action in a dedicated non-animated
card. It retains copied ownership, token isolation, queuing, exactly-once guest
polling and cleanup, without synthetic selection. New public XCUI fixtures
exercise Download/Cancel taps and game-input restoration with the exact SDL
default/tracking run-loop turns, alongside the four original state cases.
The workflow gates release on their results, not just on successful compilation.

A separate PRIVATE 689-asset pack contains Marketplace.wad, eleven missing
assistant WADs and their audio from the user's supplied 1.62 archive. Their v4
container format and 1.41 resource identifiers match; this is a cross-version
data port and those checks do not prove actual map/assistant gameplay.
No copyrighted game bytes or guest executable are published here.

The installer requires the exact supplied 1.41 executable and exact pack. It
checks every payload, stages changes, backs up replaced cache content, rolls
back publication failures and only then writes the game's genuine completion
indicators. Base Chef/Common WADs, built-in Fry Guy, saves/profile, purchases,
hiring rules and currency are untouched. Only verified local package checks
may bypass obsolete server metadata; missing/damaged packs do not claim success.
The V18 1.0 pack/guards and phone-confirmed V21 startup fix remain unchanged.
Same host bundle ID: install over the current app, do not uninstall it.

## Retained V21 application-loop lifetime correction

The user's V20 phone log shows the startup promotion popup returns, the guest
timer finishes, and the app exits with status `806421216` (`0x301102e0`), the
same pointer as that timer. JIT and both graphics contexts initialized normally.
The game's private startup routine preserves UIApplicationMain's return value
and passes it to exit. UIKit's UIApplicationMain must never return, but the
emulator previously called `-[NSRunLoop run]` only once. CFRunLoopStop could
therefore end the entire application instead of only that loop activation.

An original ARMv7 UIApplicationMain/NSTimer/popup fixture reproduces the early
return on the exact V20 executable. V21 restarts stopped application-loop
activations without changing ordinary CFRunLoopRun/Stop behavior. Separate
fixtures check direct stop returns, nested activation returns and later timers
continue, and genuine guest exit still terminates with its requested status.
Nonzero guest exits now include a caller stack to distinguish remaining errors.

All previous patches, native button event delivery, programmatic dismissal,
buttonless loading, original 1.0 executable guards and offline-pack checks stay
unchanged. No save, coin, purchase, first-run flag or private game byte is edited
by this correction. Version 21.0.0 (21) keeps the same existing test-app identity.
Both V21 builds and the new regression verification passed. This is not a claim
of full 1.41 startup/gameplay compatibility or a phone-tested fix.

## Verified V21 build and private package

The iPhone [run 38152812767](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38152812767)
and regression [run 38152812772](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38152812772)
both passed from source `02894ccad42fb7d0edbb1f3b9eeae59dec6e2fcb`.
The exact downloaded V20 baseline reproduced UIApplicationMain's early return.
The corrected source-built CLI passed four lifecycle cases: continued dispatch
after a stopped main activation, normal direct CFRunLoopStop return, nested
activation return and continued dispatch, and genuine exit with status 73.

Four native UIKit simulator state/event-boundary checks, six async ARMv7 alert
cases, four graphical and four headless loading cases, four old alert-callback
cases, four content-safety unit tests, four profile-preservation unit tests and
16 formatter cases passed. The broad Rust suite retains exactly the two known
duplicate-export failures for `_CATransform3DMakeScale` and
`NSProcessInfo.operatingSystemVersionString`, with 74 passes and no new failures.
The downloaded Linux CLI rechecked all four lifecycle cases locally and
validated all 1,992 private offline assets without filesystem or save changes.

The private final `Applesauce-OrderUp-v21.ipa` is 97,462,648 bytes with SHA256
`ff3e9c1999a7a6586bf56e8d71cfabe2285e424bfdd390a9b839bf3913ceab8c`.
All 19 patch-input digests, same host identity/version, compiled V21 core and
retained V20 shared-SDL bridge markers were checked. The original offline pack
remains byte-for-byte unchanged and its compiled ARM64 digest guard is present.
The pack still targets the user's working original 1.0; no private game binary,
Chef.wad or save is bundled. Install over the same existing app, retain the
independent 1.0 backup and enable JIT. Actual 1.41 phone startup, native button
taps and full gameplay remain pending the user's test.

## V20 build and phone regression

The iPhone [run 38149645335](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38149645335)
and Linux [run 38149645355](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38149645355)
passed from `b7860b3be2decb4b48fedc3f620eaa0b67f26ef9`. Four native UIKit
state/event-boundary tests and six original ARMv7 async-alert cases passed.
Those fixtures did not exercise UIApplicationMain's lifetime; the user's
subsequent actual game launch exited early as described above. The new V21
fixture closes that test gap. Hardware tap/full game behavior is still unverified.

## Previous V19 work

# Order Up!! V19: first-loading alert fix for 1.41

The user's V18 phone log confirms that Order Up!! 1.41 launches with JIT and
extracts its main package, then stops while presenting the buttonless
"Loading for the first time. Please wait..." alert. The guest's progress
alert has no user action; its original completion selector dismisses it.
The emulator previously invented an OK button and blocked the guest scheduler
inside SDL's native dialog, preventing loading from completing normally.

V19 lets a nonempty alert with zero buttons return immediately. The logical
alert remains visible and retained until the original game dismisses it.
Repeated show is ignored, and guarded programmatic dismissal releases that
presentation ownership after delegate callbacks. The existing empty-placeholder
behavior and V18 native button/click/dismissal path are retained. Buttonless
alerts do not display a native modal or custom progress bar in this targeted
fix; this is not a full asynchronous implementation of button-bearing alerts.

An independent ARMv7 fixture checks genuine NSTimer completion, nested
programmatic dismissal, repeated presentation, caller release during loading,
and message-only loading alerts. The graphical V18 baseline and V19 tests run
under a virtual display, separately from the existing V18 callback, private
content, save-preservation and formatter regressions.

This is the first 1.41 startup fix, not a claim that the full newer game works.
The previous 1.0-specific executable guards and recovery stay unchanged.
No original game executable, save or private asset is published in this repo.
The private final IPA retains the existing V18 content pack for returning to
the user's working 1.0 game. It keeps bundle ID
`io.github.sloppytaco.applesaucehyperhletest` and uses version 19.0.0 (19),
so it installs over the same test app with the same signing account.

The user confirmed V18's download fix and subsequent 1.0 gameplay work on
their phone. Keep their independent 1.0 backup untouched while testing 1.41.
## Verified V19 build and private package

The [iPhone build 38142173228](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38142173228)
passed for source commit `d1b1c099f6136ccb77fc7bb248478f015da547f8`.
The ARM64 host and core, app identity, version 19.0.0 (19), all 16 patch
digests and compiled V15–V19 markers were checked in the downloaded IPA.

The [regression run 38142887341](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38142887341)
passed with the same emulator patch chain. Its later commit
`1010886d845554d30ccc7a0700d13683ecd38d89` changes only the fixture and
verification workflow. The baseline reuses the byte-verified V18 Linux
artifact from run 38085250794. On the Linux virtual display, SDL returned
without opening a dialog, reproducing V18's incorrect synthetic click and
premature dismissal. The fixture also recognizes the blocking path observed
on the phone. V19 bypasses that native path for buttonless loading alerts.

- Four real ARMv7 loading cases passed with a graphical window and again
  headlessly, including real timer completion and caller-release lifetime.
- Four existing alert callback cases, four offline content checks, four
  profile/save-preservation checks and 16 formatter guest cases passed.
- The broad Rust suite has 74 passing tests and the same two existing
  duplicate-export failures for `_CATransform3DMakeScale` and
  `NSProcessInfo.operatingSystemVersionString`; no new failures were accepted.

The private final `Applesauce-OrderUp-v19.ipa` is 97,450,427 bytes with SHA256
`f648c64e9cdcf6f8c9846dcf4c9b58b1e251b39e9d0a7ec5bb7c965a19016851`.
The unchanged V18 offline pack contains 1,992 verified assets and has SHA256
`c8a5c51ecc17200272897b9104b05f7a48f95e712617c9bc212dbe0ee6596a41`.
The new source-built Linux CLI validated it without changing files or saves.
The packaged ARM64 core retains the exact compiled pack-digest comparison.
Those resources still target the original 1.0 game; no 1.41 content port or
game executable is included in this first loading fix.

The first-loading behavior is verified with independent guest programs.
Full Order Up!! 1.41 startup and gameplay remain pending the user's phone
test. Install over the existing app using the same AltStore account, enable
JIT, and launch the already imported 1.41 game. Keep the separate 1.0 backup.

## Previous V18 work

# Order Up!! V18: alert dismissal and private offline Gravy Chug content

The user confirmed that V17 purchases Gravy Chug correctly. Entering it opens
an alert asking to download the free restaurant content and then freezes.
The original ChefDownloadManager guest callback at `0x1b567c` explicitly calls
`dismissWithClickedButtonIndex:animated:`. The base emulator incorrectly sends
`clickedButtonAtIndex:` from programmatic dismissal, re-entering that same
callback. An independent ARMv7 guest reproduced this exact recursion on V17.

V18 separates user-click delivery from programmatic dismissal, makes dismissal
idempotent before delegate calls, and retains alert/delegate lifetime across
callbacks. SDL also uses a bounded native run-loop turn after button selection
and no longer resets a selection after presentation. The native dialog is still
modal; this is a targeted callback fix, not a claim of full asynchronous UIKit.

The user's 1.0 package contains Chef.wad but no Diner.wad. Their supplied 1.62
archive contains the Diner and shared v4 WADs. A PRIVATE offline pack keeps the
Diner payload intact and combines the disjoint Common_v1/Common_v2 resource
indices into the original engine's Common.wad name. It includes their stream
assets. No copyrighted game bytes are committed to or uploaded through GitHub.
The final user-specific IPA gets the private resource locally after the emulator
build. This is a cross-version data port; actual 1.0 restaurant gameplay still
requires iPhone testing, and container/hash checks do not establish full game
compatibility.

The executable-guarded installer verifies the exact pack, every payload digest,
safe path, entry count and bounded sizes before changing cached content. It
stages and checks files, preserves original-version stream assets, backs up any
other replaced cached content, rolls back failed publication, and creates only
the original diner/common completion indicators after successful installation.
It never replaces Chef.wad, edits the profile, changes purchase/unlock bits,
changes currency, or resets progress. Only verified local diner/common package
checks bypass the obsolete remote download dictionary; other downloads stay
unchanged. Without the pack, the emulator never reports a completed download.

The same V18 binary can also read the exact pack from the guest's Documents
folder; content does not require another emulator build. A read-only CLI check
is available as `--check-order-up-offline-pack=PATH` for private validation.

V18 retains the complete V17 patch chain and the same test-app bundle ID:
`io.github.sloppytaco.applesaucehyperhletest`. Install over the existing app,
not as a fresh app, to retain imports and saves. The host version is 18.0.0 (18).

## Verified V18 build and private package

The [iPhone build 38085250715](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38085250715)
and [regression run 38085250794](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38085250794)
both passed using source commit `e7d2d0f5891abd89be3aa875363244f0ae403973`.
V17 reproduced recursive clicked-button delivery; V18 passed all four independent
ARMv7 alert cases, four private-content safety tests, four existing profile
preservation tests, and all 16 formatter guest cases. Broad Rust checks recorded
74 passes and only the same two pre-existing duplicate-export failures noted
below; there were no new failures.

The compiled Linux V18 decoder locally validated all 1,992 private assets.
The original 1.0 guest also exercised the real installer in a fresh isolated
sandbox: the first launch published the missing/replacement assets, retained
all 76 original streams and original Chef.wad, preserved a Documents save-data
sentinel, and backed up both previous test WADs. The second launch published
zero files and retained all 1,992 installed assets. These launches deliberately
used headless mode and stopped when the game requested a window; they establish
installation/preservation, NOT restaurant gameplay or iPhone compatibility.

The user-specific final file is `Applesauce-OrderUp-v18.ipa`, 97,450,380 bytes,
SHA-256 `8988a927d80911cf556f3825304092d9ffdf76ecdf3f0b193e4053b84ef707b4`.
Its archive integrity, all 15 patch hashes, exact bundled offline resource,
unchanged ARM64 host/core, V15-V18 markers, optimized native pack-digest
comparison, and same bundle identity/version were verified after packaging.
It includes the offline pack; the public GitHub emulator artifact intentionally
does not. AltStore must re-sign the private IPA. Install OVER V17, keep the
existing imported 1.0 game and saves, and enable JIT as before. The newer-asset
port still needs a real iPhone Gravy Chug test.

## Previous V17 validation

# Order Up!! V17 profile identity recovery

V16's phone log confirms the full Gravy Chug name now formats correctly, but all
eight loaded restaurant profile entries have zero IDs at purchase. The original game's
purchase routine searches those IDs before setting the purchased bit. It still
shows its success message when no matching row exists.

V17 records the IDs and exact save-row locations produced by the game's original
restaurant initializer. Before an ownership query, purchase, or level load, it
can restore those ID words only if all 24 current ID slots are zero, the profile
pointer is unchanged, and the original restaurant definitions still match. The
recovery does not set purchased/unlocked bits, reset the profile, modify currency,
or alter chef/day/restaurant progress. The original game performs the purchase.
It skips recovery if native identity capture or any validation fails.

The V17 iPhone build, packaging checks, and validation workflow completed
successfully. All four profile identity tests passed, including byte-for-byte
preservation outside the recovered ID words, repeated calls, existing/partial
profiles, ambiguous mappings, and wrong profile lengths. All 16 independent
ARMv7 guest formatter cases also passed through the real emulator ABI.
The broad Rust checks recorded 70 passes and the same two previously confirmed
duplicate-export failures (`_CATransform3DMakeScale` and
`NSProcessInfo.operatingSystemVersionString`); no new failures appeared.
The user subsequently confirmed purchasing on their iPhone works. Logs report native capture,
recovery, and original before/after purchase state.

Verified V17 iPhone build: [run 38079511023](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38079511023).
[Profile/formatter validation run 38079511051](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38079511051)
uses source commit `263f9a36c2d6691d457b73d00b1df982490ce113`.
The IPA is 42,358,051 bytes, SHA-256
`9e0d476af0d7976c2fe4f58da2fa30cb09a4399fc506fc4ac00103dd806ba497`.
After download, the artifact digest, IPA checksum/integrity, all 14 patch hashes,
ARM64 host/core, compiled V17 recovery markers, existing test-app bundle identity,
and exclusion of private game assets were checked. The saved download is named
`Applesauce-OrderUp-v17.ipa`; the GitHub artifact is
`Applesauce-HLE-Rendering-Test-v17`.

Install over the existing Applesauce HLE Test app to retain its imported game and
save data, enable JIT as before, and try the purchase once. The package contains
only the emulator; it does not contain Order Up game files.

## Previous V16 validation and build

# Applesauce HLE Rendering Test

Experimental, unsigned iPhone build for investigating Order Up!! rendering.
The test installs as **Applesauce HLE Test**, with bundle ID
`io.github.sloppytaco.applesaucehyperhletest`.

## Current test: v16 candidate

The V15 phone test completed the Burger Face tutorial. Its fresh log verifies
that Chef.wad already matched the original digest; no cache repair ran on that
launch. All eight restaurant definitions loaded. After day one, Gravy Chug
shows missing description text and a purchase message containing only "G",
but it stays unpurchased.

V16 fixes a confirmed emulator formatter bug: `%ls` was reading a 32-bit
`wchar_t` string as bytes and stopping at the zero byte after its first letter.
The original purchase message uses `%ls`. Wide output now writes Unicode
scalars and counts capacity in wide characters; narrow output converts the
wide argument to UTF-8 without splitting a character at the precision limit.
Existing plain `%s` behavior is retained.

The purchase/ownership failure is still under investigation. The V15 log
shows the purchase achievement callback, but the native game can reach that
callback even when no matching ownership row was found. V16 records bounded
before/after snapshots of the original purchase state and formatted strings,
only for the previously verified Order Up!! v1.0 executable. Definition
indices and profile rows are logged separately because the guest matches
ownership by ID. These diagnostics do not set ownership, spend money, unlock
restaurants or replace saves.

The V16 iPhone build and package verification passed. The independent ARMv7
guest regression fails the purchase-name case on V15, then passes all 16
cases on V16. It exercises the real emulator ABI and formatter entry points,
including argument order, precision, padding, Unicode counts, output capacity
and plain narrow strings. The test contains no original game executable or
assets. The required broad Rust run completed with 66 passes and the same two
existing failures: duplicate `_CATransform3DMakeScale` and duplicate
`NSProcessInfo.operatingSystemVersionString`. V16 changes neither export.
The original regression job is marked failed because its shell exited at the
known failing broad tests before the reporting step could classify them;
all 16 formatter cases passed. The reporting step now captures that exit
status before checking the exact known failures for future runs.

On-device restaurant purchasing remains unverified, so this remains a
purchase-diagnostic candidate. The successful checks verify the formatter fix
and package, rather than an end-to-end Gravy Chug purchase.
Install V16 over the existing HLE Test app with the same signing account and
preserve the game data. After trying Gravy Chug once, export the fresh host
log containing `[ORDER UP FORMAT v16]`, `[ORDER UP PURCHASE v16]`,
`[ORDER UP OWNERSHIP v16]` and `[ORDER UP DEFINITION v16]`.

Verified V16 build: [run 38036059501](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38036059501),
source commit `9a2620ac4c8b4ea0d23fc97ab4e944637972ad76`.
[Formatter regression run 38036333684](https://github.com/SloppyTaco/Applesauce-HyperHLE-Test/actions/runs/38036333684)
uses the same V16 source patch, SHA-256
`9f188f80f356ea452d98c1be5ae9aa12dce0aab6f2dc1a3c470a357295ba2a03`.
The IPA is 42,354,812 bytes, SHA-256
`2013011bbaba54cccc7390052a490281690b92272402da1d6cb42169b95ddd5c`.
The downloaded archive, IPA integrity/checksum, all 13 patch hashes, ARM64
host/core, V16 compiled markers and exclusion of private game assets were
also checked after download.

The build starts from working Applesauce iOS source at
`c75278bda86c80cbcec2d8d1493b5be9d5a9e0d1` and applies the small patch in
`patches/ios-rendering-backport.patch`. It retains Applesauce's existing
HyperHLE core and iOS integration. **This is not a complete update to HyperHLE
trunk. The first phone test still showed a black screen.**

## Graphics changes

- Skip fixed-function fog queries on native GLES2/3, preventing emulator
  GL_FOG queries from raising GL_INVALID_ENUM before each guest draw.
- Recover an unregistered current renderbuffer when exactly one drawable
  exists, and pass that drawable's renderbuffer through readback and display.
- Query dimensions from the selected renderbuffer and restore the guest binding.
- Disable guest scissor clipping during the ES2 presentation copy and restore it.
- Keep shader, texture and framebuffer caches specific to each EAGL context
  lifetime, including a new game launch. Reuse objects when switching live contexts.
- Log source-frame dimensions, framebuffer completeness and maximum RGB value
  at frames 1, 60 and 300 for diagnosing a remaining black screen.

Adapted to the iOS host API from HyperHLE rendering work, including
[renderbuffer propagation](https://github.com/KlugKlugTG/HyperHLE-Fork/commit/98b7269212d7206df3117bd1a0d8646c5bddb402),
[drawable mismatch recovery](https://github.com/KlugKlugTG/HyperHLE-Fork/commit/6190b7dba937e097409d2eb1d96e03735c1ec812)
and fog, scissor and context-cache fixes in that fork. The fog change avoids
the unsupported query instead of consuming existing guest GL errors.

## Build and install

The Actions workflow compiles the iPhone app on macOS, packages an unsigned
IPA, validates its contents, and uploads the IPA and SHA-256 checksum as
**Applesauce-HLE-Rendering-Test-v16**. Failed builds upload diagnostic logs.

Download the artifact after a successful run and extract
`Applesauce-HLE-Rendering-Test.ipa`. Install it through AltStore Classic
**My Apps → +**, enable JIT for **Applesauce HLE Test**, and import the game.
The test app has a separate container. Start with the same options used for
the previous comparison.

Full credit for emulation belongs to [touchHLE](https://github.com/touchHLE/touchHLE)
and [HyperHLE](https://github.com/KlugKlugTG/HyperHLE-Fork), and for the iPhone
host to [Applesauce](https://github.com/johnny901901901/Applesauce).

## Startup trace v2

The first rendering test (run 6) launched with JIT and extracted Chef.wad,
but the supplied phone log contained no first presentation message. Manual
exit returned normally. This does not establish the startup blocker.

The next diagnostic patch logs display-link creation, registration, pausing,
and early callback entry/return; timer callback entry/return and autorelease
pool completion; deferred Game Center authentication; and first nonempty
GLES draws. Timer milestones are limited to fires 1, 2, 3, 60, 300 and 1800.
The added tracing does not fix the dictionary subclass or missing-selector
warnings. Those remain leads, not proven causes.

Install the new IPA over Applesauce HLE Test using the same signing account.
Fully close and reopen the host so process-wide first-call markers reset,
enable JIT, launch Order Up!! once, leave it running for approximately
60 seconds, then exit manually and export the complete log. Preserve the
existing game data and settings. Look for `[STARTUP TRACE v2]` markers.

## Callback and lifecycle fix v3

Run 7's phone trace reached display-link callbacks 60 and 300, with callbacks
returning and timer pools draining. Game Center's deferred delivery entered,
but never reached its invocation marker. The implementation copied the guest
block using an Objective-C `copy` message even though the block isa symbols
are placeholders, then silently skipped delivery when the result was nil.

This patch uses the C Blocks runtime directly for stored Game Center handlers.
Stack blocks are copied using their descriptor size, compiler copy/dispose
helpers run, heap ownership is counted, and captured blocks/byref storage
are managed. Handler replacement and destruction release the owned block;
the persistent authenticate handler also holds a temporary reference during
reentrant callbacks. This does not add general Objective-C block classes.
The new `[CALLBACK FIX v3]` marker records the original and copied addresses.

On iOS, the scheduler pauses guest execution after the background event while
continuing event polling and checking the exit request. Foreground activation
resumes execution. The exit overlay is raised above normal game windows, and
both its button and the Rust exit entry point log requests. These changes
address background GPU submissions and make exit failures distinguishable;
on-device close/resume behavior still needs validation.

The black-screen cause is not yet confirmed. Test this build in place over
the existing test app, preserving data and settings. The key evidence is
whether Game Center now logs `invoking completion` and `completion returned`,
whether nonempty draws/presentation start, and whether the close request
reaches `Returning to the iOS host library`. Do not infer successful rendering
from a successful build alone.

## V20: asynchronous iPhone button prompts

V19 was confirmed on the user's iPhone to finish extracting Order Up!! 1.41 and dismiss its first-run loading alert. The next log ends in the Facebook/Twitter promotion popup before any native OK-button callback; the user reports that the popup freezes and requires force-close.

V20 replaces the iOS guest button-alert blocking SDL wait with copied, asynchronous UIKit state and a non-animated scene-aware alert window above the game controls. A guest main-run-loop timer consumes a real button selection once and dispatches the unchanged V18 callback path. No automatic OK click, currency change, first-run/save-flag edit, guest executable patch, or broader 1.41 asset assumption is introduced.

The full V18/V19 patch chain, same host bundle identity and byte-identical private offline pack for the working original 1.0 fallback are retained. Public Actions artifacts contain emulator/test code only; private assets are added locally after verification.

Validation for this revision includes four native UIKit simulator state/event-boundary checks and six original ARMv7 guest timer/ownership/callback cases, plus the preserved V18/V19 loading, callback, formatter, content and profile tests. Simulator event injection is not a hardware-touch test. iPhone OK-button behavior and full 1.41 gameplay remain unverified until the user tests the new build. Build/test results will be recorded after completion.
