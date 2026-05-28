mod commands;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Load .env from the directory next to the executable (works in dev and release)
    let env_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join(".env")));
    if let Some(path) = env_path {
        dotenvy::from_path(path).ok();
    }
    dotenvy::dotenv().ok();

    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .manage(commands::window::WindowMode(std::sync::Mutex::new(false)))
        .setup(|app| {
            use tauri::{Emitter, Manager, window::Color};
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.set_background_color(Some(Color(0, 0, 0, 0)));

                #[cfg(target_os = "windows")]
                {
                    use windows::Win32::Foundation::HWND;
                    use windows::Win32::Graphics::Dwm::DwmExtendFrameIntoClientArea;
                    use windows::Win32::UI::Controls::MARGINS;
                    let hwnd = match win.hwnd() {
                        Ok(h)  => HWND(h.0 as _),
                        Err(e) => { eprintln!("[jarvis] DWM setup failed: {:?}", e); return Ok(()); }
                    };
                    let margins = MARGINS { cxLeftWidth: -1, cxRightWidth: -1, cyTopHeight: -1, cyBottomHeight: -1 };
                    unsafe { let _ = DwmExtendFrameIntoClientArea(hwnd, &margins); }
                }
            }
            use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

            let handle = app.handle().clone();
            app.global_shortcut().on_shortcut(
                Shortcut::new(Some(Modifiers::CONTROL), Code::Space),
                move |_app, _shortcut, event| {
                    let name = if event.state == ShortcutState::Pressed {
                        "hotkey-listen-start"
                    } else {
                        "hotkey-listen-stop"
                    };
                    handle.emit(name, ()).ok();
                    eprintln!("[jarvis] global shortcut: {}", name);
                },
            )?;
            eprintln!("[jarvis] global shortcut Ctrl+Space enregistré");
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::memory::read_memory_context,
            commands::memory::list_docs,
            commands::memory::read_doc,
            commands::memory::fetch_staging,
            commands::memory::read_staging,
            commands::memory::delete_staging,
            commands::memory::commit_memory_item,
            commands::memory::confirm_staging_item,
            commands::memory::debug_memory,
            commands::gemini_live::transcribe_gemini,
            commands::claude::ask_claude,
            commands::gemini_tts::synthesize_speech,
            commands::widgets::read_widgets_context,
            commands::window::set_window_compact,
            commands::window::set_window_extended,
            commands::window::toggle_window_mode,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
