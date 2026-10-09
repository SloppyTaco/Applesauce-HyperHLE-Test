from pathlib import Path


eagl_source = Path("applesauce/src/frameworks/opengles/eagl.rs")
eagl = eagl_source.read_text()
start_anchor = "    // Order Up!! v1.0 V7 diagnostic:"
end_anchor = '    let use_ios_es2_direct_path = cfg!(target_os = "ios")'
if eagl.count(start_anchor) != 1 or eagl.count(end_anchor) != 1:
    raise SystemExit("V9 patch failed: expected V7 presentation anchors not found")
start = eagl.index(start_anchor)
end = eagl.index(end_anchor, start)
eagl = eagl[:start] + '''    // Validate the source readback and inject a visible control square.
    if env.bundle.bundle_identifier() == "com.chillingo.orderup" {
        use std::sync::atomic::{AtomicU64, Ordering};
        static ORDER_UP_PROBE_FRAMES: AtomicU64 = AtomicU64::new(0);
        let frame = ORDER_UP_PROBE_FRAMES.fetch_add(1, Ordering::Relaxed) + 1;
        if let Some(mut gles) = super::sync_context(
            &mut env.framework_state.opengles,
            &mut env.objc,
            env.window.as_mut().unwrap(),
            env.current_thread,
        ) {
            unsafe { order_up_present_probe(gles.as_mut(), renderbuffer, frame); }
        }
    }

''' + eagl[end:]

helper_anchor = "/// Copies the pixels in a renderbuffer bound to `GL_RENDERBUFFER_BINDING_OES`\n/// (which should be provided by the app) to a provided [Vec]"
probe_helper = '''// Diagnostic only: a green control square bypasses the game's shaders while
// going through the same renderbuffer and presentation path as its image.
unsafe fn order_up_present_probe(gles: &mut dyn GLES, renderbuffer: GLuint, frame: u64) {
    use crate::gles::gles2_raw as gl;
    if !gles.is_es2() {
        return;
    }
    let sample = matches!(frame, 1 | 2 | 10 | 30 | 60 | 120 | 300);
    let pre_error = gles.GetError();
    let old_fb = get_int(gles, gl::FRAMEBUFFER_BINDING) as GLuint;
    let (width, height) = get_presented_renderbuffer_size(gles, renderbuffer);
    if width <= 0 || height <= 0 {
        if sample {
            log!("[ORDER UP TRACE v9] invalid source size={}x{} rb={}", width, height, renderbuffer);
        }
        return;
    }

    let mut draw_color_name: GLint = 0;
    let mut draw_color_type: GLint = 0;
    if sample && old_fb != 0 {
        gles.GetFramebufferAttachmentParameterivOES(
            gl::FRAMEBUFFER, gl::COLOR_ATTACHMENT0,
            gl::FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &mut draw_color_name,
        );
        gles.GetFramebufferAttachmentParameterivOES(
            gl::FRAMEBUFFER, gl::COLOR_ATTACHMENT0,
            gl::FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &mut draw_color_type,
        );
    }

    let mut probe_fb: GLuint = 0;
    gles.GenFramebuffersOES(1, &mut probe_fb);
    gles.BindFramebufferOES(gl::FRAMEBUFFER, probe_fb);
    gles.FramebufferRenderbufferOES(
        gl::FRAMEBUFFER, gl::COLOR_ATTACHMENT0, gl::RENDERBUFFER, renderbuffer,
    );
    let status = gles.CheckFramebufferStatusOES(gl::FRAMEBUFFER);
    let setup_error = gles.GetError();

    if sample && status == gl::FRAMEBUFFER_COMPLETE && setup_error == gl::NO_ERROR {
        let mut pixels = vec![0xCDu8; (width as usize) * (height as usize) * 4];
        gles.Finish();
        gles.ReadPixels(0, 0, width, height, gl::RGBA, gl::UNSIGNED_BYTE, pixels.as_mut_ptr().cast());
        let read_error = gles.GetError();
        if read_error == gl::NO_ERROR {
            let rgb_max = pixels.chunks_exact(4).flat_map(|p| p[..3].iter()).copied().max().unwrap_or(0);
            let nonblack = pixels.chunks_exact(4).filter(|p| p[..3].iter().any(|&v| v != 0)).count();
            let alpha_max = pixels.chunks_exact(4).map(|p| p[3]).max().unwrap_or(0);
            let untouched = pixels.iter().all(|&v| v == 0xCD);
            log!(
                "[ORDER UP TRACE v9] source frame={} rb={} draw_fb={} draw_color_type=0x{:x} draw_color_name={} size={}x{} status=0x{:x} pre_error=0x{:x} read_error=0x{:x} sentinel_untouched={} rgb_max={} nonblack_pixels={} alpha_max={}",
                frame, renderbuffer, old_fb, draw_color_type, draw_color_name, width, height,
                status, pre_error, read_error, untouched, rgb_max, nonblack, alpha_max,
            );
        } else {
            log!("[ORDER UP TRACE v9] source frame={} read failed error=0x{:x}; pixel counts are unavailable", frame, read_error);
        }
    } else if sample {
        log!("[ORDER UP TRACE v9] source frame={} setup failed status=0x{:x} error=0x{:x}; pixel counts are unavailable", frame, status, setup_error);
    }

    if frame >= 60 && status == gl::FRAMEBUFFER_COMPLETE && setup_error == gl::NO_ERROR {
        let old_scissor = get_ints::<4>(gles, gl::SCISSOR_BOX);
        let old_clear = get_floats::<4>(gles, gl::COLOR_CLEAR_VALUE);
        let mut old_mask = [0u8; 4];
        gles.GetBooleanv(gl::COLOR_WRITEMASK, old_mask.as_mut_ptr());
        let scissor_on = gles.IsEnabled(gl::SCISSOR_TEST) != 0;
        let edge = (width.min(height) / 6).min(160).max(1);
        let pad = edge / 2;
        gles.Enable(gl::SCISSOR_TEST);
        gles.Scissor(pad, pad, edge, edge);
        gles.ColorMask(gl::TRUE, gl::TRUE, gl::TRUE, gl::TRUE);
        gles.ClearColor(0.0, 1.0, 0.0, 1.0);
        gles.Clear(gl::COLOR_BUFFER_BIT);
        if sample {
            let mut pixel = [0xCDu8; 4];
            gles.ReadPixels(pad + edge / 2, pad + edge / 2, 1, 1, gl::RGBA, gl::UNSIGNED_BYTE, pixel.as_mut_ptr().cast());
            let error = gles.GetError();
            log!("[ORDER UP PROBE v9] frame={} rb={} green_square_rgba={:?} error=0x{:x} expected=[0, 255, 0, 255]", frame, renderbuffer, pixel, error);
        }
        gles.Scissor(old_scissor[0], old_scissor[1], old_scissor[2], old_scissor[3]);
        gles.ClearColor(old_clear[0], old_clear[1], old_clear[2], old_clear[3]);
        gles.ColorMask(old_mask[0], old_mask[1], old_mask[2], old_mask[3]);
        if !scissor_on {
            gles.Disable(gl::SCISSOR_TEST);
        }
    }
    gles.DeleteFramebuffersOES(1, &probe_fb);
    gles.BindFramebufferOES(gl::FRAMEBUFFER, old_fb);
}

'''
if eagl.count(helper_anchor) != 1:
    raise SystemExit("V9 patch failed: renderbuffer helper anchor not found")
