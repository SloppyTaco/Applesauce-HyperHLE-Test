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
Purchasing on the user's iPhone is not yet confirmed. Logs report native capture,
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
