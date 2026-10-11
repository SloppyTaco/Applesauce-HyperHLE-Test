"""V19: let buttonless loading alerts return while guest loading continues.

Applied after V18. Alerts with real buttons retain V18's native dialog and
callback behavior. This does not change game executables, assets or saves.
"""
from pathlib import Path


def edit(path, old, new):
    source = Path('applesauce') / path
    text = source.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'V19 patch failed: missing or ambiguous anchor in {path}')
    source.write_text(text.replace(old, new, 1))


ALERT = 'src/frameworks/uikit/ui_view/ui_alert_view.rs'

edit(ALERT, '    visible: bool,\n',
     '    visible: bool,\n    owns_loading_presentation: bool,\n')
edit(ALERT, '        visible:             false,\n',
     '        visible:             false,\n        owns_loading_presentation: false,\n')
edit(ALERT, '''- (())show {
    log!("UIAlertView show (SDL2 dialog)");''',
     '''- (())show {
    // UIKit ignores a second show while the same alert is already visible.
    if env.objc.borrow::<UIAlertViewHostObject>(this).visible { return; }
    log!("UIAlertView show (SDL2 dialog)");''')
edit(ALERT, '''    if env.options.headless {
        log!("[ALERT CALLBACK v18] Headless alert presented; waiting for a user event or programmatic dismissal");''',
     '''    let btn_count: NSUInteger = msg![env; buttons count];
    if btn_count == 0 {
        // A progress alert is dismissed by the app when loading finishes.
        // Waiting in SDL_ShowMessageBox would suspend the guest scheduler,
        // preventing its worker and completion selector from getting there.
        // Keep logical visibility and ownership until the original app
        // dismisses it. Do not invent an OK button or a user-click callback.
        retain(env, this);
        env.objc.borrow_mut::<UIAlertViewHostObject>(this)
            .owns_loading_presentation = true;
        log!("[ALERT LOADING v19] Buttonless loading alert is nonblocking; title={:?}", raw_title);
        return;
    }

    if env.options.headless {
        log!("[ALERT CALLBACK v18] Headless alert presented; waiting for a user event or programmatic dismissal");''')
edit(ALERT, '''    let btn_count: NSUInteger = msg![env; buttons count];
    let mut btn_strings: Vec<String> = Vec::new();''',
     '''    let mut btn_strings: Vec<String> = Vec::new();''')
edit(ALERT, '''    if !env.objc.borrow::<UIAlertViewHostObject>(this).visible { return; }
    env.objc.borrow_mut::<UIAlertViewHostObject>(this).visible = false;
    retain(env, this);''',
     '''    let owns_loading_presentation = {
        let host = env.objc.borrow_mut::<UIAlertViewHostObject>(this);
        if !host.visible { return; }
        host.visible = false;
        std::mem::take(&mut host.owns_loading_presentation)
    };
    retain(env, this);''')
edit(ALERT, '''    release(env, this);
}

- (id)description {''',
     '''    if owns_loading_presentation {
        log!("[ALERT LOADING v19] Loading alert dismissed by the game");
        release(env, this);
    }
    release(env, this);
}

- (id)description {''')

print('Applied V19 nonblocking buttonless loading alerts; V18 button handling retained.')
