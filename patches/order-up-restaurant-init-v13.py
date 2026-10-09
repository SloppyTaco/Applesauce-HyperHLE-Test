from pathlib import Path


def edit(path, old, new):
    source = Path("applesauce") / path
    text = source.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"V13 patch failed: missing or ambiguous anchor in {path}")
    source.write_text(text.replace(old, new, 1))


module = r'''// Order Up!! 1.0 restaurant initialization recovery and bounded traces.
// The V12 phone reaches the menu but polls a null restaurant at 0x1565ec.
// Replay the original initializer only for an empty, unselected manager,
// before the level registers its load task. Never fabricate a restaurant
// or report the readiness check as successful.
use crate::abi::{CallFromHost, GuestFunction};
use crate::cpu::{Cpu, CpuContext};
use crate::mem::{ConstPtr, MutVoidPtr};
use crate::Environment;
use std::collections::{HashMap, HashSet};

#[derive(Default)]
pub(crate) struct State {
    checked: bool,
    slide: Option<u32>,
    recovery_attempted: bool,
    init_frames: HashSet<u32>,
    module_frames: HashMap<u32, u32>,
    nil_sites: HashSet<u32>,
    level_entries: u32,
    shader_events: u32,
}

pub(crate) fn matching_slide(env: &mut Environment) -> Option<u32> {
    if env.libc_state.order_up.checked {
        return env.libc_state.order_up.slide;
    }
    let slide = verify_executable(env);
    env.libc_state.order_up.checked = true;
    env.libc_state.order_up.slide = slide;
    slide
}

fn verify_executable(env: &Environment) -> Option<u32> {
    if env.bundle.bundle_identifier() != "com.chillingo.orderup"
        || env.bundle.bundle_version() != "1.0"
    {
        return None;
    }
    let bin = env.bins.first()?;
    let slide = bin.text_base.checked_sub(0x1000)?;
    let code = bin.get_section("__text")?;
    let data = bin.get_section("__data")?;
    let _end = 0x6598fc_u32.checked_add(slide)?;
    if code.addr != 0x3c6c_u32.checked_add(slide)? || code.size != 0x587890
        || data.addr != 0x6564b8_u32.checked_add(slide)? || data.size != 0x56e4
    {
        return None;
    }
    const SIGNATURES: &[(u32, &[u32])] = &[
        (0x157728, &[0xe92d40f0, 0xe28d700c, 0xe92d0d00, 0xed2d8b10,
            0xe24ddf7b, 0xe59f3f84, 0xe58d004c, 0xe28d0094]),
        (0x157770, &[0xeb10d219, 0xe59f0f58, 0xe59d204c]),
        (0xc775c, &[0xe92d40f0, 0xe28d700c, 0xe92d0d00, 0xed2d8b10,
            0xe24ddf5d, 0xe59f3fac, 0xe58d0010, 0xe28d0080]),
        (0xc77a4, &[0xeb13120c, 0xe59f3f80, 0xe79f0003, 0xe5900000]),
        (0x1565dc, &[0xe590001c, 0xe5903000, 0xe5933018, 0xe12fff33]),
        (0x3c8f00, &[0xe92d40f0, 0xe28d700c, 0xe92d0d00, 0xed2d8b10]),
    ];
    for &(address, words) in SIGNATURES {
        let address = address.checked_add(slide)?;
        for (index, &expected) in words.iter().enumerate() {
            if env.mem.read(ConstPtr::<u32>::from_bits(address + index as u32 * 4))
                != expected
            {
                log_once!("[ORDER UP INIT v13] Executable mismatch; recovery skipped.");
                return None;
            }
        }
    }
    Some(slide)
}

fn valid(env: &Environment, address: u32, size: u32) -> bool {
    address >= env.mem.null_segment_size() && address.checked_add(size).is_some()
}

fn word(env: &Environment, address: u32) -> u32 {
    if valid(env, address, 4) && address % 4 == 0 {
        env.mem.read(ConstPtr::from_bits(address))
    } else {
        0
    }
}

fn text(env: &Environment, address: u32) -> String {
    if !valid(env, address, 96) {
        return "<null>".into();
    }
    let bytes = env.mem.bytes_at(ConstPtr::from_bits(address), 96);
    let end = bytes.iter().position(|&b| b == 0).unwrap_or(bytes.len());
    String::from_utf8_lossy(&bytes[..end]).into_owned()
}

fn snapshot(env: &Environment, slide: u32, phase: &str) {
    let manager = word(env, slide + 0x656a70);
    let profile = word(env, slide + 0x656a74);
    let selected = if valid(env, profile, 0x12f04) {
        word(env, profile + 0x12f00)
    } else { 0 };
    let count = word(env, manager.saturating_add(8));
    let entries = word(env, manager.saturating_add(4));
    log!("[ORDER UP INIT v13] phase={} manager=0x{:x} vtable=0x{:x} count={} entries=0x{:x} current=0x{:x} defs=0x{:x} asset_store=0x{:x} scripts=0x{:x} selected=0x{:x}",
        phase, manager, word(env, manager), count, entries,
        word(env, manager.saturating_add(0x18)),
        word(env, manager.saturating_add(0x214)),
        word(env, slide + 0x6598f8), word(env, slide + 0x65a260), selected);
    if count <= 16 && valid(env, entries, count * 4) {
        for index in 0..count {
            let entry = word(env, entries + index * 4);
            let name = word(env, entry.saturating_add(0x14));
            log!("[ORDER UP RESTAURANT v13] phase={} index={} object=0x{:x} name={:?}",
                phase, index, entry, text(env, name));
        }
    }
}

fn recover_before_level(env: &mut Environment, slide: u32) {
    env.libc_state.order_up.level_entries += 1;
    if env.libc_state.order_up.level_entries <= 4 {
        snapshot(env, slide, "before-level");
    }
    if env.libc_state.order_up.recovery_attempted {
        return;
    }
    let manager = word(env, slide + 0x656a70);
    let profile = word(env, slide + 0x656a74);
    if !valid(env, manager, 0x218)
        || word(env, manager) != slide + 0x66ae6c
        || word(env, manager + 8) != 0
        || word(env, manager + 0x18) != 0
        || !valid(env, profile, 0x12f04)
        || word(env, profile + 0x12f00) != 0
        || !valid(env, word(env, slide + 0x6598f8), 0x18)
        || !valid(env, word(env, slide + 0x65a260), 8)
    {
        return;
    }
    env.libc_state.order_up.recovery_attempted = true;
    log_once!("[ORDER UP RECOVERY v13] Empty restaurant list: replaying the game's initializer before level setup.");

    // Preserve all CPU state and run with the original VFP registers and
    // FPSCR modes. Heap changes survive the call; CPU changes do not.
    let mut saved = CpuContext::new();
    env.cpu.swap_context(&mut saved);
    let mut execution = CpuContext {
        regs: saved.regs,
        extregs: saved.extregs,
        cpsr: saved.cpsr,
        fpscr: saved.fpscr,
    };
    env.cpu.swap_context(&mut execution);
    let (): () = GuestFunction::from_addr_with_thumb_bit(slide + 0xc775c)
        .call_from_host(env, (MutVoidPtr::from_bits(manager),));
    env.cpu.swap_context(&mut saved);
    snapshot(env, slide, "after-recovery");
}

pub(crate) fn register_frame(env: &mut Environment, frame: MutVoidPtr) {
    let Some(slide) = matching_slide(env) else { return; };
    let Some(site) = env.cpu.regs()[Cpu::LR].checked_sub(slide) else { return; };
    let address = frame.to_bits();
    if site == 0x157774 {
        recover_before_level(env, slide);
    } else if site == 0xc77a8 {
        env.libc_state.order_up.init_frames.insert(address);
        snapshot(env, slide, "initializer-enter");
    } else if site == 0x3c8f58 {
        let name = text(env, word(env, address.saturating_sub(0x10)));
        if name == "restaurant_defs" {
            let result = word(env, address.saturating_sub(8));
            env.libc_state.order_up.module_frames.insert(address, result);
            log!("[ORDER UP MODULE v13] loading {:?} into 0x{:x}", name, result);
        }
    }
}

pub(crate) fn unregister_frame(env: &mut Environment, frame: MutVoidPtr) {
    let Some(slide) = matching_slide(env) else { return; };
    let address = frame.to_bits();
    if env.libc_state.order_up.init_frames.remove(&address) {
        snapshot(env, slide, "initializer-exit");
    }
    if let Some(result) = env.libc_state.order_up.module_frames.remove(&address) {
        let module = word(env, result);
        log!("[ORDER UP MODULE v13] restaurant_defs result=0x{:x} body=0x{:x}",
            module, word(env, module.saturating_add(0xc)));
    }
}

pub(crate) fn note_nil_call(env: &mut Environment, pc: u32, lr: u32) {
    let Some(slide) = matching_slide(env) else { return; };
    if pc != env.mem.null_segment_size() { return; }
    let Some(site) = lr.checked_sub(slide) else { return; };
    if !matches!(site, 0x275ca9 | 0x271377 | 0x2713a5 | 0x27b075
        | 0x30ed88 | 0x30ee94 | 0x1583f0 | 0x1565ec)
        || !env.libc_state.order_up.nil_sites.insert(site)
    {
        return;
    }
    log!("[ORDER UP NIL v13] site=0x{:x} thread={} registers={:x?}",
        site, env.current_thread, env.cpu.regs());
    snapshot(env, slide, "nil-call");
    let Some(stack) = env.threads.get(env.current_thread).and_then(|t| t.stack.clone())
        else { return; };
    let mut fp = env.cpu.regs()[7];
    for depth in 0..8 {
        if fp % 4 != 0 || !stack.contains(&fp)
            || fp.checked_add(7).is_none_or(|end| !stack.contains(&end))
        {
            break;
        }
        let parent = word(env, fp);
        log!("[ORDER UP STACK v13] site=0x{:x} depth={} return=0x{:x}",
            site, depth, word(env, fp + 4));
        if parent <= fp { break; }
        fp = parent;
    }
}

pub(crate) fn shader_sample(env: &mut Environment) -> bool {
    if matching_slide(env).is_none() { return false; }
    env.libc_state.order_up.shader_events += 1;
    env.libc_state.order_up.shader_events <= 256
}
'''