eagl = eagl.replace(helper_anchor, probe_helper + helper_anchor, 1)

guest_source = Path("applesauce/src/frameworks/opengles/gles_guest.rs")
guest = guest_source.read_text()
trace_helper = '''// Bound the logging and readbacks to startup and a few later milestones.
unsafe fn trace_order_up_render_call(gles: &mut dyn GLES, kind: &str, mode: GLenum, count: GLsizei) {
    use crate::gles::gles2_raw as gl;
    use std::sync::atomic::{AtomicU64, Ordering};
    static DRAWS: AtomicU64 = AtomicU64::new(0);
    static CLEARS: AtomicU64 = AtomicU64::new(0);
    let counter = if kind == "Clear" { &CLEARS } else { &DRAWS };
    let n = counter.fetch_add(1, Ordering::Relaxed) + 1;
    if !gles.is_es2() || !matches!(n, 1..=8 | 60 | 300 | 1800) {
        return;
    }
    let pre_error = gles.GetError();
    let mut fb: GLint = 0;
    let mut program: GLint = 0;
    let mut array_buffer: GLint = 0;
    let mut texture: GLint = 0;
    let mut viewport = [0i32; 4];
    let mut scissor = [0i32; 4];
    let mut mask = [0u8; 4];
    let mut clear = [0.0f32; 4];
    gles.GetIntegerv(gl::FRAMEBUFFER_BINDING, &mut fb);
    gles.GetIntegerv(gl::CURRENT_PROGRAM, &mut program);
    gles.GetIntegerv(gl::ARRAY_BUFFER_BINDING, &mut array_buffer);
    gles.GetIntegerv(gl::TEXTURE_BINDING_2D, &mut texture);
    gles.GetIntegerv(gl::VIEWPORT, viewport.as_mut_ptr());
    gles.GetIntegerv(gl::SCISSOR_BOX, scissor.as_mut_ptr());
    gles.GetBooleanv(gl::COLOR_WRITEMASK, mask.as_mut_ptr());
    gles.GetFloatv(gl::COLOR_CLEAR_VALUE, clear.as_mut_ptr());
    let status = gles.CheckFramebufferStatusOES(gl::FRAMEBUFFER);
    let mut color_name: GLint = 0;
    let mut color_type: GLint = 0;
    if fb != 0 {
        gles.GetFramebufferAttachmentParameterivOES(gl::FRAMEBUFFER, gl::COLOR_ATTACHMENT0, gl::FRAMEBUFFER_ATTACHMENT_OBJECT_NAME, &mut color_name);
        gles.GetFramebufferAttachmentParameterivOES(gl::FRAMEBUFFER, gl::COLOR_ATTACHMENT0, gl::FRAMEBUFFER_ATTACHMENT_OBJECT_TYPE, &mut color_type);
    }
    let mut linked: GLint = 0;
    if program > 0 {
        gles.GetProgramiv(program as GLuint, gl::LINK_STATUS, &mut linked);
    }
    let scissor_on = gles.IsEnabled(gl::SCISSOR_TEST);
    let depth_on = gles.IsEnabled(gl::DEPTH_TEST);
    let cull_on = gles.IsEnabled(gl::CULL_FACE);
    let blend_on = gles.IsEnabled(gl::BLEND);
    let stencil_on = gles.IsEnabled(gl::STENCIL_TEST);
    let mut pixel = [0xCDu8; 4];
    let mut read_attempted = false;
    if status == gl::FRAMEBUFFER_COMPLETE && viewport[2] > 0 && viewport[3] > 0 {
        read_attempted = true;
        gles.ReadPixels(viewport[0] + viewport[2] / 2, viewport[1] + viewport[3] / 2, 1, 1, gl::RGBA, gl::UNSIGNED_BYTE, pixel.as_mut_ptr().cast());
    }
    let error = gles.GetError();
    log!(
        "[ORDER UP DRAW v9] {} #{} mode=0x{:x} count={} fb={} color_type=0x{:x} color_name={} status=0x{:x} program={} linked={} vbo={} texture={} viewport={:?} scissor={:?}/{} color_mask={:?} clear={:?} depth={} cull={} blend={} stencil={} pre_error=0x{:x} query_read_error=0x{:x} read_attempted={} center_rgba={:?}",
        kind, n, mode, count, fb, color_type, color_name, status, program, linked, array_buffer,
        texture, viewport, scissor, scissor_on, mask, clear, depth_on, cull_on, blend_on,
        stencil_on, pre_error, error, read_attempted, pixel,
    );
    if kind != "Clear" && n <= 3 {
        for index in 0..8u32 {
            let mut enabled: GLint = 0;
            let mut size: GLint = 0;
            let mut buffer: GLint = 0;
            let mut stride: GLint = 0;
            gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_ENABLED, &mut enabled);
            if enabled == 0 {
                continue;
            }
            gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_SIZE, &mut size);
            gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_BUFFER_BINDING, &mut buffer);
            gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_STRIDE, &mut stride);
            log!("[ORDER UP ATTR v9] draw={} index={} enabled={} size={} buffer={} stride={}", n, index, enabled, size, buffer, stride);
        }
    }
}

'''
draw_anchor = "fn glDrawArrays(env: &mut Environment, mode: GLenum, first: GLint, count: GLsizei) {"
if guest.count(draw_anchor) != 1:
    raise SystemExit("V9 patch failed: glDrawArrays anchor not found")
