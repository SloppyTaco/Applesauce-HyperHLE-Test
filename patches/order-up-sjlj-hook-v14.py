from pathlib import Path


def edit(path, old, new):
    source = Path("applesauce") / path
    text = source.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"V14 patch failed: missing or ambiguous anchor in {path}")
    source.write_text(text.replace(old, new, 1))


edit("src/order_up.rs",
     "    shader_events: u32,\n",
     "    shader_events: u32,\n"
     "    sjlj_register: Option<GuestFunction>,\n"
     "    sjlj_unregister: Option<GuestFunction>,\n"
     "    sjlj_calls: u32,\n")

hooks = r'''
// The bundled libgcc exports these functions and normally wins lazy binding.
// Install observation wrappers before guest startup, then forward every call
// to those original exports so the real thread-local unwind chain survives.
pub(crate) fn install_sjlj_hooks(env: &mut Environment) {
    if matching_slide(env).is_none() {
        return;
    }
    const SYMBOLS: [&str; 2] = [
        "__Unwind_SjLj_Register", "__Unwind_SjLj_Unregister",
    ];
    let targets: Vec<_> = SYMBOLS.iter().map(|symbol| {
        env.bins.iter().skip(1).find_map(|bin| {
            bin.exported_symbols.get(*symbol).copied()
        })
    }).collect();
    let (Some(register), Some(unregister)) = (targets[0], targets[1]) else {
        log!("[ORDER UP HOOK v14] Original SjLj exports missing; wrappers skipped.");
        return;
    };
    let wrappers: Vec<_> = SYMBOLS.iter().map(|symbol| {
        env.dyld.create_proc_address(&mut env.mem, &mut env.cpu, symbol)
            .expect("Order Up SjLj wrapper must be exported")
    }).collect();
    env.libc_state.order_up.sjlj_register =
        Some(GuestFunction::from_addr_with_thumb_bit(register));
    env.libc_state.order_up.sjlj_unregister =
        Some(GuestFunction::from_addr_with_thumb_bit(unregister));

    // Initial non-lazy linking has already run. Update those pointers too;
    // lazy imports use the cached wrappers above before looking in dylibs.
    for bin in &env.bins {
        let Some(section) = bin.get_section(
            crate::mach_o::SectionType::NonLazySymbolPointers
        ) else { continue; };
        let Some(info) = section.dyld_indirect_symbol_info.as_ref()
            else { continue; };
        if info.entry_size != 4 { continue; }
        for (index, symbol) in info.indirect_undef_symbols.iter().enumerate() {
            let Some(symbol) = symbol.as_deref() else { continue; };
            if let Some(which) = SYMBOLS.iter().position(|&name| name == symbol) {
                let pointer = crate::mem::MutPtr::<u32>::from_bits(
                    section.addr + index as u32 * info.entry_size
                );
                env.mem.write(pointer, wrappers[which].addr_with_thumb_bit());
            }
        }
    }
    log!("[ORDER UP HOOK v14] SjLj wrappers installed; original register=0x{:x} unregister=0x{:x}",
        register, unregister);
}

pub(crate) fn forward_sjlj(env: &mut Environment, frame: MutVoidPtr, register: bool) {
    let state = &mut env.libc_state.order_up;
    let target = if register { state.sjlj_register } else { state.sjlj_unregister };
    let Some(target) = target else { return; };
    state.sjlj_calls += 1;
    if state.sjlj_calls <= 8 {
        log!("[ORDER UP SJLJ v14] register={} frame=0x{:x} caller=0x{:x} original=0x{:x}",
            register, frame.to_bits(), env.cpu.regs()[Cpu::LR],
            target.addr_with_thumb_bit());
    }
    let (): () = target.call_from_host(env, (frame,));
}
'''

edit("src/order_up.rs", "pub(crate) fn matching_slide(env:",
     hooks + "\npub(crate) fn matching_slide(env:")
edit("src/libc/cxxabi.rs",
     "    crate::order_up::register_frame(env, jmpbuf);\n}",
     "    crate::order_up::register_frame(env, jmpbuf);\n"
     "    crate::order_up::forward_sjlj(env, jmpbuf, true);\n}")
edit("src/libc/cxxabi.rs",
     "    crate::order_up::unregister_frame(env, jmpbuf);\n}",
     "    crate::order_up::unregister_frame(env, jmpbuf);\n"
     "    crate::order_up::forward_sjlj(env, jmpbuf, false);\n}")
edit("src/dyld.rs",
     "    pub fn do_late_linking(env: &mut Environment) {\n",
     "    pub fn do_late_linking(env: &mut Environment) {\n"
     "        crate::order_up::install_sjlj_hooks(env);\n")

print("Applied V14: guarded SjLj observation wrappers forward to original guest libgcc")
