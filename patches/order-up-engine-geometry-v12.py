from pathlib import Path

source = Path("applesauce/src/frameworks/opengles/gles_guest.rs")
text = source.read_text()


def replace_once(old, new):
    global text
    if text.count(old) != 1:
        raise SystemExit("V12 patch failed: insertion point is missing or ambiguous")
    text = text.replace(old, new, 1)


helpers = r'''// V11's phone trace established zero screen_dims and zero-area GUI
// vertices. Fix the engine inputs before its initial viewport and menu
// geometry are calculated, rather than only changing the GL uniform.
// These addresses were verified against the supplied decrypted ARMv7
// executable. Require the title/version, section layout and independent
// instruction signatures; a different executable must not be modified.
fn order_up_geometry_v12_slide(env: &Environment) -> Option<u32> {
    if env.bundle.bundle_identifier() != "com.chillingo.orderup"
        || env.bundle.bundle_version() != "1.0"
    {
        return None;
    }
    let bin = env.bins.first()?;
    let slide = bin.text_base.checked_sub(0x1000)?;
    let _data_end = 0x65bb9c_u32.checked_add(slide)?;
    let code = bin.get_section("__text")?;
    let data = bin.get_section("__data")?;
    if code.addr != 0x3c6c_u32.checked_add(slide)? || code.size != 0x587890
        || data.addr != 0x6564b8_u32.checked_add(slide)? || data.size != 0x56e4
    {
        return None;
    }
    const SIGNATURES: &[(u32, &[u32])] = &[
        (0x3e76c0, &[0xe59f30b0, 0xe1a0000a, 0xe3a04000, 0xe79f1003]),
        (0x371e34, &[0xe79f2003, 0xe59d3448, 0xe5823000, 0xe59d3468, 0xe5823004]),
        (0x3e8104, &[0xe92d40b0, 0xe28d7008, 0xe59035a0, 0xe1a05000]),
        (0x3e8190, &[0xe5942008, 0xe594000c, 0xee072a10, 0xee050a10]),
    ];
    for &(address, words) in SIGNATURES {
        let address = address.checked_add(slide)?;
        for (index, &expected) in words.iter().enumerate() {
            let actual: u32 = env.mem.read(ConstPtr::from_bits(address + index as u32 * 4));
            if actual != expected {
                log_once!("[ORDER UP GEOMETRY v12] Executable signature mismatch; engine repair skipped.");
                return None;
            }
        }
    }
    Some(slide)
}

fn repair_order_up_geometry_v12(env: &mut Environment, slide: u32, phase: &str) {
    let mut old_dims = [[0i32; 2]; 2];
    let mut dims = old_dims;
    let mut old_scales = [[0.0f32; 2]; 2];
    let mut scales = old_scales;
    for pair in 0..2 {
        for axis in 0..2 {
            let dim_addr = slide + 0x65ad28 + pair as u32 * 8 + axis as u32 * 4;
            let scale_addr = slide + 0x65ad38 + pair as u32 * 8 + axis as u32 * 4;
            old_dims[pair][axis] = env.mem.read(ConstPtr::from_bits(dim_addr));
            old_scales[pair][axis] = env.mem.read(ConstPtr::from_bits(scale_addr));
            dims[pair][axis] = old_dims[pair][axis];
            scales[pair][axis] = old_scales[pair][axis];
            if dims[pair][axis] <= 0 {
                dims[pair][axis] = if axis == 0 { 480 } else { 320 };
                env.mem.write(MutPtr::from_bits(dim_addr), dims[pair][axis]);
            }
            if !scales[pair][axis].is_finite() || scales[pair][axis] <= 0.0 {
                scales[pair][axis] = 1.0;
                env.mem.write(MutPtr::from_bits(scale_addr), scales[pair][axis]);
            }
        }
    }
    use std::sync::atomic::{AtomicU32, Ordering};
    static SAMPLES: AtomicU32 = AtomicU32::new(0);
    let sample = SAMPLES.fetch_add(1, Ordering::Relaxed) + 1;
    if sample <= 8 {
        log!("[ORDER UP GEOMETRY v12] phase={} sample={} reference_dims={:?}->{:?} render_dims={:?}->{:?} reference_scale={:?}->{:?} render_scale={:?}->{:?}",
            phase, sample, old_dims[0], dims[0], old_dims[1], dims[1],
            old_scales[0], scales[0], old_scales[1], scales[1]);
    }
}

fn repair_order_up_viewport_geometry_v12(
    env: &mut Environment,
    slide: u32,
    width: &mut GLsizei,
    height: &mut GLsizei,
) {
    // The verified ARM caller keeps the selected rectangle in r4 and the
    // renderer in r5. After glViewport it reads that same rectangle again
    // to compute its aspect ratio. Repairing GL alone leaves that ratio
    // undefined, as well as leaving the guest's cached dimensions at zero.
    if env.cpu.regs()[crate::cpu::Cpu::LR] != slide + 0x3e8190 {
        return;
    }
    let rect = env.cpu.regs()[4];
    let renderer = env.cpu.regs()[5];
    let Some(cached) = renderer.checked_add(0x5a0) else { return; };
    if rect < env.mem.null_segment_size() || rect.checked_add(28).is_none()
        || renderer < env.mem.null_segment_size() || cached.checked_add(4).is_none()
        || rect % 4 != 0 || renderer % 4 != 0
    {
        return;
    }
    if env.mem.read(ConstPtr::<u32>::from_bits(cached)) != rect {
        return;
    }
    let old = [
        env.mem.read(ConstPtr::<i32>::from_bits(rect + 8)),
        env.mem.read(ConstPtr::<i32>::from_bits(rect + 12)),
    ];
    let mut new = old;
    for axis in 0..2 {
        if old[axis] <= 0 {
            let dim: i32 = env.mem.read(ConstPtr::from_bits(slide + 0x65ad30 + axis as u32 * 4));
            let scale: f32 = env.mem.read(ConstPtr::from_bits(slide + 0x65ad40 + axis as u32 * 4));
            new[axis] = (dim as f32 * scale) as i32;
            if new[axis] <= 0 {
                new[axis] = if axis == 0 { 480 } else { 320 };
            }
            env.mem.write(MutPtr::from_bits(rect + 8 + axis as u32 * 4), new[axis]);
        }
    }
    if *width <= 0 { *width = new[0]; }
    if *height <= 0 { *height = new[1]; }

    // GUI position generation reads the canvas multipliers at +20/+24.
    // Record them without guessing a replacement for a valid transform.
    let canvas: u32 = env.mem.read(ConstPtr::from_bits(slide + 0x65ad1c));
    let canvas_scale = if canvas >= env.mem.null_segment_size()
        && canvas.checked_add(28).is_some() && canvas % 4 == 0
    {
        Some([
            env.mem.read(ConstPtr::<f32>::from_bits(canvas + 20)),
            env.mem.read(ConstPtr::<f32>::from_bits(canvas + 24)),
        ])
    } else {
        None
    };
    log!("[ORDER UP VIEWPORT GEOMETRY v12] rect=0x{:x} old={:?} new={:?} gl=({}, {}) canvas=0x{:x} canvas_scale={:?}",
        rect, old, new, *width, *height, canvas, canvas_scale);
}

'''

