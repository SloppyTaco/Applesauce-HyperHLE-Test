"""V18: faithful alert dismissal and verified, private offline restaurant data.

Applied after the complete V17 chain. No game payload is stored in this repo.
The user-specific content pack is added only to the final private IPA.
"""
from pathlib import Path


def edit(path,old,new):
    source=Path('applesauce')/path
    text=source.read_text()
    if text.count(old)!=1:
        raise SystemExit(f'V18 patch failed: missing or ambiguous anchor in {path}')
    source.write_text(text.replace(old,new,1))


# The original 1.0 ChefDownloadManager callback at 0x1b567c explicitly
# dismisses the alert again, including on the Yes path at 0x1b5720.
# Programmatic dismissal must NOT synthesize another button click.
edit('src/frameworks/uikit/ui_view/ui_alert_view.rs',
     '    let _: () = msg![env; this dismissWithClickedButtonIndex:dismiss_index animated:false];\n}\n\n- (())dismissWithClickedButtonIndex:',
     '''    let _: () = msg![env; this _touchHLE_userClickedButton:dismiss_index];
}

// One entry point for a native user action, separate from programmatic
// dismissal. Headless regression guests can deliver the same event here.
- (())_touchHLE_userClickedButton:(NSInteger)dismiss_index {
    if !env.objc.borrow::<UIAlertViewHostObject>(this).visible { return; }
    // Hold the alert across the native UI and guest callback. The delegate
    // may release its ownership or call dismiss again while handling the tap.
    retain(env, this);
    let delegate = env.objc.borrow::<UIAlertViewHostObject>(this).delegate;
    log!("[ALERT CALLBACK v18] Native button {} returned; dispatching one user click", dismiss_index);
    if delegate != nil && env.mem.read::<u32>(delegate.cast()) != 0 {
        retain(env, delegate);
        if let Some(sel) = env.objc.lookup_selector("alertView:clickedButtonAtIndex:") {
            let responds: bool = msg![env; delegate respondsToSelector:sel];
            if responds {
                let _: () = msg![env; delegate alertView:this clickedButtonAtIndex:dismiss_index];
            }
        }
        release(env, delegate);
    }
    // If the callback already dismissed it, the guarded method is a no-op.
    let _: () = msg![env; this dismissWithClickedButtonIndex:dismiss_index animated:false];
    log!("[ALERT CALLBACK v18] User-click callback completed without recursive dismissal");
    release(env, this);
}

- (())dismissWithClickedButtonIndex:''')
edit('src/frameworks/uikit/ui_view/ui_alert_view.rs',
     '''    env.objc.borrow_mut::<UIAlertViewHostObject>(this).visible = false;
    let delegate = env.objc.borrow::<UIAlertViewHostObject>(this).delegate;

    // Честно проверяем, не был ли делегат удален (isa != 0)''',
     '''    // Set hidden BEFORE dispatch. A delegate may re-enter dismissal;
    // UIKit sends will/did-dismiss once, not another clicked-button event.
    if !env.objc.borrow::<UIAlertViewHostObject>(this).visible { return; }
    env.objc.borrow_mut::<UIAlertViewHostObject>(this).visible = false;
    retain(env, this);
    let delegate = env.objc.borrow::<UIAlertViewHostObject>(this).delegate;
    log!("[ALERT CALLBACK v18] Dismiss button {}; no synthetic user click", button_index);

    // Честно проверяем, не был ли делегат удален (isa != 0)''')
edit('src/frameworks/uikit/ui_view/ui_alert_view.rs',
     '''            if let Some(sel) = env.objc.lookup_selector("alertView:clickedButtonAtIndex:") {
                let responds: bool = msg![env; delegate respondsToSelector:sel];
                if responds { let _: () = msg![env; delegate alertView:this clickedButtonAtIndex:button_index]; }
            }
''',
     '            retain(env, delegate);\n')
