"""V22: direct native alert buttons and narrowly guarded private 1.41 DLC.

Apply after the complete V21 chain. No game bytes are present in this repo.
"""
from pathlib import Path

ROOT = Path(__file__).parent

def edit(path, old, new):
    target = Path('applesauce') / path
    text = target.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'V22 missing or ambiguous anchor in {path}')
    target.write_text(text.replace(old, new, 1))

native = Path('applesauce/vendor/rust-sdl2/sdl2-sys/SDL/src/video/uikit')
target = native / 'SDL_touchhle_asyncalert_v22.inc'
if target.exists():
    raise SystemExit('V22 native bridge already exists')
target.write_bytes((ROOT / 'async-alert-uikit-v22.inc').read_bytes())
edit('vendor/rust-sdl2/sdl2-sys/SDL/src/video/uikit/SDL_uikitmessagebox.m',
     '#include "SDL_touchhle_asyncalert_v20.inc"',
     '#include "SDL_touchhle_asyncalert_v22.inc"')
module = Path('applesauce/src/order_up_dlc_v22.rs')
if module.exists():
    raise SystemExit('V22 DLC module already exists')
module.write_bytes((ROOT / 'order-up-dlc-v22.rs').read_bytes())
edit('src/lib.rs', 'mod order_up_download;\n',
     'mod order_up_download;\nmod order_up_dlc_v22;\n')
edit('src/lib.rs', '        } else if arg == "--info" {\n',
     '        } else if let Some(path) = arg.strip_prefix("--check-order-up-dlc-pack=") {\n'
     '            echo!("{}", crate::order_up_dlc_v22::validate_pack_file(path)?);\n'
     '            return Ok(());\n'
     '        } else if arg == "--info" {\n')
edit('src/order_up.rs', '    pub(crate) offline_diner_ready: bool,\n',
     '    pub(crate) offline_diner_ready: bool,\n    pub(crate) v141_dlc_ready: bool,\n')
edit('src/order_up.rs', 'pub(crate) fn install_sjlj_hooks(env: &mut Environment) {\n',
     'pub(crate) fn install_sjlj_hooks(env: &mut Environment) {\n'
     '    crate::order_up_dlc_v22::prepare(env);\n')
edit('src/objc/messages.rs',
     '    if super2.is_none() && crate::order_up_download::interpose(env, selector, orig_class) {\n',
     '    if super2.is_none() && crate::order_up_dlc_v22::interpose(env, selector, orig_class) {\n'
     '        return;\n    }\n\n'
     '    if super2.is_none() && crate::order_up_download::interpose(env, selector, orig_class) {\n')