target = Path("applesauce/src/order_up.rs")
if target.exists():
    raise SystemExit("V13 patch failed: helper module already exists")
target.write_text(module)

edit("src/lib.rs", "mod options;\n", "mod options;\nmod order_up;\n")
edit("src/libc.rs", "pub struct State {\n    aio:",
     "pub struct State {\n    pub(crate) order_up: crate::order_up::State,\n    aio:")
edit("src/libc/cxxabi.rs",
     "fn _Unwind_SjLj_Register(_env: &mut Environment, _jmpbuf: MutVoidPtr) {}",
     "fn _Unwind_SjLj_Register(env: &mut Environment, jmpbuf: MutVoidPtr) {\n"
     "    crate::order_up::register_frame(env, jmpbuf);\n}")
edit("src/libc/cxxabi.rs",
     "fn _Unwind_SjLj_Unregister(_env: &mut Environment, _jmpbuf: MutVoidPtr) {}",
     "fn _Unwind_SjLj_Unregister(env: &mut Environment, jmpbuf: MutVoidPtr) {\n"
     "    crate::order_up::unregister_frame(env, jmpbuf);\n}")
edit("src/environment.rs", "                // Track repeated occurrences of the same bypass site.\n",
     "                crate::order_up::note_nil_call(self, pc, lr);\n\n"
     "                // Track repeated occurrences of the same bypass site.\n")