edit('src/frameworks/uikit/ui_view/ui_alert_view.rs',
     '''                if responds { let _: () = msg![env; delegate alertView:this didDismissWithButtonIndex:button_index]; }
            }
        }
    }
}''',
     '''                if responds { let _: () = msg![env; delegate alertView:this didDismissWithButtonIndex:button_index]; }
            }
            release(env, delegate);
        }
    }
    release(env, this);
}''')
edit('src/frameworks/uikit/ui_view/ui_alert_view.rs',
     '    let title_str: String = if raw_title.is_empty() { "Alert".into() } else { raw_title };\n',
     '''    if env.options.headless {
        log!("[ALERT CALLBACK v18] Headless alert presented; waiting for a user event or programmatic dismissal");
        return;
    }
    let title_str: String = if raw_title.is_empty() { "Alert".into() } else { raw_title };
''')

# SDL must inspect the selected button after a bounded native run-loop turn.
# Do not reset the selection a second time after presenting the controller.
# (The initial sentinel already lives in UIKit_ShowMessageBoxAlertController.)
edit('vendor/rust-sdl2/sdl2-sys/SDL/src/video/uikit/SDL_uikitmessagebox.m',
     '    *clickedindex = messageboxdata->numbuttons;\n\n',
     '    /* Applesauce V18: preserve a selection delivered during presentation. */\n\n')
edit('vendor/rust-sdl2/sdl2-sys/SDL/src/video/uikit/SDL_uikitmessagebox.m',
     'beforeDate:[NSDate distantFuture]',
     'beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.01]')

