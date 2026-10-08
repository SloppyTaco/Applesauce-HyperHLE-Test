# Applesauce HLE Rendering Test

Experimental, unsigned iPhone build for investigating Order Up!! rendering.
The test installs as **Applesauce HLE Test**, with bundle ID
`io.github.sloppytaco.applesaucehyperhletest`.

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
**Applesauce-HLE-Rendering-Test**. Failed builds upload diagnostic logs.

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
