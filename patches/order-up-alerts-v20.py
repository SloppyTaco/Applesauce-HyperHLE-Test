"""V20: asynchronous iOS button alerts with real, exactly-once user events.

Applied after the complete V19 chain. No guest/asset/save modifications.
Desktop graphical dialogs retain their previous path; headless guests exercise
the same presentation ownership and timer/callback path without native UIKit.
"""
from pathlib import Path
import shutil


def edit(path, old, new):
    source = Path('applesauce') / path
    text = source.read_text()
    if text.count(old) != 1:
        raise SystemExit(f'V20 patch failed: missing or ambiguous anchor in {path}')
    source.write_text(text.replace(old, new, 1))


ALERT = 'src/frameworks/uikit/ui_view/ui_alert_view.rs'
edit(ALERT, '    owns_loading_presentation: bool,\n', '''    owns_loading_presentation: bool,
    owns_native_presentation: bool,
    native_alert_token: u64,
    native_alert_timer: id,
    native_poll_count: u32,
''')
edit(ALERT, '        owns_loading_presentation: false,\n', '''        owns_loading_presentation: false,
        owns_native_presentation: false,
        native_alert_token: 0,
        native_alert_timer: nil,
        native_poll_count: 0,
''')
edit(ALERT, '''    if env.options.headless {
        log!("[ALERT CALLBACK v18] Headless alert presented; waiting for a user event or programmatic dismissal");
        return;
    }
''', '')
edit(ALERT, '''    let btn_refs: Vec<&str> = btn_strings.iter().map(|s| s.as_str()).collect();
    let clicked = window::show_alert_dialog(env, &title_str, &message_str, &btn_refs);''', '''    let btn_refs: Vec<&str> = btn_strings.iter().map(|s| s.as_str()).collect();
    if cfg!(target_os = "ios") || env.options.headless {
        // UIKit show is asynchronous. Keep this alert alive even when its
        // caller releases it immediately after show returns.
        retain(env, this);
        let token = if env.options.headless { 0 } else {
            window::begin_async_alert(env, &title_str, &message_str, &btn_refs)
        };
        {
            let host = env.objc.borrow_mut::<UIAlertViewHostObject>(this);
            host.owns_native_presentation = true;
            host.native_alert_token = token;
            host.native_poll_count = 0;
        }
        let selector = env.objc.lookup_selector("_touchHLE_pollNativeAlert:").unwrap();
        let interval = 1.0f64 / 30.0;
        let timer: id = msg_class![env; NSTimer timerWithTimeInterval:interval
            target:this selector:selector userInfo:nil repeats:true];
        retain(env, timer);
        env.objc.borrow_mut::<UIAlertViewHostObject>(this).native_alert_timer = timer;
        // Guest UIKit callbacks always return on the main run loop, including
        // alerts constructed by a guest worker thread.
        let run_loop: id = msg_class![env; NSRunLoop mainRunLoop];
        let mode = ns_string::get_static_str(env, "NSRunLoopCommonModes");
        let _: () = msg![env; run_loop addTimer:timer forMode:mode];
        log!("[ALERT ASYNC v20] Show returned without a modal wait; token={} buttons={} headless={}",
            token, btn_count, env.options.headless);
        return;
    }
    let clicked = window::show_alert_dialog(env, &title_str, &message_str, &btn_refs);''')
edit(ALERT, '''// One entry point for a native user action, separate from programmatic''', '''// Poll only copied native state; UIKit never calls into guest code directly.
- (())_touchHLE_pollNativeAlert:(id)timer {
    let (token, count) = {
        let host = env.objc.borrow_mut::<UIAlertViewHostObject>(this);
        if !host.visible || host.native_alert_timer != timer { return; }
        host.native_poll_count = host.native_poll_count.saturating_add(1);
        (host.native_alert_token, host.native_poll_count)
    };
    if count == 1 {
        log!("[ALERT ASYNC v20] Guest run loop continues while popup is visible; token={}", token);
    }
    if token == 0 { return; }
    let result = window::poll_async_alert(env, token);
    if result >= 0 {
        let buttons: NSUInteger = msg![env; this numberOfButtons];
        if (result as NSUInteger) < buttons {
            log!("[ALERT ASYNC v20] Delivering selected button {} on guest thread {}", result, env.current_thread);
            let _: () = msg![env; this _touchHLE_userClickedButton:(result as NSInteger)];
        }
    } else if result == -2 {
        // A failed or externally removed presentation is not a user click.
        log!("[ALERT ASYNC v20] Native presentation unavailable; dismissing without a user click");
        let _: () = msg![env; this dismissWithClickedButtonIndex:(-1 as NSInteger) animated:false];
    }
}

// One entry point for a native user action, separate from programmatic''')
edit(ALERT, '''    let owns_loading_presentation = {
        let host = env.objc.borrow_mut::<UIAlertViewHostObject>(this);
        if !host.visible { return; }
        host.visible = false;
        std::mem::take(&mut host.owns_loading_presentation)
    };
    retain(env, this);''', '''    let (owns_loading_presentation, owns_native_presentation, token, timer) = {
        let host = env.objc.borrow_mut::<UIAlertViewHostObject>(this);
        if !host.visible { return; }
        host.visible = false;
        (std::mem::take(&mut host.owns_loading_presentation),
         std::mem::take(&mut host.owns_native_presentation),
         std::mem::take(&mut host.native_alert_token),
         std::mem::replace(&mut host.native_alert_timer, nil))
    };
    retain(env, this);
    // Stop the old timer/UI before callbacks. A callback may reuse this alert
    // and create a new timer/token which must not be canceled here.
    if timer != nil {
        let _: () = msg![env; timer invalidate];
        release(env, timer);
    }
    if token != 0 { window::dismiss_async_alert(env, token); }''')
