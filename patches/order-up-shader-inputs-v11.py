from pathlib import Path


def replace_once(text, old, new, description):
    if text.count(old) != 1:
        raise SystemExit(f"V11 patch failed: expected {description} exactly once")
    return text.replace(old, new, 1)


native_source = Path("applesauce/src/gles/gles2_native.rs")
native = native_source.read_text()
native = replace_once(
    native,
    '''    unsafe fn GetUniformLocation(&mut self, program: GLuint, name: *const GLchar) -> GLint {
        gles2::GetUniformLocation(program, name)
    }
''',
    '''    unsafe fn GetUniformLocation(&mut self, program: GLuint, name: *const GLchar) -> GLint {
        gles2::GetUniformLocation(program, name)
    }
    unsafe fn GetUniformfv(&mut self, program: GLuint, location: GLint, params: *mut GLfloat) {
        gles2::GetUniformfv(program, location, params)
    }
    unsafe fn GetUniformiv(&mut self, program: GLuint, location: GLint, params: *mut GLint) {
        gles2::GetUniformiv(program, location, params)
    }
    unsafe fn GetTexParameteriv(&mut self, target: GLenum, pname: GLenum, params: *mut GLint) {
        gles2::GetTexParameteriv(target, pname, params)
    }
''',
    "native ES2 uniform getter insertion point",
)

