// Private, executable-guarded Order Up!! 1.41 DLC installer.
// Source assets belong to the user and are not included in the source repo.
// No Chef/Common WAD, saves, purchases, hiring rules or currency are modified.
use crate::fs::{Fs, GuestPathBuf};
use crate::objc::{id, Class, SEL};
use crate::Environment;
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::io::{Cursor, Read};

const PACK_NAME: &str = "OrderUpDLC-1.41-v22.zip";
const PACK_SHA256: &str = "a69882d58ae513c96f6b48b182e6ba90a4b9e4a9a16ed637736c60462bbfeef1";
const EXECUTABLE_SHA256: &str = "6fd26085f17563cf31617cc0cff3a72d8c3ebb7db31a41127832fb35bbda9063";
const MAX_PACK: usize = 15_000_000;
const MAX_UNPACKED: u64 = 31_000_000;
const MAX_ENTRY: u64 = 8_000_000;

struct Package {
    name: &'static str,
    wad: &'static str,
    marker: &'static str,
    size: u64,
    hash: &'static str,
}

const PACKAGES: &[Package] = &[
    Package { name: "farmers_market", wad: "Marketplace.wad", marker: "farmers_market_extracted_v1_4.svs", size: 7702480, hash: "49add49c653ae231299a4913f9c9bcd099704eb2b6449d11b23c507bde6746ad" },
    Package { name: "crowd_pleaser", wad: "CrowdPleaser.wad", marker: "crowdpleaser_extracted_v1_2.svs", size: 1299536, hash: "456b7c1890b9a4a518609f6d566a638cf1d1bd8a12a9d7313245c47caa0a486a" },
    Package { name: "pushthespecial_guy", wad: "PushSpecial.wad", marker: "pushspecial_extracted_v1_2.svs", size: 1589072, hash: "368d9ee0bd3f7ef159a1eebd3879163ba89ea0f1ab8808164595dd7133e1a253" },
    Package { name: "grill_guy", wad: "GrillGuy.wad", marker: "grillguy_extracted_v1_2.svs", size: 1170640, hash: "45e6d8c45cecb2c4f5e51acbe7841e3d331b4a9e08340d3c245eb05a6faefbfe" },
    Package { name: "knifeskills_guy", wad: "KnifeGuy.wad", marker: "knifeguy_extracted_v1_2.svs", size: 923472, hash: "d43f200ea415c077a20004d8bd7f56dd6e869b01843f7a2ac80a7fe23c1536d4" },
    Package { name: "dough_boy", wad: "DoughBoy.wad", marker: "doughboy_extracted_v1_2.svs", size: 998864, hash: "9f36fa66a722741b65fa097b0ef03861dfc22275a73a434b34e580eeab90cfc4" },
    Package { name: "spice_guy", wad: "SpiceGuy.wad", marker: "spiceguy_extracted_v1_2.svs", size: 1035344, hash: "16531bf985619ae9ce2da70453c62881e7619cf4efc3e5c1164a2a1563792553" },
    Package { name: "precision_guy", wad: "PrecisionGuy.wad", marker: "precision_extracted_v1_2.svs", size: 1268176, hash: "55b76373ca3a3069bb89c12eabf8f6e6747d89064e82bba596e0f2e63e7862a1" },
    Package { name: "speed_guy", wad: "SpeedGuy.wad", marker: "speedguy_extracted_v1_2.svs", size: 1120336, hash: "4ac08e0c35c55c0f556ef885de0f60b6129629308acd664f35d78135a09e816c" },
    Package { name: "espritdecorps_guy", wad: "EspiritGuy.wad", marker: "espirit_extracted_v1_2.svs", size: 1137872, hash: "d74f430a2d8e70d0aca1a430af0f519aea2992cae1661a3425dfe72d4a562dfd" },
    Package { name: "prodigy", wad: "ProdigyGuy.wad", marker: "prodigy_extracted_v1_2.svs", size: 919120, hash: "8e2704c5c3fc4d3e0153c98c4a18708a357d203b9805fad9b6924162647dfb57" },
    Package { name: "monkey", wad: "Monkey.wad", marker: "monkey_extracted_v1_2.svs", size: 561104, hash: "19a0aa58e42d4d34d7091c6d8a7bb2b20b0989d922557d8a8bce14721fd436b7" },
];

struct Asset {
    name: String,
    bytes: Vec<u8>,
    hash: String,
    original_hash: Option<String>,
}

fn digest(bytes: &[u8]) -> String { format!("{:x}", Sha256::digest(bytes)) }

