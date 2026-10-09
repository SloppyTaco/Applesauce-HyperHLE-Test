from pathlib import Path


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise SystemExit(f"V10 patch failed: expected one {label} anchor")
    return text.replace(old, new, 1)


guest_path = Path("applesauce/src/frameworks/opengles/gles_guest.rs")
guest = guest_path.read_text()
anchor = "// Bound the logging and readbacks to startup and a few later milestones."
helper = '''// V9 confirmed that this title enables scissoring without ever setting its
// initial box: every clear/draw was clipped to [0, 0, 0, 0]. Seed only that
// uninitialized native ES2 state from the already corrected host viewport.
unsafe fn repair_order_up_empty_scissor(gles: &mut dyn GLES) {
    use crate::gles::gles2_raw as gl;
    if !gles.is_es2() || gles.IsEnabled(gl::SCISSOR_TEST) == 0 {
        return;
    }
    let mut scissor = [0i32; 4];
    gles.GetIntegerv(gl::SCISSOR_BOX, scissor.as_mut_ptr());
    if scissor != [0, 0, 0, 0] {
        return;
    }
    let mut viewport = [0i32; 4];
    gles.GetIntegerv(gl::VIEWPORT, viewport.as_mut_ptr());
    if viewport[2] <= 0 || viewport[3] <= 0 {
        return;
    }
    gles.Scissor(viewport[0], viewport[1], viewport[2], viewport[3]);
    log_once!(
        "[ORDER UP FIX v10] Repaired enabled empty scissor box using host viewport {:?}.",
        viewport
    );
}

'''
guest = replace_once(guest, anchor, helper + anchor, "draw helper")
for call in ("gles.DrawArrays(mode, first, count);", "gles.DrawElements(mode, count, type_, indices);"):
    guest = replace_once(
        guest, call,
        '''if order_up && count > 0 {
            repair_order_up_empty_scissor(gles);
        }
        ''' + call,
        call,
    )
guest = replace_once(
    guest, "        gles.Clear(mask);",
    '''        if order_up {
            repair_order_up_empty_scissor(gles);
        }
        gles.Clear(mask);''',
    "guest clear",
)

state_path = Path("applesauce/src/frameworks/opengles.rs")
state = replace_once(
    state_path.read_text(),
    "pub struct State {\n    /// Current EAGLContext for each thread",
    '''pub struct State {
    /// Order Up's direct presenter owns the display after its first frame.
    /// Reset with the environment or when the owning context is deallocated.
    pub(crate) order_up_direct_context: Option<crate::objc::id>,
    /// Current EAGLContext for each thread''',
    "OpenGLES state",
)

eagl_path = Path("applesauce/src/frameworks/opengles/eagl.rs")
eagl = eagl_path.read_text()
eagl = replace_once(
    eagl, "- (())dealloc {\n    let host_obj = env.objc.borrow_mut::<EAGLContextHostObject>(this);",
    '''- (())dealloc {
    if env.framework_state.opengles.order_up_direct_context == Some(this) {
        env.framework_state.opengles.order_up_direct_context = None;
    }
    let host_obj = env.objc.borrow_mut::<EAGLContextHostObject>(this);''',
    "EAGL context teardown",
)
eagl = replace_once(
    eagl,
    '''    let use_ios_es2_direct_path = cfg!(target_os = "ios")
        && env.options.ios_es2_direct_present
        && fullscreen_layer == nil''',
    '''    // V9 wrote and read a green source pixel successfully, but the layer
    // compositor never displayed it. Use the existing ES2 presenter for this
    // title and keep later compositor ticks from overwriting its frame.
    let order_up_direct_path = cfg!(target_os = "ios")
        && env.bundle.bundle_identifier() == "com.chillingo.orderup"
        && !env.options.force_composition
        && fullscreen_layer == nil
        && env.objc.borrow::<EAGLContextHostObject>(this).api
            == kEAGLRenderingAPIOpenGLES2;
    if order_up_direct_path {
        if env.framework_state.opengles.order_up_direct_context != Some(this) {
            log!(
                "[ORDER UP FIX v10] Direct ES2 presentation active: context={:?} source_rb={} drawable={:?}.",
                this, renderbuffer, drawable
            );
        }
        env.framework_state.opengles.order_up_direct_context = Some(this);
    } else if env.framework_state.opengles.order_up_direct_context == Some(this) {
        env.framework_state.opengles.order_up_direct_context = None;
    }

    let use_ios_es2_direct_path = cfg!(target_os = "ios")
        && (env.options.ios_es2_direct_present || order_up_direct_path)
        && fullscreen_layer == nil''',
    "direct presentation selection",
)
eagl = replace_once(
    eagl,
    '''    let trace_gl_errors = env.options.trace_gl_errors;
    // Save these for when we need to draw the frame''',
    '''    let trace_gl_errors = env.options.trace_gl_errors;
    let probe_order_up = cfg!(target_os = "ios")
        && env.bundle.bundle_identifier() == "com.chillingo.orderup";
    // Save these for when we need to draw the frame''',
    "present title capture",
)
eagl = replace_once(
    eagl,
    '''    let is_ios_es2_override_path = cfg!(target_os = "ios")
        && env.options.ios_es2_direct_present''',
    '''    let is_ios_es2_override_path = cfg!(target_os = "ios")
        && (env.options.ios_es2_direct_present
            || env.framework_state.opengles.order_up_direct_context == Some(context))''',
    "direct presentation rotation",
)
signature = '''    virtual_cursor_visible_at: Option<(f32, f32, bool)>,
) {
    use crate::gles::gles2_raw as gles2;'''
