mod commands;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Load .env from the directory next to the executable (works both in dev and release)
    let env_path = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.join(".env")));
    if let Some(path) = env_path {
        dotenvy::from_path(path).ok();
    }
    // Also try CWD (convenient during `cargo tauri dev`)
    dotenvy::dotenv().ok();

    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            commands::memory::read_memory_context,
            commands::memory::list_docs,
            commands::memory::read_doc,
            commands::memory::read_staging,
            commands::memory::delete_staging,
            commands::memory::debug_memory,
            commands::groq::transcribe_audio,
            commands::claude::ask_claude,
            commands::tts::synthesize_speech,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