replace_once("fn glViewport(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {", helpers + "fn glViewport(env: &mut Environment, x: GLint, y: GLint, width: GLsizei, height: GLsizei) {")

replace_once(
    "    // ULTRAHLE_MINIONJUMP_VIEWPORT_END\n    let (mut x, mut y, mut width, mut height) = (x, y, width, height);\n",
    "    // ULTRAHLE_MINIONJUMP_VIEWPORT_END\n    let (mut x, mut y, mut width, mut height) = (x, y, width, height);\n\n"
    "    if let Some(slide) = order_up_geometry_v12_slide(env) {\n"
    "        repair_order_up_geometry_v12(env, slide, \"viewport\");\n"
    "        repair_order_up_viewport_geometry_v12(env, slide, &mut width, &mut height);\n"
    "    }\n",
)

replace_once(
    "fn glBlendEquation(env: &mut Environment, mode: GLenum) {\n    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.BlendEquation(mode) });\n}",
    "fn glBlendEquation(env: &mut Environment, mode: GLenum) {\n"
    "    if let Some(slide) = order_up_geometry_v12_slide(env) {\n"
    "        // Last GL setup call before the ES2 renderer reads the engine\n"
    "        // dimensions to construct its initial viewport.\n"
    "        if env.cpu.regs()[crate::cpu::Cpu::LR] == slide + 0x3e76c0 {\n"
    "            repair_order_up_geometry_v12(env, slide, \"renderer-init\");\n"
    "        }\n"
    "    }\n"
    "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.BlendEquation(mode) });\n}"
)

replace_once(
    "fn glEnable(env: &mut Environment, cap: GLenum) {\n    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.Enable(cap) });\n}",
    "fn glEnable(env: &mut Environment, cap: GLenum) {\n"
    "    if cap == gles11::SCISSOR_TEST {\n"
    "        if let Some(slide) = order_up_geometry_v12_slide(env) {\n"
    "            if env.cpu.regs()[crate::cpu::Cpu::LR] == slide + 0x3da0bc {\n"
    "                repair_order_up_geometry_v12(env, slide, \"renderer-init-es1\");\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.Enable(cap) });\n}"
)

source.write_text(text)
print("Applied Order Up guarded engine geometry repair v12")