edit(ALERT, '''    if owns_loading_presentation {
        log!("[ALERT LOADING v19] Loading alert dismissed by the game");
        release(env, this);
    }
    release(env, this);''', '''    if owns_loading_presentation {
        log!("[ALERT LOADING v19] Loading alert dismissed by the game");
        release(env, this);
    }
    if owns_native_presentation {
        log!("[ALERT ASYNC v20] Presentation released and native timer canceled");
        release(env, this);
    }
    release(env, this);''')

window_source = Path('applesauce/src/window.rs')
window_source.write_text(window_source.read_text() + r'''
// V20: iOS guest alerts do not call SDL's synchronous message-box wait.
#[cfg(target_os = "ios")]
extern "C" {
    fn SDL_TOUCHHLE_AlertBeginV20(window: *mut sdl2_sys::SDL_Window,
        title: *const std::os::raw::c_char, message: *const std::os::raw::c_char,
        buttons: *const *const std::os::raw::c_char, count: i32) -> u64;
    fn SDL_TOUCHHLE_AlertPollV20(token: u64) -> i32;
    fn SDL_TOUCHHLE_AlertDismissV20(token: u64);
    fn SDL_TOUCHHLE_AlertResetV20();
}

pub fn begin_async_alert(env: &mut Environment, title: &str, message: &str,
                         buttons: &[&str]) -> u64 {
    #[cfg(target_os = "ios")]
    {
        use std::ffi::CString;
        let title = CString::new(title.replace('\0', "")).unwrap();
        let message = CString::new(message.replace('\0', "")).unwrap();
        let buttons: Vec<CString> = buttons.iter()
            .map(|s| CString::new(s.replace('\0', "")).unwrap()).collect();
        env.on_parent_stack_in_coroutine(move |window, _| {
            let pointers: Vec<_> = buttons.iter().map(|s| s.as_ptr()).collect();
            // SAFETY: called on the native main stack. The bridge copies every
            // string/index synchronously and never stores these pointers.
            unsafe { SDL_TOUCHHLE_AlertBeginV20(window.window.raw(), title.as_ptr(),
                message.as_ptr(), pointers.as_ptr(), pointers.len() as i32) }
        })
    }
    #[cfg(not(target_os = "ios"))]
    { let _ = (env, title, message, buttons); 0 }
}

pub fn poll_async_alert(env: &mut Environment, token: u64) -> i32 {
    #[cfg(target_os = "ios")]
    { env.on_parent_stack_in_coroutine(move |_, _| unsafe { SDL_TOUCHHLE_AlertPollV20(token) }) }
    #[cfg(not(target_os = "ios"))]
    { let _ = (env, token); -1 }
}

pub fn dismiss_async_alert(env: &mut Environment, token: u64) {
    #[cfg(target_os = "ios")]
    { env.on_parent_stack_in_coroutine(move |_, _| unsafe { SDL_TOUCHHLE_AlertDismissV20(token) }); }
    #[cfg(not(target_os = "ios"))]
    { let _ = (env, token); }
}

#[cfg(target_os = "ios")]
pub fn reset_async_alerts() {
    // Called at the native core entry/exit boundary, outside guest coroutines.
    unsafe { SDL_TOUCHHLE_AlertResetV20(); }
}
''')

SDL = 'vendor/rust-sdl2/sdl2-sys/SDL/src/video/uikit/SDL_uikitmessagebox.m'
shutil.copyfile(Path(__file__).with_name('async-alert-uikit-v20.inc'),
                Path('applesauce') / Path(SDL).with_name('SDL_touchhle_asyncalert_v20.inc'))
edit(SDL, '#endif /* SDL_VIDEO_DRIVER_UIKIT */', '''#include "SDL_touchhle_asyncalert_v20.inc"

/* Explicit default visibility: these four entry points live in shared SDL. */
SDL_DECLSPEC uint64_t SDLCALL SDL_TOUCHHLE_AlertBeginV20(SDL_Window *parent,
    const char *title, const char *message, const char *const *buttons, int count)
{
    SDL_WindowData *data = parent ? (__bridge SDL_WindowData *)parent->driverdata : nil;
    return TouchHLE_BeginAsyncAlertV20(data.uiwindow, title, message, buttons, count);
}
SDL_DECLSPEC int SDLCALL SDL_TOUCHHLE_AlertPollV20(uint64_t token)
{ return TouchHLE_PollAsyncAlertV20(token); }
SDL_DECLSPEC void SDLCALL SDL_TOUCHHLE_AlertDismissV20(uint64_t token)
{ TouchHLE_DismissAsyncAlertV20(token); }
SDL_DECLSPEC void SDLCALL SDL_TOUCHHLE_AlertResetV20(void)
{ TouchHLE_ResetAsyncAlertsV20(); }

#endif /* SDL_VIDEO_DRIVER_UIKIT */''')
edit('src/lib.rs', 'pub fn clear_host_exit_request() {', '''#[cfg(target_os = "ios")]
pub fn reset_native_host_alerts() {
    window::reset_async_alerts();
}

pub fn clear_host_exit_request() {''')
edit('platform/ios/rust-entry/src/lib.rs', '''    touchHLE::clear_host_exit_request();''', '''    touchHLE::reset_native_host_alerts();
    touchHLE::clear_host_exit_request();''')
edit('platform/ios/rust-entry/src/lib.rs', '''    match outcome {''', '''    touchHLE::reset_native_host_alerts();
    match outcome {''')

print('Applied V20 async iOS button-alert bridge; V18 callbacks/V19 loading fix retained.')