guest_source = Path("applesauce/src/frameworks/opengles/gles_guest.rs")
guest = guest_source.read_text()
helper_anchor = "// Bound the logging and readbacks to startup and a few later milestones."
helpers = '''// The shipped GUI vertex shader divides pos_attr.xy by screen_dims.xy.
// A valid GL viewport cannot compensate for a zero/non-finite divisor there.
// Repair only that invalid uniform for this title's known 480x320 GUI space.
unsafe fn repair_order_up_screen_dims(gles: &mut dyn GLES) {
    use crate::gles::gles2_raw as gl;
    use std::sync::atomic::{AtomicU32, Ordering};
    if !gles.is_es2() {
        return;
    }
    let mut program: GLint = 0;
    gles.GetIntegerv(gl::CURRENT_PROGRAM, &mut program);
    if program <= 0 {
        return;
    }
    let location = gles.GetUniformLocation(program as GLuint, b"screen_dims\\0".as_ptr().cast());
    if location < 0 {
        return;
    }
    // Sixteen components also make this query safe if the named uniform is a
    // matrix in an unexpected program. The shipped GUI uses a vec4.
    let mut values = [0.0f32; 16];
    gles.GetUniformfv(program as GLuint, location, values.as_mut_ptr());
    if values[0].is_finite() && values[0] > 0.0
        && values[1].is_finite() && values[1] > 0.0
    {
        return;
    }
    // Confirm the vec4 type before writing; never alter an unrelated shader.
    let mut active: GLint = 0;
    gles.GetProgramiv(program as GLuint, gl::ACTIVE_UNIFORMS, &mut active);
    let mut is_vec4 = false;
    for index in 0..active.clamp(0, 128) as GLuint {
        let mut name = [0u8; 256];
        let mut length: GLsizei = 0;
        let mut size: GLint = 0;
        let mut type_: GLenum = 0;
        gles.GetActiveUniform(program as GLuint, index, name.len() as GLsizei,
            &mut length, &mut size, &mut type_, name.as_mut_ptr().cast());
        let length = (length.max(0) as usize).min(name.len() - 1);
        if &name[..length] == b"screen_dims" && type_ == gl::FLOAT_VEC4 && size == 1 {
            is_vec4 = true;
            break;
        }
    }
    if !is_vec4 {
        return;
    }
    let old = [values[0], values[1], values[2], values[3]];
    if !values[0].is_finite() || values[0] <= 0.0 {
        values[0] = 480.0;
    }
    if !values[1].is_finite() || values[1] <= 0.0 {
        values[1] = 320.0;
    }
    gles.Uniform4fv(location, 1, values.as_ptr());
    static REPAIRS: AtomicU32 = AtomicU32::new(0);
    let repair = REPAIRS.fetch_add(1, Ordering::Relaxed) + 1;
    if repair <= 8 {
        log!("[ORDER UP FIX v11] screen_dims repair={} program={} location={} old={:?} new={:?}",
            repair, program, location, old, &values[..4]);
    }
}

// Sample actual shader inputs at the same bounded draw milestones as V9.
// These queries preserve the guest's program, textures and array state.
unsafe fn trace_order_up_shader_inputs(
    gles: &mut dyn GLES, mem: &Mem, program: GLuint, draw: u64,
    first: Option<GLint>, count: GLsizei,
) {
    use crate::gles::gles2_raw as gl;
    if program == 0 {
        return;
    }
    let mut active: GLint = 0;
    gles.GetProgramiv(program, gl::ACTIVE_UNIFORMS, &mut active);
    for index in 0..active.clamp(0, 32) as GLuint {
        let mut name = [0u8; 256];
        let mut length: GLsizei = 0;
        let mut size: GLint = 0;
        let mut type_: GLenum = 0;
        gles.GetActiveUniform(program, index, name.len() as GLsizei,
            &mut length, &mut size, &mut type_, name.as_mut_ptr().cast());
        let length = (length.max(0) as usize).min(name.len() - 1);
        name[length] = 0;
        let location = gles.GetUniformLocation(program, name.as_ptr().cast());
        if location < 0 {
            continue;
        }
        let name = String::from_utf8_lossy(&name[..length]);
        let components = match type_ {
            gl::FLOAT | gl::INT | gl::BOOL | gl::SAMPLER_2D | gl::SAMPLER_CUBE => 1,
            gl::FLOAT_VEC2 | gl::INT_VEC2 | gl::BOOL_VEC2 => 2,
            gl::FLOAT_VEC3 | gl::INT_VEC3 | gl::BOOL_VEC3 => 3,
            gl::FLOAT_VEC4 | gl::INT_VEC4 | gl::BOOL_VEC4 | gl::FLOAT_MAT2 => 4,
            gl::FLOAT_MAT3 => 9,
            gl::FLOAT_MAT4 => 16,
            _ => continue,
        };
        let mut values = [0.0f32; 16];
        gles.GetUniformfv(program, location, values.as_mut_ptr());
        log!("[ORDER UP UNIFORM v11] draw={} program={} name={} location={} type=0x{:x} array_size={} first_element={:?}",
            draw, program, name, location, type_, size, &values[..components]);
        if type_ == gl::SAMPLER_2D {
            let mut unit: GLint = -1;
            let mut max_units: GLint = 0;
            let mut old_active: GLint = 0;
            gles.GetUniformiv(program, location, &mut unit);
            gles.GetIntegerv(gl::MAX_COMBINED_TEXTURE_IMAGE_UNITS, &mut max_units);
            gles.GetIntegerv(gl::ACTIVE_TEXTURE, &mut old_active);
            if unit >= 0 && unit < max_units {
                gles.ActiveTexture(gl::TEXTURE0 + unit as GLenum);
                let mut texture: GLint = 0;
                let mut min_filter: GLint = 0;
                let mut mag_filter: GLint = 0;
                let mut wrap_s: GLint = 0;
                let mut wrap_t: GLint = 0;
                gles.GetIntegerv(gl::TEXTURE_BINDING_2D, &mut texture);
                gles.GetTexParameteriv(gl::TEXTURE_2D, gl::TEXTURE_MIN_FILTER, &mut min_filter);
                gles.GetTexParameteriv(gl::TEXTURE_2D, gl::TEXTURE_MAG_FILTER, &mut mag_filter);
                gles.GetTexParameteriv(gl::TEXTURE_2D, gl::TEXTURE_WRAP_S, &mut wrap_s);
                gles.GetTexParameteriv(gl::TEXTURE_2D, gl::TEXTURE_WRAP_T, &mut wrap_t);
                log!("[ORDER UP SAMPLER v11] draw={} name={} unit={} texture={} min=0x{:x} mag=0x{:x} wrap_s=0x{:x} wrap_t=0x{:x}",
                    draw, name, unit, texture, min_filter, mag_filter, wrap_s, wrap_t);
                gles.ActiveTexture(old_active as GLenum);
            }
        }
    }
    for (name, pname) in [
        ("front_face", gl::FRONT_FACE), ("cull_mode", gl::CULL_FACE_MODE),
        ("blend_src_rgb", gl::BLEND_SRC_RGB), ("blend_dst_rgb", gl::BLEND_DST_RGB),
        ("blend_src_alpha", gl::BLEND_SRC_ALPHA), ("blend_dst_alpha", gl::BLEND_DST_ALPHA),
        ("blend_equation_rgb", gl::BLEND_EQUATION_RGB),
        ("blend_equation_alpha", gl::BLEND_EQUATION_ALPHA),
    ] {
        let mut value: GLint = 0;
        gles.GetIntegerv(pname, &mut value);
        log!("[ORDER UP STATE v11] draw={} {}=0x{:x}", draw, name, value);
    }
    let mut active_attrs: GLint = 0;
    gles.GetProgramiv(program, gl::ACTIVE_ATTRIBUTES, &mut active_attrs);
    for attr in 0..active_attrs.clamp(0, 16) as GLuint {
        let mut name = [0u8; 256];
        let mut length: GLsizei = 0;
        let mut size: GLint = 0;
        let mut type_: GLenum = 0;
        gles.GetActiveAttrib(program, attr, name.len() as GLsizei,
            &mut length, &mut size, &mut type_, name.as_mut_ptr().cast());
        let length = (length.max(0) as usize).min(name.len() - 1);
        name[length] = 0;
        let location = gles.GetAttribLocation(program, name.as_ptr().cast());
        if location < 0 {
            continue;
        }
        let name = String::from_utf8_lossy(&name[..length]);
        let index = location as GLuint;
        let mut enabled: GLint = 0;
        let mut components: GLint = 0;
        let mut buffer: GLint = 0;
        let mut stride: GLint = 0;
        let mut array_type: GLint = 0;
        gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_ENABLED, &mut enabled);
        gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_SIZE, &mut components);
        gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_BUFFER_BINDING, &mut buffer);
        gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_STRIDE, &mut stride);
        gles.GetVertexAttribiv(index, gl::VERTEX_ATTRIB_ARRAY_TYPE, &mut array_type);
        let mut current = [0.0f32; 4];
        gles.GetVertexAttribfv(index, gl::CURRENT_VERTEX_ATTRIB, current.as_mut_ptr());
        log!("[ORDER UP VERTEX v11] draw={} name={} index={} enabled={} components={} buffer={} stride={} type=0x{:x} default={:?}",
            draw, name, index, enabled, components, buffer, stride, array_type, current);
        if enabled == 0 || buffer != 0 || array_type as GLenum != gl::FLOAT
            || !(1..=4).contains(&components) || stride < 0
        {
            continue;
        }
        let Some(first) = first.filter(|&v| v >= 0) else { continue; };
        let mut pointer: *mut GLvoid = std::ptr::null_mut();
        gles.GetVertexAttribPointerv(index, gl::VERTEX_ATTRIB_ARRAY_POINTER, &mut pointer);
        if !mem.is_host_ptr_in_guest_mem(pointer) {
            continue;
        }
        let base = mem.host_ptr_to_guest_ptr(pointer).to_bits();
        let step = if stride == 0 { components as u32 * 4 } else { stride as u32 };
        for vertex in 0..count.clamp(0, 4) as u32 {
            let Some(offset) = (first as u32).checked_add(vertex).and_then(|v| v.checked_mul(step))
                else { break; };
            let Some(address) = base.checked_add(offset) else { break; };
            let Some(end) = offset.checked_add(components as u32 * 4 - 1) else { break; };
            if address < mem.null_segment_size()
                || !mem.is_host_ptr_in_guest_mem(pointer.cast::<u8>().wrapping_add(end as usize).cast())
            {
                break;
            }
            let mut values = [0.0f32; 4];
            for component in 0..components as usize {
                values[component] = mem.read(ConstPtr::<GLfloat>::from_bits(address + component as u32 * 4));
            }
            log!("[ORDER UP VERTEX v11] draw={} name={} vertex={} guest=0x{:x} values={:?}",
                draw, name, first as u32 + vertex, address, &values[..components as usize]);
        }
    }
    let error = gles.GetError();
    log!("[ORDER UP INPUTS v11] draw={} query_error=0x{:x}", draw, error);
}

'''
guest = replace_once(guest, helper_anchor, helpers + helper_anchor, "draw trace helper anchor")
guest = replace_once(
    guest,
    'unsafe fn trace_order_up_render_call(gles: &mut dyn GLES, kind: &str, mode: GLenum, count: GLsizei) {',
    '''unsafe fn trace_order_up_render_call(
    gles: &mut dyn GLES, mem: &Mem, kind: &str, mode: GLenum, count: GLsizei,
    first: Option<GLint>,
) {''',
    "V9 trace signature",
)
guest = replace_once(
    guest,
    '    if kind != "Clear" && n <= 3 {',
    '''    if kind != "Clear" && linked != 0 {
        trace_order_up_shader_inputs(gles, mem, program as GLuint, n, first, count);
    }
    if kind != "Clear" && n <= 3 {''',
    "draw input trace insertion point",
)
for kind, first in (("DrawArrays", "Some(first)"), ("DrawElements", "None")):
    guest = replace_once(
        guest,
        f'            trace_order_up_render_call(gles, "{kind}", mode, count);',
        f'            trace_order_up_render_call(gles, mem, "{kind}", mode, count, {first});',
        f"{kind} trace call",
    )