eagl = replace_once(
    eagl, signature,
    '''    virtual_cursor_visible_at: Option<(f32, f32, bool)>,
    probe_order_up: bool,
) {
    use crate::gles::gles2_raw as gles2;''',
    "ES2 presenter signature",
)
eagl = replace_once(
    eagl,
    '''            rotation_matrix,
            virtual_cursor_visible_at,
        );
        std::mem::drop(gles_boxed);''',
    '''            rotation_matrix,
            virtual_cursor_visible_at,
            probe_order_up,
        );
        std::mem::drop(gles_boxed);''',
    "ES2 presenter call",
)
display_probe = '''
    // Sample the actual display framebuffer after the present shader, so a
    // future black-screen report distinguishes source rendering from output.
    let frame = PRESENT_DIAGNOSTIC_FRAME.with(|counter| counter.get());
    if probe_order_up && matches!(frame, 1 | 60 | 300) {
        let status = gles.CheckFramebufferStatus(gles2::FRAMEBUFFER);
        let setup_error = gles.GetError();
        if status == gles2::FRAMEBUFFER_COMPLETE && setup_error == gles2::NO_ERROR {
            let mut pixels = vec![0xCDu8; (viewport.2 as usize) * (viewport.3 as usize) * 4];
            gles.ReadPixels(
                viewport.0 as GLint, viewport.1 as GLint,
                viewport.2 as GLsizei, viewport.3 as GLsizei,
                gles2::RGBA, gles2::UNSIGNED_BYTE, pixels.as_mut_ptr().cast(),
            );
            let read_error = gles.GetError();
            if read_error == gles2::NO_ERROR {
                let rgb_max = pixels.chunks_exact(4)
                    .flat_map(|pixel| pixel[..3].iter()).copied().max().unwrap_or(0);
                let nonblack = pixels.chunks_exact(4)
                    .filter(|pixel| pixel[..3].iter().any(|&v| v != 0)).count();
                let untouched = pixels.iter().all(|&v| v == 0xCD);
                log!(
                    "[ORDER UP DISPLAY v10] frame={} display_fb={} viewport={:?} status=0x{:x} read_error=0x{:x} sentinel_untouched={} rgb_max={} nonblack_pixels={}",
                    frame, drawable_framebuffer, viewport, status, read_error,
                    untouched, rgb_max, nonblack,
                );
            } else {
                log!("[ORDER UP DISPLAY v10] frame={} read failed error=0x{:x}", frame, read_error);
            }
        } else {
            log!(
                "[ORDER UP DISPLAY v10] frame={} display_fb={} setup failed status=0x{:x} error=0x{:x}",
                frame, drawable_framebuffer, status, setup_error,
            );
        }
    }
'''
eagl = replace_once(
    eagl,
    "    gles.DrawArrays(gles2::TRIANGLES, 0, 6);\n\n    // Optional: virtual cursor.",
    "    gles.DrawArrays(gles2::TRIANGLES, 0, 6);\n" + display_probe + "\n    // Optional: virtual cursor.",
    "display readback",
)

composition_path = Path("applesauce/src/frameworks/core_animation/composition.rs")
composition = replace_once(
    composition_path.read_text(),
    '''    if env.window.is_none() {
        return None;
    }

    let mut animation_state = animation::State::default();''',
    '''    if env.window.is_none() {
        return None;
    }

    // Once Order Up starts direct ES2 presentation, the independent ES1 UI
    // compositor must not clear/swap over those frames on later run-loop ticks.
    if cfg!(target_os = "ios")
        && env.bundle.bundle_identifier() == "com.chillingo.orderup"
        && !env.options.force_composition
        && env.framework_state.opengles.order_up_direct_context.is_some()
    {
        return None;
    }

    let mut animation_state = animation::State::default();''',
    "compositor ownership",
)

for path, text in ((guest_path, guest), (state_path, state), (eagl_path, eagl), (composition_path, composition)):
    path.write_text(text)
print("Applied Order Up empty-scissor repair and direct ES2 presentation v10")
