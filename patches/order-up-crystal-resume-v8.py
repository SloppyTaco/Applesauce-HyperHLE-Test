from pathlib import Path

source = Path("applesauce/src/objc/messages.rs")
text = source.read_text()

# messages.rs already re-exports msg and msg_class in this module. Importing
# them again from super causes Rust E0252 duplicate macro definitions.

old = '''        if selector_name == "activateCrystalUI"
            && env.objc.get_class_name(receiver) == "CrystalSession"
        {
            log_once!(
                "[ORDER UP FIX v5] Suppressing obsolete Crystal full-screen UI activation."
            );
            env.cpu.regs_mut()[0..2].fill(0);
            return;
        }
'''

new = '''        if selector_name == "activateCrystalUI"
            && env.objc.get_class_name(receiver) == "CrystalSession"
        {
            log_once!(
                "[ORDER UP FIX v8] Suppressing obsolete Crystal full-screen UI activation and simulating immediate dismissal."
            );

            // Order Up pauses its game/audio immediately before asking Crystal
            // to open.  Simply swallowing activateCrystalUI leaves the game in
            // that paused state forever.  Real Crystal later tells the app
            // delegate that its UI was dismissed; synthesize that callback so
            // Order Up follows its normal resume path without ever showing the
            // obsolete Crystal overlay.
            let application: id = msg_class![env; UIApplication sharedApplication];
            let delegate: id = msg![env; application delegate];
            if delegate != nil {
                log!(
                    "[ORDER UP FIX v8] Delivering synthetic crystalUiDeactivated to {:?} ({}).",
                    delegate,
                    env.objc.get_class_name(delegate)
                );
                let _: () = msg![env; delegate crystalUiDeactivated];
                log!("[ORDER UP FIX v8] Synthetic crystalUiDeactivated returned.");
            } else {
                log!("[ORDER UP FIX v8] UIApplication delegate is nil; cannot synthesize Crystal dismissal.");
            }

            env.cpu.regs_mut()[0..2].fill(0);
            return;
        }
'''

if old not in text:
    raise SystemExit("V8 patch failed: expected V5 activateCrystalUI block not found")
text = text.replace(old, new, 1)
source.write_text(text)
print("Applied Order Up Crystal dismissal/resume fix v8")