fn safe_asset_name(name: &str) -> bool {
    let allowed = PACKAGES.iter().any(|p| p.wad == name)
        || name == "streams/bgm_farmers_market.stm.iph.caf"
        || name.starts_with("streams/vo/en/peds/ped_farmersmarketguy/")
        || name.starts_with("streams/vo/en/assistants/");
    allowed && !name.contains(['\\', '\0', ':'])
        && name.split('/').all(|p| !matches!(p, "" | "." | ".."))
        && (name.ends_with(".wad") || name.ends_with(".stm.iph.caf"))
}

fn should_replace(current: Option<&str>, expected: &str, original: Option<&str>) -> bool {
    current.is_none_or(|hash| hash != expected && Some(hash) != original)
}

fn decode_checked(bytes: Vec<u8>, expected_hash: &str) -> Result<Vec<Asset>, String> {
    if bytes.len() > MAX_PACK || digest(&bytes) != expected_hash {
        return Err("unrecognized or damaged 1.41 DLC pack; cache untouched".into());
    }
    let mut zip = zip::ZipArchive::new(Cursor::new(bytes)).map_err(|e| e.to_string())?;
    if zip.len() != 690 { return Err("DLC file count mismatch".into()); }
    let mut names = HashSet::new();
    for index in 0..zip.len() {
        let file = zip.by_index(index).map_err(|e| e.to_string())?;
        if !names.insert(file.name().to_string()) { return Err("duplicate DLC zip entry".into()); }
    }
    let mut manifest_bytes = Vec::new();
    {
        let file = zip.by_name("manifest.json").map_err(|e| e.to_string())?;
        if file.size() > 300_000 { return Err("oversized DLC manifest".into()); }
        file.take(300_001).read_to_end(&mut manifest_bytes).map_err(|e| e.to_string())?;
    }
    let manifest: serde_json::Value = serde_json::from_slice(&manifest_bytes).map_err(|e| e.to_string())?;
    if manifest["format"] != 22 || manifest["target_version"] != "1.41"
        || manifest["source_version"] != "1.62"
        || manifest["target_executable_sha256"] != EXECUTABLE_SHA256 {
        return Err("DLC manifest target mismatch".into());
    }
    let rows = manifest["files"].as_array().ok_or("missing DLC asset list")?;
    if rows.len() != 689 { return Err("incomplete DLC asset list".into()); }
    let mut listed = HashSet::from(["manifest.json".to_string()]);
    let mut total = 0u64;
    let mut assets = Vec::new();
    for row in rows {
        let name = row["name"].as_str().ok_or("missing DLC asset name")?;
        let size = row["size"].as_u64().ok_or("missing DLC asset size")?;
        let hash = row["sha256"].as_str().ok_or("missing DLC asset digest")?;
        if !safe_asset_name(name) || !listed.insert(name.to_string()) || size == 0 || size > MAX_ENTRY {
            return Err("unsafe or repeated DLC asset".into());
        }
        total = total.checked_add(size).filter(|&n| n <= MAX_UNPACKED).ok_or("DLC size limit")?;
        let file = zip.by_name(name).map_err(|e| e.to_string())?;
        if file.size() != size { return Err("DLC entry size mismatch".into()); }
        let mut data = Vec::with_capacity(size as usize);
        file.take(size + 1).read_to_end(&mut data).map_err(|e| e.to_string())?;
        if data.len() as u64 != size || digest(&data) != hash { return Err("DLC asset digest mismatch".into()); }
        assets.push(Asset { name: name.into(), bytes: data, hash: hash.into(),
            original_hash: row["original_sha256"].as_str().map(str::to_string) });
    }
    if listed != names { return Err("unlisted DLC entry".into()); }
    let by_name: HashMap<_, _> = assets.iter().map(|a| (a.name.as_str(), a)).collect();
    for package in PACKAGES {
        let asset = by_name.get(package.wad).ok_or("DLC model missing")?;
        if asset.bytes.len() as u64 != package.size || asset.hash != package.hash {
            return Err("DLC model verification failed".into());
        }
    }
    Ok(assets)
}

fn find_pack(fs: &Fs) -> Result<Option<Vec<u8>>, String> {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            let path = parent.join(PACK_NAME);
            if path.is_file() {
                if std::fs::metadata(&path).map_err(|e| e.to_string())?.len() > MAX_PACK as u64 {
                    return Err("oversized native DLC pack".into());
                }
                return std::fs::read(path).map(Some).map_err(|e| e.to_string());
            }
        }
    }
    let path = fs.home_directory().join(&format!("Documents/{}", PACK_NAME));
    if !fs.is_file(&path) { return Ok(None); }
    if fs.size(&path).map_err(|_| "cannot stat DLC pack")? > MAX_PACK as u64 {
        return Err("oversized guest DLC pack".into());
    }
    fs.read(path).map(Some).map_err(|_| "cannot read DLC pack".into())
}

