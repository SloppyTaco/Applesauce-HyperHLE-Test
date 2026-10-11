"""Keep UIApplicationMain alive after a temporary CFRunLoopStop activation.

This is a UIKit lifecycle correction, not an exit/abort bypass. Genuine guest
exit still terminates, with a stack trace on nonzero status for diagnosis.
All V18-V20 alert, content and original-game recovery code is unchanged.
"""
from pathlib import Path


def replace_once(path, before, after):
    original = path.read_text()
    assert original.count(before) == 1, f'Unexpected source for {path}'
    path.write_text(original.replace(before, after, 1))


replace_once(Path('applesauce/src/frameworks/uikit/ui_application.rs'),
    '''    let run_loop: id = msg_class![env; NSRunLoop mainRunLoop];
    let _: () = msg![env; run_loop run];
}

pub(super) fn exit''',
    '''    let run_loop: id = msg_class![env; NSRunLoop mainRunLoop];
    // UIApplicationMain never returns, even when a guest CFRunLoopStop
    // ends one activation. Returning here leaks the last callback's r0
    // into guest main(), whose startup routine calls exit with that value.
    // Keep CFRunLoopRun/Stop semantics unchanged for their actual callers.
    loop {
        let _: () = msg![env; run_loop run];
        log!(
            "[APPLICATION LOOP v21] Main run-loop activation stopped; \\
             restarting application event processing"
        );
    }
}

pub(super) fn exit''')

replace_once(Path('applesauce/src/libc/stdlib.rs'),
    '''    echo!("App called exit({}); touchHLE will now quit.", exit_code);
    std::process::exit(exit_code);''',
    '''    echo!("App called exit({}); touchHLE will now quit.", exit_code);
    if exit_code != 0 {
        log!(
            "[GUEST EXIT v21] Nonzero guest exit; \\
             recording caller stack without suppressing termination"
        );
        env.stack_trace_current();
    }
    std::process::exit(exit_code);''')

print('V21 UIKit application-loop lifetime correction applied; genuine exit and abort preserved.')