edit("src/frameworks/opengles/gles_guest.rs",
     "fn glCreateShader(env: &mut Environment, type_: GLenum) -> GLuint {\n"
     "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.CreateShader(type_) })\n}",
     "fn glCreateShader(env: &mut Environment, type_: GLenum) -> GLuint {\n"
     "    let shader = with_ctx_and_mem(env, |gles, _mem| unsafe { gles.CreateShader(type_) });\n"
     "    if crate::order_up::shader_sample(env) {\n"
     "        log!(\"[ORDER UP SHADER v13] create shader={} type=0x{:x} caller=0x{:x}\",\n"
     "            shader, type_, env.cpu.regs()[crate::cpu::Cpu::LR]);\n    }\n"
     "    shader\n}")
edit("src/frameworks/opengles/gles_guest.rs",
     "fn glDeleteShader(env: &mut Environment, shader: GLuint) {\n"
     "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.DeleteShader(shader) });\n}",
     "fn glDeleteShader(env: &mut Environment, shader: GLuint) {\n"
     "    if crate::order_up::shader_sample(env) {\n"
     "        log!(\"[ORDER UP SHADER v13] delete shader={} caller=0x{:x}\",\n"
     "            shader, env.cpu.regs()[crate::cpu::Cpu::LR]);\n    }\n"
     "    with_ctx_and_mem(env, |gles, _mem| unsafe { gles.DeleteShader(shader) });\n}")
edit("src/frameworks/opengles/gles_guest.rs",
     "fn glAttachShader(env: &mut Environment, program: GLuint, shader: GLuint) {\n"
     "    with_ctx_and_mem(env, |gles, _mem| unsafe {\n"
     "        gles.AttachShader(program, shader)\n    });\n}",
     "fn glAttachShader(env: &mut Environment, program: GLuint, shader: GLuint) {\n"
     "    let sample = crate::order_up::shader_sample(env);\n"
     "    let caller = env.cpu.regs()[crate::cpu::Cpu::LR];\n"
     "    with_ctx_and_mem(env, |gles, _mem| unsafe {\n"
     "        if sample {\n"
     "            let valid = gles.IsShader(shader);\n"
     "            let mut kind: GLint = 0;\n"
     "            if valid != 0 { gles.GetShaderiv(shader, 0x8B4F, &mut kind); }\n"
     "            log!(\"[ORDER UP SHADER v13] attach program={} shader={} valid={} type=0x{:x} caller=0x{:x}\",\n"
     "                program, shader, valid, kind, caller);\n        }\n"
     "        gles.AttachShader(program, shader)\n    });\n}")

print("Applied V13: guarded restaurant initialization recovery and module/nil/shader traces")