guest = guest.replace(draw_anchor, trace_helper + draw_anchor + '\n    let order_up = env.bundle.bundle_identifier() == "com.chillingo.orderup";', 1)
elements_anchor = '''    indices: ConstVoidPtr,
) {
    if count > 0 {'''
if guest.count(elements_anchor) != 1:
    raise SystemExit("V9 patch failed: glDrawElements anchor not found")
guest = guest.replace(elements_anchor, '''    indices: ConstVoidPtr,
) {
    let order_up = env.bundle.bundle_identifier() == "com.chillingo.orderup";
    if count > 0 {''', 1)
for call, kind in [("gles.DrawArrays(mode, first, count);", "DrawArrays"), ("gles.DrawElements(mode, count, type_, indices);", "DrawElements")]:
    if guest.count(call) != 1:
        raise SystemExit(f"V9 patch failed: {kind} call anchor not found")
    guest = guest.replace(call, call + f'''
        if order_up && count > 0 {{
            trace_order_up_render_call(gles, "{kind}", mode, count);
        }}''', 1)
clear_anchor = "fn glClear(env: &mut Environment, mask: GLbitfield) {"
if guest.count(clear_anchor) != 1:
    raise SystemExit("V9 patch failed: glClear anchor not found")
guest = guest.replace(clear_anchor, clear_anchor + '\n    let order_up = env.bundle.bundle_identifier() == "com.chillingo.orderup";', 1)
clear_call = "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.Clear(mask) });"
if guest.count(clear_call) != 1:
    raise SystemExit("V9 patch failed: Clear call anchor not found")
guest = guest.replace(clear_call, '''    with_ctx_and_mem(env, |gles, _mem| unsafe {
        gles.Clear(mask);
        if order_up {
            trace_order_up_render_call(gles, "Clear", mask, 0);
        }
    });''', 1)

eagl_source.write_text(eagl)
guest_source.write_text(guest)
print("Applied Order Up validated framebuffer/draw-state probe v9")