pub(crate) fn validate_pack_file(path: &str) -> Result<String, String> {
    if std::fs::metadata(path).map_err(|e| e.to_string())?.len() > MAX_PACK as u64 {
        return Err("oversized DLC pack".into());
    }
    let assets = decode_checked(std::fs::read(path).map_err(|e| e.to_string())?, PACK_SHA256)?;
    Ok(format!("[ORDER UP DLC v22] Validated {} private assets for 1.41: Farmers Market and 11 assistants; no filesystem or save changes", assets.len()))
}

fn rollback(fs: &mut Fs, changes: &[(GuestPathBuf, Option<GuestPathBuf>)]) {
    for (destination, backup) in changes.iter().rev() {
        let _ = fs.remove(destination);
        if let Some(backup) = backup { let _ = fs.rename(backup.as_ref(), destination.as_ref()); }
    }
}

fn install(fs: &mut Fs, assets: &[Asset]) -> Result<(), String> {
    let cache = fs.home_directory().join("Library/Caches");
    let stage = fs.home_directory().join("tmp/orderup-dlc-v22");
    fs.create_dir_all(&cache).map_err(|_| "cannot create DLC cache")?;
    fs.create_dir_all(&stage).map_err(|_| "cannot create DLC staging")?;
    let mut staged = Vec::new();
    let mut retained = 0usize;
    for asset in assets {
        let destination = cache.join(&asset.name);
        let current = fs.read(&destination).ok().map(|bytes| digest(&bytes));
        if !should_replace(current.as_deref(), &asset.hash, asset.original_hash.as_deref()) {
            retained += 1;
            continue;
        }
        let temp = stage.join(&asset.name);
        fs.create_dir_all(temp.parent().ok_or("invalid staged DLC path")?).map_err(|_| "cannot stage DLC directory")?;
        fs.write(&temp, &asset.bytes).map_err(|_| "cannot stage DLC asset")?;
        if digest(&fs.read(&temp).map_err(|_| "cannot reread staged DLC")?) != asset.hash {
            return Err("staged DLC verification failed; no completion indicators written".into());
        }
        staged.push((temp, destination, current));
    }
    let mut changes = Vec::new();
    let result: Result<(), String> = (|| {
        for (temp, destination, old_hash) in &staged {
            fs.create_dir_all(destination.parent().ok_or("invalid DLC destination")?).map_err(|_| "cannot create DLC destination")?;
            let backup = if let Some(hash) = old_hash {
                let base = format!("{}.v22-backup-{}", destination.as_str(), &hash[..16]);
                let backup = (0..1024).map(|n| GuestPathBuf::from(format!("{}-{}", base, n)))
                    .find(|p| !fs.exists(p)).ok_or("DLC backup limit")?;
                fs.rename(destination.as_ref(), backup.as_ref()).map_err(|_| "cannot preserve old DLC")?;
                Some(backup)
            } else { None };
            if fs.rename(temp.as_ref(), destination.as_ref()).is_err() {
                if let Some(backup) = &backup { let _ = fs.rename(backup.as_ref(), destination.as_ref()); }
                return Err("cannot publish DLC asset".into());
            }
            changes.push((destination.clone(), backup));
        }
        // Recheck all 689 published/retained assets, including every audio file,
        // BEFORE publishing the game's genuine package-completion indicators.
        for asset in assets {
            let hash = digest(&fs.read(cache.join(&asset.name)).map_err(|_| "published DLC missing")?);
            if hash != asset.hash && Some(&hash) != asset.original_hash.as_ref() {
                return Err("published DLC digest mismatch".into());
            }
        }
        for package in PACKAGES {
            let destination = cache.join(package.marker);
            if fs.is_file(&destination) { continue; }
            let temp = stage.join(package.marker);
            fs.write(&temp, b"Verified private Order Up 1.41 DLC assets v22\n").map_err(|_| "cannot stage DLC indicator")?;
            fs.rename(temp.as_ref(), destination.as_ref()).map_err(|_| "cannot publish DLC indicator")?;
            changes.push((destination, None));
        }
        Ok(())
    })();
    if let Err(error) = result {
        rollback(fs, &changes);
        return Err(format!("{}; DLC publication rolled back, saves untouched", error));
    }
    log!("[ORDER UP DLC v22] Verified {} assets; published {}, retained {}; Farmers Market and 11 assistants installed; Chef/Common/save/purchases untouched",
        assets.len(), staged.len(), retained);
    Ok(())
}

