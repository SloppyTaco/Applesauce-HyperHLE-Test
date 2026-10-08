from pathlib import Path

source = Path("applesauce/src/frameworks/opengles/gles_guest.rs")
text = source.read_text()

old_scissor = '''fn glScissor(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {
    {
        use std::sync::atomic::{AtomicBool, Ordering};
        static SEEN: AtomicBool = AtomicBool::new(false);
        if !SEEN.swap(true, Ordering::Relaxed) {
            log!(
                "First glScissor({}, {}, {}, {}) [this log will only be shown once]",
                x,
                y,
                width,
                height
            );
        }
    }
    let factor = env.options.scale_hack.get() as GLsizei;
'''

new_scissor = '''fn glScissor(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {
    {
        use std::sync::atomic::{AtomicBool, Ordering};
        static SEEN: AtomicBool = AtomicBool::new(false);
        if !SEEN.swap(true, Ordering::Relaxed) {
            log!(
                "First glScissor({}, {}, {}, {}) [this log will only be shown once]",
                x,
                y,
                width,
                height
            );
        }
    }

    // Order Up!! v1.0 reaches its render loop on iOS, but one failing run
    // reported an initial zero-sized viewport. Trace the companion scissor
    // state as well so we can tell whether clipping is also suppressing the
    // frame without changing scissor semantics yet.
    if env.bundle.bundle_identifier() == "com.chillingo.orderup" {
        use std::sync::atomic::{AtomicU32, Ordering};
        static ORDER_UP_SCISSOR_CALLS: AtomicU32 = AtomicU32::new(0);
        let call = ORDER_UP_SCISSOR_CALLS.fetch_add(1, Ordering::Relaxed) + 1;
        if call <= 120 {
            log!(
                "[ORDER UP TRACE v6] glScissor request #{}: ({}, {}, {}, {})",
                call,
                x,
                y,
                width,
                height
            );
        }
    }

    let factor = env.options.scale_hack.get() as GLsizei;
'''

if old_scissor not in text:
    raise SystemExit("V6 patch failed: expected glScissor block was not found")
text = text.replace(old_scissor, new_scissor, 1)

old_viewport = '''    // ULTRAHLE_MINIONJUMP_VIEWPORT_END
    let (mut x, mut y, mut width, mut height) = (x, y, width, height);

    if std::env::var_os("TOUCHHLE_FORCE_LANDSCAPE_VIEWPORT").is_some() {
'''

new_viewport = '''    // ULTRAHLE_MINIONJUMP_VIEWPORT_END
    let (mut x, mut y, mut width, mut height) = (x, y, width, height);

    // Order Up!! v1.0 normally renders a 480x320 landscape frame. On the
    // problematic iOS path it can issue glViewport(0, 0, 0, 0) even though
    // its EAGL drawable has already been created. A zero-sized viewport makes
    // every later draw legal but invisible. Correct only that broken state for
    // this exact title, then let the existing scale-hack logic enlarge the
    // logical 480x320 viewport to the actual drawable (for example 1440x960
    // with scale_hack=3).
    let order_up_viewport_call = if env.bundle.bundle_identifier() == "com.chillingo.orderup" {
        use std::sync::atomic::{AtomicU32, Ordering};
        static ORDER_UP_VIEWPORT_CALLS: AtomicU32 = AtomicU32::new(0);
        let call = ORDER_UP_VIEWPORT_CALLS.fetch_add(1, Ordering::Relaxed) + 1;
        if call <= 120 {
            log!(
                "[ORDER UP TRACE v6] glViewport request #{}: ({}, {}, {}, {})",
                call,
                x,
                y,
                width,
                height
            );
        }

        if width == 0 || height == 0 {
            log!(
                "[ORDER UP FIX v6] Correcting zero-sized glViewport({}, {}, {}, {}) -> glViewport(0, 0, 480, 320)",
                x,
                y,
                width,
                height
            );
            x = 0;
            y = 0;
            width = 480;
            height = 320;
        }
        Some(call)
    } else {
        None
    };

    if std::env::var_os("TOUCHHLE_FORCE_LANDSCAPE_VIEWPORT").is_some() {
'''

if old_viewport not in text:
    raise SystemExit("V6 patch failed: expected glViewport insertion point was not found")
text = text.replace(old_viewport, new_viewport, 1)

old_host_viewport = '''    let (x, y, width, height) = if apply_scale_hack {
        (x * factor, y * factor, width * factor, height * factor)
    } else {
        (x, y, width, height)
    };
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.Viewport(x, y, width, height)
    })
'''

new_host_viewport = '''    let (x, y, width, height) = if apply_scale_hack {
        (x * factor, y * factor, width * factor, height * factor)
    } else {
        (x, y, width, height)
    };
    if let Some(call) = order_up_viewport_call {
        if call <= 120 {
            log!(
                "[ORDER UP TRACE v6] glViewport host #{}: ({}, {}, {}, {}) scale_hack={} applies_to_target={}",
                call,
                x,
                y,
                width,
                height,
                factor,
                apply_scale_hack
            );
        }
    }
    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.Viewport(x, y, width, height)
    })
'''

if old_host_viewport not in text:
    raise SystemExit("V6 patch failed: expected host glViewport block was not found")
text = text.replace(old_host_viewport, new_host_viewport, 1)

source.write_text(text)
print("Applied Order Up viewport fix/trace v6")
