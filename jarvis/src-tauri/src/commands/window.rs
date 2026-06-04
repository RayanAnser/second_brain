use tauri::{LogicalSize, window::Color};

const COMPACT_W: f64 = 200.0;
const COMPACT_H: f64 = 200.0;
const EXTENDED_W: f64 = 1200.0;
const EXTENDED_H: f64 = 800.0;

pub struct WindowMode(pub std::sync::Mutex<bool>); // true = compact

#[tauri::command]
pub fn set_window_compact(window: tauri::WebviewWindow) -> Result<(), String> {
    window.set_size(LogicalSize::new(COMPACT_W, COMPACT_H)).map_err(|e| e.to_string())?;
    window.set_always_on_top(true).map_err(|e| e.to_string())?;
    window.set_background_color(Some(Color(0, 0, 0, 0))).map_err(|e| e.to_string())?;
    window.set_shadow(false).map_err(|e| e.to_string())?;
    eprintln!("[jarvis] window: compact mode ({}×{})", COMPACT_W, COMPACT_H);
    Ok(())
}

#[tauri::command]
pub fn set_window_extended(window: tauri::WebviewWindow) -> Result<(), String> {
    window.set_size(LogicalSize::new(EXTENDED_W, EXTENDED_H)).map_err(|e| e.to_string())?;
    window.set_always_on_top(false).map_err(|e| e.to_string())?;
    // Opaque background: un-do the transparent compact mode so HTML elements are visible.
    window.set_background_color(Some(Color(10, 10, 15, 255))).map_err(|e| e.to_string())?;
    eprintln!("[jarvis] window: extended mode ({}×{})", EXTENDED_W, EXTENDED_H);
    Ok(())
}

// Toggles between compact and extended; returns true when switching to compact.
#[tauri::command]
pub fn toggle_window_mode(
    window: tauri::WebviewWindow,
    state: tauri::State<WindowMode>,
) -> Result<bool, String> {
    let mut compact = state.0.lock().map_err(|e| e.to_string())?;
    *compact = !*compact;
    if *compact {
        window.set_size(LogicalSize::new(COMPACT_W, COMPACT_H)).map_err(|e| e.to_string())?;
        window.set_always_on_top(true).map_err(|e| e.to_string())?;
        eprintln!("[jarvis] window: toggle → compact");
    } else {
        window.set_size(LogicalSize::new(EXTENDED_W, EXTENDED_H)).map_err(|e| e.to_string())?;
        window.set_always_on_top(false).map_err(|e| e.to_string())?;
        eprintln!("[jarvis] window: toggle → extended");
    }
    Ok(*compact)
}