guest = replace_once(
    guest,
    '            trace_order_up_render_call(gles, "Clear", mask, 0);',
    '            trace_order_up_render_call(gles, _mem, "Clear", mask, 0, None);',
    "clear trace call",
)
for call in ("gles.DrawArrays(mode, first, count);", "gles.DrawElements(mode, count, type_, indices);"):
    guest = replace_once(
        guest,
        f'''        if order_up && count > 0 {{
            repair_order_up_empty_scissor(gles);
        }}
        {call}''',
        f'''        if order_up && count > 0 {{
            repair_order_up_empty_scissor(gles);
            repair_order_up_screen_dims(gles);
        }}
        {call}''',
        f"{call} shader dimension repair insertion point",
    )

# The V10 phone screenshot proves presentation, so stop covering the game's
# image with the old green square. Keep the original source/display readbacks.
eagl_source = Path("applesauce/src/frameworks/opengles/eagl.rs")
eagl = eagl_source.read_text()
start = '    if frame >= 60 && status == gl::FRAMEBUFFER_COMPLETE && setup_error == gl::NO_ERROR {'
end = '    gles.DeleteFramebuffersOES(1, &probe_fb);'
if eagl.count(start) != 1 or eagl.count(end) != 1:
    raise SystemExit("V11 patch failed: expected green-square probe anchors exactly once")
begin = eagl.index(start)
finish = eagl.index(end, begin)
eagl = eagl[:begin] + eagl[finish:]
eagl = replace_once(
    eagl,
    '''// Diagnostic only: a green control square bypasses the game's shaders while
// going through the same renderbuffer and presentation path as its image.''',
    '''// V10 confirmed display delivery; retain bounded readbacks of the game's
// source image without injecting the old green control square.''',
    "presentation probe comment",
)

native_source.write_text(native)
guest_source.write_text(guest)
eagl_source.write_text(eagl)
print("Applied Order Up invalid shader-dimension repair and input diagnostics v11")