pub(crate) fn prepare(env: &mut Environment) {
    if env.bundle.bundle_identifier() != "com.chillingo.orderup" || env.bundle.bundle_version() != "1.41" {
        return;
    }
    if !env.fs.read(env.bundle.executable_path()).is_ok_and(|bytes| digest(&bytes) == EXECUTABLE_SHA256) {
        log!("[ORDER UP DLC v22] Different 1.41 executable; private DLC preparation skipped");
        return;
    }
    let result = (|| {
        let Some(pack) = find_pack(&env.fs)? else { return Ok(false); };
        let assets = decode_checked(pack, PACK_SHA256)?;
        install(&mut env.fs, &assets)?;
        Ok::<bool, String>(true)
    })();
    match result {
        Ok(ready) => {
            env.libc_state.order_up.v141_dlc_ready = ready;
            if !ready { log!("[ORDER UP DLC v22] No private pack; no completed downloads claimed"); }
        }
        Err(error) => log!("[ORDER UP DLC v22] Preparation skipped: {}", error),
    }
}

fn package_ready(fs: &Fs, package: &Package) -> bool {
    let cache = fs.home_directory().join("Library/Caches");
    fs.is_file(&cache.join(package.marker))
        && fs.size(&cache.join(package.wad)) == Ok(package.size)
        && fs.read(cache.join(package.wad)).is_ok_and(|data| digest(&data) == package.hash)
}

pub(crate) fn interpose(env: &mut Environment, selector: SEL, class: Class) -> bool {
    if !env.libc_state.order_up.v141_dlc_ready || env.objc.get_class_name(class) != "ChefDownloadManager" {
        return false;
    }
    let selector = selector.as_str(&env.mem).to_string();
    if !matches!(selector.as_str(), "checkPackageDownloaded:" | "checkCompletePackageDownloaded:version:") {
        return false;
    }
    // Support the known dictionary revision 1 only, as in the original DLC
    // checks. Different requests retain the game's original version check.
    if selector == "checkCompletePackageDownloaded:version:" && env.cpu.regs()[3] != 1 {
        log_once!("[ORDER UP DLC v22] Unrecognized requested package revision; original check retained");
        return false;
    }
    let name: id = crate::mem::MutPtr::from_bits(env.cpu.regs()[2]);
    if name == crate::objc::nil { return false; }
    let name = crate::frameworks::foundation::ns_string::to_rust_string(env, name).into_owned();
    let Some(package) = PACKAGES.iter().find(|p| p.name == name) else { return false; };
    if !package_ready(&env.fs, package) { return false; }
    log_once!("[ORDER UP DLC v22] Using verified private local DLC instead of unavailable legacy download metadata");
    env.cpu.regs_mut()[0] = 1;
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn forbids_base_game_save_and_unsafe_paths() {
        for name in ["Chef.wad", "Common.wad", "Save00.bin", "DataStore", "Diner.wad",
                     "Marketplace.wad/../save.bin", "streams/vo/en/assistants/../save.stm.iph.caf",
                     "/Marketplace.wad", "streams/vo/en/assistants/a\\b.stm.iph.caf", "streams//x.stm.iph.caf"] {
            assert!(!safe_asset_name(name), "{}", name);
        }
        for name in ["Marketplace.wad", "KnifeGuy.wad", "streams/bgm_farmers_market.stm.iph.caf",
                     "streams/vo/en/assistants/ac_monkey/test.stm.iph.caf"] { assert!(safe_asset_name(name)); }
    }
    #[test]
    fn preserves_existing_original_and_verified_assets() {
        assert!(!should_replace(Some("original"), "new", Some("original")));
        assert!(!should_replace(Some("new"), "new", None));
        assert!(should_replace(Some("damaged"), "new", None));
        assert!(should_replace(None, "new", None));
    }
    #[test]
    fn rejects_unknown_and_truncated_pack_before_writes() {
        for bytes in [vec![], b"PK\x03\x04".to_vec(), b"unverified map".to_vec()] {
            assert!(decode_checked(bytes, PACK_SHA256).is_err());
        }
    }
    #[test]
    fn package_scope_is_market_and_eleven_missing_assistants() {
        assert_eq!(PACKAGES.len(), 12);
        assert_eq!(PACKAGES.iter().filter(|p| p.wad == "Marketplace.wad").count(), 1);
        assert!(!PACKAGES.iter().any(|p| p.name == "fry_guy" || p.name == "diner" || p.name == "common"));
        assert_eq!(PACKAGES.iter().map(|p| p.marker).collect::<HashSet<_>>().len(), 12);
    }
}
