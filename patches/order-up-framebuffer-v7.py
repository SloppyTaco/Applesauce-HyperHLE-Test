from pathlib import Path

source = Path("applesauce/src/frameworks/opengles/eagl.rs")
text = source.read_text()

needle = '''    let use_ios_es2_direct_path = cfg!(target_os = "ios")
'''

insert = '''    // Order Up!! v1.0 V7 diagnostic: by this point the app has selected the
    // renderbuffer it wants to present. Sample that exact renderbuffer on a
    // few frames without changing the normal presentation path. This tells us
    // whether the guest is genuinely producing black pixels or whether a real
    // image exists but is being lost later in Core Animation/composition.
    if env.bundle.bundle_identifier() == "com.chillingo.orderup" {
        use std::sync::atomic::{AtomicU64, Ordering};
        static ORDER_UP_PRESENT_SAMPLES: AtomicU64 = AtomicU64::new(0);
        let frame = ORDER_UP_PRESENT_SAMPLES.fetch_add(1, Ordering::Relaxed) + 1;

        if matches!(frame, 1 | 2 | 10 | 30 | 60 | 120) {
            let sample = {
                let maybe_gles = super::sync_context(
                    &mut env.framework_state.opengles,
                    &mut env.objc,
                    env.window.as_mut().unwrap(),
                    env.current_thread,
                );

                match maybe_gles {
                    Some(mut gles) => {
                        let mut framebuffer_binding: GLint = 0;
                        let mut renderbuffer_binding: GLint = 0;
                        unsafe {
                            gles.GetIntegerv(
                                gles11::FRAMEBUFFER_BINDING_OES,
                                &mut framebuffer_binding,
                            );
                            gles.GetIntegerv(
                                gles11::RENDERBUFFER_BINDING_OES,
                                &mut renderbuffer_binding,
                            );
                        }

                        let (pixels, width, height) = unsafe {
                            read_renderbuffer(gles.as_mut(), renderbuffer, Vec::new())
                        };
                        let rgb_max = pixels
                            .chunks_exact(4)
                            .flat_map(|pixel| pixel[..3].iter())
                            .copied()
                            .max()
                            .unwrap_or(0);
                        let nonblack_pixels = pixels
                            .chunks_exact(4)
                            .filter(|pixel| pixel[0] != 0 || pixel[1] != 0 || pixel[2] != 0)
                            .count();
                        let alpha_max = pixels
                            .chunks_exact(4)
                            .map(|pixel| pixel[3])
                            .max()
                            .unwrap_or(0);

                        Some((
                            width,
                            height,
                            rgb_max,
                            nonblack_pixels,
                            alpha_max,
                            framebuffer_binding,
                            renderbuffer_binding,
                        ))
                    }
                    None => None,
                }
            };

            match sample {
                Some((
                    width,
                    height,
                    rgb_max,
                    nonblack_pixels,
                    alpha_max,
                    framebuffer_binding,
                    renderbuffer_binding,
                )) => {
                    log!(
                        "[ORDER UP TRACE v7] source frame={} present_rb={} current_rb={} current_fb={} size={}x{} rgb_max={} nonblack_pixels={} alpha_max={}",
                        frame,
                        renderbuffer,
                        renderbuffer_binding,
                        framebuffer_binding,
                        width,
                        height,
                        rgb_max,
                        nonblack_pixels,
                        alpha_max,
                    );
                }
                None => {
                    log!(
                        "[ORDER UP TRACE v7] source frame={} could not sample: no current GL context",
                        frame
                    );
                }
            }
        }
    }

    let use_ios_es2_direct_path = cfg!(target_os = "ios")
'''

if needle not in text:
    raise SystemExit("V7 patch failed: expected iOS ES2 present-path anchor was not found")

text = text.replace(needle, insert, 1)
source.write_text(text)
print("Applied Order Up framebuffer source diagnostic v7")