module=r'''// Private Order Up!! 1.0 offline content. Executable-guarded by order_up.
// The original Chef.wad, save/profile, purchases and currency are untouched.
// These v4 restaurant assets come from the user's supplied 1.62 archive.
use crate::fs::Fs;
use crate::objc::{id, Class, SEL};
use crate::Environment;
use sha2::{Digest, Sha256};
use std::collections::HashSet;
use std::io::{Cursor, Read};

const PACK_NAME: &str = "OrderUpOffline-v18.zip";
const PACK_SHA256: &str = "c8a5c51ecc17200272897b9104b05f7a48f95e712617c9bc212dbe0ee6596a41";
const MAX_PACK: usize = 60_000_000;
const MAX_UNPACKED: u64 = 110_000_000;
const MAX_ENTRY: u64 = 42_000_000;
const DINER_SIZE: u64 = 23_076_128;
const COMMON_SIZE: u64 = 40_776_240;
const DINER_SHA256: &str = "709c7d86e3848cc8c60513b0538b2370beeb2b65fa0f97e6b5d6188f47f0f6ca";
const COMMON_SHA256: &str = "7674242aff7063718b2e74e89d38d4a7a35114a2fedbe1df74db2509286e3115";

struct Asset {
    name: String,
    bytes: Vec<u8>,
    hash: String,
    original_hash: Option<String>,
}

fn digest(bytes: &[u8]) -> String { format!("{:x}", Sha256::digest(bytes)) }

fn safe_asset_name(name: &str) -> bool {
    (matches!(name, "Diner.wad" | "Common.wad") || name.starts_with("streams/"))
        && !name.contains(['\\', '\0', ':'])
        && name.split('/').all(|p| !matches!(p, "" | "." | ".."))
}

fn should_replace(current: Option<&str>, expected: &str, original: Option<&str>) -> bool {
    match current {
        None => true,
        Some(hash) => hash != expected && Some(hash) != original,
    }
}

fn decode_checked(bytes: Vec<u8>, expected_pack: &str) -> Result<Vec<Asset>, String> {
    if bytes.len() > MAX_PACK || digest(&bytes) != expected_pack {
        return Err("unrecognized or damaged offline pack; cache untouched".into());
    }
    let mut zip = zip::ZipArchive::new(Cursor::new(bytes)).map_err(|e| e.to_string())?;
    if zip.len() != 1993 { return Err("offline pack file count mismatch".into()); }
    let mut manifest_bytes = Vec::new();
    {
        let mut file = zip.by_name("manifest.json").map_err(|e| e.to_string())?;
        if file.size() > 500_000 { return Err("oversized manifest".into()); }
        file.read_to_end(&mut manifest_bytes).map_err(|e| e.to_string())?;
    }
    let manifest: serde_json::Value = serde_json::from_slice(&manifest_bytes)
        .map_err(|e| e.to_string())?;
    if manifest["format"] != 1 || manifest["target_version"] != "1.0"
        || manifest["source_version"] != "1.62" {
        return Err("offline manifest version mismatch".into());
    }
    let files = manifest["files"].as_array().ok_or("missing offline asset list")?;
    if files.len() != 1992 { return Err("incomplete offline asset list".into()); }
    let mut names = HashSet::new();
    names.insert("manifest.json".to_string());
    let mut total = 0u64;
    let mut assets = Vec::new();
    for row in files {
        let name = row["name"].as_str().ok_or("missing asset name")?;
        let size = row["size"].as_u64().ok_or("missing asset size")?;
        let hash = row["sha256"].as_str().ok_or("missing asset digest")?;
        if !safe_asset_name(name) || !names.insert(name.to_string()) || size > MAX_ENTRY {
            return Err("unsafe or repeated offline entry".into());
        }
        total = total.checked_add(size).filter(|&t| t <= MAX_UNPACKED)
            .ok_or("offline content exceeds size limit")?;
        let mut file = zip.by_name(name).map_err(|e| e.to_string())?;
        if file.size() != size { return Err(format!("asset size mismatch: {}", name)); }
        let mut data = Vec::with_capacity(size as usize);
        (&mut file).take(size + 1).read_to_end(&mut data).map_err(|e| e.to_string())?;
        if data.len() as u64 != size || digest(&data) != hash {
            return Err(format!("asset digest mismatch: {}", name));
        }
        assets.push(Asset { name: name.into(), bytes: data, hash: hash.into(),
            original_hash: row["original_sha256"].as_str().map(str::to_string) });
    }
    for i in 0..zip.len() {
        let file = zip.by_index(i).map_err(|e| e.to_string())?;
        if !names.contains(file.name()) { return Err("unlisted offline entry".into()); }
    }
    for (name, size, hash) in [("Diner.wad", DINER_SIZE, DINER_SHA256),
                              ("Common.wad", COMMON_SIZE, COMMON_SHA256)] {
        let asset = assets.iter().find(|a| a.name == name).ok_or("restaurant WAD missing")?;
        if asset.bytes.len() as u64 != size || asset.hash != hash {
            return Err("restaurant WAD verification failed".into());
        }
    }
    Ok(assets)
}

fn find_pack(fs: &Fs) -> Result<Option<Vec<u8>>, String> {
    // current_exe is the native host executable, not the emulated Chef binary.
    // AltStore re-signs the final IPA, including this private resource.
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let path = parent.join(PACK_NAME);
            if path.is_file() {
                let size = std::fs::metadata(&path).map_err(|e| e.to_string())?.len();
                if size > MAX_PACK as u64 { return Err("oversized offline pack".into()); }
                return std::fs::read(path).map(Some).map_err(|e| e.to_string());
            }
        }
    }
    // Allows the same V18 binary to accept a replacement exact pack later;
    // there is no need to compile another app just to add its data resource.
    let path = fs.home_directory().join(&format!("Documents/{}", PACK_NAME));
    if fs.is_file(&path) {
        if fs.size(&path).map_err(|_| "offline pack stat failed")? > MAX_PACK as u64 {
            return Err("oversized offline pack".into());
        }
        return fs.read(path).map(Some).map_err(|_| "offline pack read failed".into());
    }
    Ok(None)
}

pub(crate) fn validate_pack_file(path: &str) -> Result<String, String> {
    if std::fs::metadata(path).map_err(|e| e.to_string())?.len() > MAX_PACK as u64 {
        return Err("oversized offline pack".into());
    }
    let bytes = std::fs::read(path).map_err(|e| e.to_string())?;
    let assets = decode_checked(bytes, PACK_SHA256)?;
    Ok(format!("[ORDER UP DOWNLOAD v18] Validated {} private offline assets, Diner.wad and Common.wad; no filesystem or save changes", assets.len()))
}

fn verified_wads(fs: &Fs) -> bool {
    let cache = fs.home_directory().join("Library/Caches");
    [("Diner.wad", DINER_SHA256), ("Common.wad", COMMON_SHA256)].iter().all(|(name, hash)| {
        fs.read(cache.join(name)).is_ok_and(|b| digest(&b) == *hash)
    })
}

pub(crate) fn installed(fs: &Fs) -> bool {
    let cache = fs.home_directory().join("Library/Caches");
    fs.size(cache.join("Diner.wad")) == Ok(DINER_SIZE)
        && fs.size(cache.join("Common.wad")) == Ok(COMMON_SIZE)
        && fs.is_file(&cache.join("diner_extracted_v1b.svs"))
        && fs.is_file(&cache.join("common_extracted_v1b.svs"))
}

fn rollback(fs: &mut Fs, changes: &[(crate::fs::GuestPathBuf, Option<crate::fs::GuestPathBuf>)]) {
    for (destination, backup) in changes.iter().rev() {
        let _ = fs.remove(destination);
        if let Some(backup) = backup {
            let _ = fs.rename(backup.as_ref(), destination.as_ref());
        }
    }
}

pub(crate) fn prepare(fs: &mut Fs) -> Result<bool, String> {
    let Some(pack) = find_pack(fs)? else {
        log!("[ORDER UP DOWNLOAD v18] No private offline pack; not claiming a completed download");
        return Ok(false);
    };
    let assets = decode_checked(pack, PACK_SHA256)?;
    let cache = fs.home_directory().join("Library/Caches");
    let staging = fs.home_directory().join("tmp/orderup-download-v18");
    fs.create_dir_all(&cache).map_err(|_| "cannot create cache directory")?;
    fs.create_dir_all(&staging).map_err(|_| "cannot create staging directory")?;
    let mut staged = Vec::new();
    let mut retained = 0usize;
    for asset in &assets {
        let destination = cache.join(&asset.name);
        let current = fs.read(&destination).ok().map(|b| digest(&b));
        if !should_replace(current.as_deref(), &asset.hash, asset.original_hash.as_deref()) {
            retained += 1;
            continue;
        }
        let temp = staging.join(&asset.name);
        fs.create_dir_all(temp.parent().ok_or("invalid asset parent")?)
            .map_err(|_| "cannot create staging path")?;
        fs.write(&temp, &asset.bytes).map_err(|_| "cannot stage offline content")?;
        if digest(&fs.read(&temp).map_err(|_| "cannot verify staged content")?) != asset.hash {
            return Err("staged content failed verification; no completion markers written".into());
        }
        staged.push((temp, destination, current));
    }
    let mut changes = Vec::new();
    let publish: Result<(), String> = (|| {
        for (temp, destination, old_hash) in &staged {
            fs.create_dir_all(destination.parent().ok_or("invalid cache asset path")?)
                .map_err(|_| "cannot create cache asset path")?;
            let backup = if let Some(hash) = old_hash {
                let base = format!("{}.v18-backup-{}", destination.as_str(), &hash[..16]);
                let backup = (0..1024).map(|n| crate::fs::GuestPathBuf::from(format!("{}-{}", base, n)))
                    .find(|p| !fs.exists(p)).ok_or("offline backup name limit")?;
                fs.rename(destination.as_ref(), backup.as_ref()).map_err(|_| "cannot preserve old cached content")?;
                Some(backup)
            } else { None };
            if fs.rename(temp.as_ref(), destination.as_ref()).is_err() {
                if let Some(backup) = &backup { let _ = fs.rename(backup.as_ref(), destination.as_ref()); }
                return Err("offline content publication failed".into());
            }
            changes.push((destination.clone(), backup));
        }
        if !verified_wads(fs) { return Err("published restaurant content failed verification".into()); }
        // These two names are the ORIGINAL download-completion indicators,
        // not game saves. Publish them only after every asset is verified.
        for name in ["common_extracted_v1b.svs", "diner_extracted_v1b.svs"] {
            let destination = cache.join(name);
            if fs.is_file(&destination) { continue; }
            let temp = staging.join(name);
            fs.write(&temp, b"OrderUp offline content v18: verified private asset pack\n")
                .map_err(|_| "cannot stage completion indicator")?;
            fs.rename(temp.as_ref(), destination.as_ref()).map_err(|_| "cannot publish completion indicator")?;
            changes.push((destination, None));
        }
        Ok(())
    })();
    if let Err(error) = publish {
        rollback(fs, &changes);
        return Err(format!("{}; cached files rolled back, no save edits", error));
    }
    log!("[ORDER UP DOWNLOAD v18] Verified {} offline assets from supplied 1.62 content; published {}, retained {} existing/original assets; original Chef.wad and saves untouched",
        assets.len(), staged.len(), retained);
    Ok(installed(fs))
}

pub(crate) fn interpose(env: &mut Environment, selector: SEL, class: Class) -> bool {
    let sel = selector.as_str(&env.mem).to_string();
    if !matches!(sel.as_str(), "checkCompletePackageDownloaded:version:" | "checkPackageDownloaded:")
        || !env.libc_state.order_up.offline_diner_ready
        || env.objc.get_class_name(class) != "ChefDownloadManager"
        || crate::order_up::matching_slide(env).is_none() || !installed(&env.fs) {
        return false;
    }
    let versioned = sel == "checkCompletePackageDownloaded:version:";
    if versioned && env.cpu.regs()[3] != 1 { return false; }
    let name: id = crate::mem::MutPtr::from_bits(env.cpu.regs()[2]);
    if name == crate::objc::nil { return false; }
    let name = crate::frameworks::foundation::ns_string::to_rust_string(env, name).into_owned();
    if !matches!(name.as_str(), "diner" | "common") { return false; }
    // The guest checks the obsolete remote DLC dictionary before looking at
    // files. Only these two verified local packages get the installed result.
    // All other restaurants, purchase checks and network requests stay native.
    log_once!("[ORDER UP DOWNLOAD v18] Using verified local Diner/Common content instead of the legacy remote package dictionary");
    env.cpu.regs_mut()[0] = 1;
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn rejects_save_and_path_traversal_entries() {
        for name in ["Chef.wad", "profile.svs", "../Diner.wad", "/Diner.wad", "streams/../save.svs",
                     "streams/a\\b", "streams//a", "streams/a\0b", "streams/a:b"] {
            assert!(!safe_asset_name(name), "{}", name);
        }
        for name in ["Diner.wad", "Common.wad", "streams/vo/en/peds/diner.caf"] {
            assert!(safe_asset_name(name));
        }
    }
    #[test]
    fn retains_verified_original_streams_and_current_content() {
        assert!(!should_replace(Some("v1"), "v162", Some("v1")));
        assert!(!should_replace(Some("v162"), "v162", Some("v1")));
        assert!(should_replace(None, "v162", Some("v1")));
        assert!(should_replace(Some("damaged"), "v162", Some("v1")));
    }
    #[test]
    fn never_accepts_unknown_or_truncated_content() {
        for bytes in [vec![], b"PK\x03\x04".to_vec(), b"not the supplied archive".to_vec()] {
            assert!(decode_checked(bytes, PACK_SHA256).is_err());
        }
    }
    #[test]
    fn rejects_incomplete_zip_even_with_matching_digest() {
        let bytes = b"PK\x05\x06\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0".to_vec();
        let hash = digest(&bytes);
        assert!(decode_checked(bytes, &hash).is_err());
    }
}
'''
target=Path('applesauce/src/order_up_download.rs')
if target.exists(): raise SystemExit('V18 module already exists')
target.write_text(module)
edit('src/lib.rs','mod order_up_cache;\n','mod order_up_cache;\nmod order_up_download;\n')
edit('src/lib.rs',
     '''        } else if arg == "--info" {
            just_info = true;
''',
     '''        } else if let Some(path) = arg.strip_prefix("--check-order-up-offline-pack=") {
            echo!("{}", crate::order_up_download::validate_pack_file(path)?);
            return Ok(());
        } else if arg == "--info" {
            just_info = true;
''')
edit('src/order_up.rs','    checked: bool,\n','    pub(crate) offline_diner_ready: bool,\n    checked: bool,\n')
edit('src/order_up.rs',
     '    const SYMBOLS: [&str; 2] = [\n',
     '''    env.libc_state.order_up.offline_diner_ready = match crate::order_up_download::prepare(&mut env.fs) {
        Ok(ready) => ready,
        Err(error) => {
            log!("[ORDER UP DOWNLOAD v18] Offline preparation skipped: {}", error);
            false
        }
    };
    const SYMBOLS: [&str; 2] = [
''')
edit('src/objc/messages.rs',
     '    // ULTRAHLE_MINIONJUMP_TAP_BRIDGE_BEGIN\n',
     '''    if super2.is_none() && crate::order_up_download::interpose(env, selector, orig_class) {
        return;
    }

    // ULTRAHLE_MINIONJUMP_TAP_BRIDGE_BEGIN
''')
