use serde::{Deserialize, Serialize};
use std::{fs, path::PathBuf};
use std::sync::OnceLock;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

fn memory_dir() -> PathBuf {
    let raw = std::env::var("MEMORY_DIR");
    eprintln!("[jarvis] MEMORY_DIR raw = {:?}", raw);
    let val = raw.unwrap_or_else(|_| "./memory".to_string());
    let path = PathBuf::from(&val);
    eprintln!("[jarvis] memory_dir resolved = {:?}", path);
    path
}

#[derive(Serialize, Deserialize)]
pub struct MemoryContext {
    pub soul:   String,
    pub user:   String,
    pub memory: String,
    pub style:  String,
}

#[derive(Serialize, Deserialize)]
pub struct DocEntry {
    pub key:     String,   // "projets/foo.md"
    pub name:    String,   // "foo"
    pub size_kb: f64,
    pub subdir:  String,   // "projets" | "concepts" | "perso"
}

#[derive(Serialize, Deserialize)]
pub struct Capture {
    pub intent:  String,
    pub content: String,
    #[serde(default)]
    pub section: Option<String>,
}

#[tauri::command]
pub fn read_memory_context() -> MemoryContext {
    let dir = memory_dir();
    let read = |name: &str| {
        let path = dir.join(name);
        match fs::read_to_string(&path) {
            Ok(content) => {
                eprintln!("[jarvis] read {:?} → {} chars", path, content.len());
                content
            }
            Err(e) => {
                eprintln!("[jarvis] read {:?} → ERROR: {}", path, e);
                String::new()
            }
        }
    };
    MemoryContext {
        soul:   read("soul.md"),
        user:   read("user.md"),
        memory: read("memory.md"),
        style:  read("jarvis_style.md"),
    }
}

#[tauri::command]
pub fn debug_memory() -> serde_json::Value {
    let raw = std::env::var("MEMORY_DIR").unwrap_or_else(|_| "<NOT SET>".to_string());
    let dir = memory_dir();
    let soul_path = dir.join("soul.md");
    let soul_result = fs::read_to_string(&soul_path)
        .map(|c| format!("OK ({} chars)", c.len()))
        .unwrap_or_else(|e| format!("ERROR: {}", e));
    serde_json::json!({
        "MEMORY_DIR_raw": raw,
        "resolved_path": dir.to_string_lossy(),
        "soul_path": soul_path.to_string_lossy(),
        "soul_exists": soul_path.exists(),
        "soul_read": soul_result,
        "cwd": std::env::current_dir().map(|p| p.to_string_lossy().to_string()).unwrap_or_default(),
    })
}

#[tauri::command]
pub fn list_docs(keyword: Option<String>) -> Vec<DocEntry> {
    let dir = memory_dir();
    let kw  = keyword.as_deref().map(|s| s.to_lowercase());
    let subdirs = [("projets", "projets"), ("concepts", "concepts"), ("perso", "perso")];
    let mut entries = Vec::new();

    for (folder, label) in subdirs {
        let path = dir.join(folder);
        if !path.exists() {
            continue;
        }
        let mut files: Vec<_> = fs::read_dir(&path)
            .into_iter()
            .flatten()
            .flatten()
            .filter(|e| e.path().extension().map_or(false, |x| x == "md"))
            .collect();
        files.sort_by_key(|e| e.file_name());

        for entry in files {
            let p    = entry.path();
            let fname = p.file_name().unwrap_or_default().to_string_lossy().to_string();
            let key  = format!("{}/{}", label, fname);

            if let Some(kw) = &kw {
                if !key.to_lowercase().contains(kw) {
                    continue;
                }
            }

            let size_kb = p.metadata().map(|m| m.len() as f64 / 1024.0).unwrap_or(0.0);
            let name    = p.file_stem().unwrap_or_default().to_string_lossy().to_string();

            entries.push(DocEntry { key, name, size_kb, subdir: label.to_string() });
        }
    }

    entries
}

#[tauri::command]
pub fn read_doc(rel_key: String) -> Result<String, String> {
    // Guard against path traversal without canonicalize() (which breaks UNC paths on Windows)
    if rel_key.contains("..") || std::path::Path::new(&rel_key).is_absolute() {
        return Err("Accès refusé".to_string());
    }
    let path = memory_dir().join(&rel_key);
    fs::read_to_string(&path).map_err(|e| e.to_string())
}

fn captures_from_json(json: &serde_json::Value) -> Vec<Capture> {
    let mut captures = Vec::new();
    if let Some(obj) = json.as_object() {
        for list in obj.values() {
            if let Some(arr) = list.as_array() {
                for item in arr {
                    captures.push(Capture {
                        intent:  item.get("hint").or_else(|| item.get("intent"))
                                     .and_then(|v| v.as_str()).unwrap_or("?").to_string(),
                        content: item.get("content").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        section: item.get("section").and_then(|v| v.as_str()).map(str::to_owned),
                    });
                }
            }
        }
    }
    captures
}

fn read_staging_file() -> Vec<Capture> {
    let path    = memory_dir().join("staging.json");
    let content = fs::read_to_string(&path).unwrap_or_else(|_| "{}".to_string());
    let json: serde_json::Value = serde_json::from_str(&content).unwrap_or_default();
    captures_from_json(&json)
}

async fn fetch_staging_impl(companion_url: &str) -> Vec<Capture> {
    if let Ok(resp) = http_client()
        .get(format!("{companion_url}/staging"))
        .send()
        .await
    {
        if resp.status().is_success() {
            if let Ok(captures) = resp.json::<Vec<Capture>>().await {
                return captures;
            }
        }
    }
    eprintln!("[jarvis] fetch_staging_impl: companion injoignable — fallback staging.json");
    read_staging_file()
}

fn delete_from_file(index: usize) -> Result<Vec<Capture>, String> {
    let path    = memory_dir().join("staging.json");
    let content = fs::read_to_string(&path).unwrap_or_else(|_| "{}".to_string());
    let mut json: serde_json::Value = serde_json::from_str(&content).map_err(|e| e.to_string())?;

    {
        let obj      = json.as_object_mut().ok_or("staging.json invalide")?;
        let mut idx  = 0usize;
        let mut found = false;
        'outer: for list in obj.values_mut() {
            if let Some(arr) = list.as_array_mut() {
                for i in 0..arr.len() {
                    if idx == index { arr.remove(i); found = true; break 'outer; }
                    idx += 1;
                }
            }
        }
        if !found { return Err(format!("Index {} hors limites", index)); }
    }

    let updated = serde_json::to_string_pretty(&json).map_err(|e| e.to_string())?;
    fs::write(&path, updated).map_err(|e| e.to_string())?;
    Ok(captures_from_json(&json))
}

/// Fetches the authoritative capture list from companion RAM.
/// Falls back to reading staging.json if companion is unreachable.
#[tauri::command]
pub async fn fetch_staging() -> Vec<Capture> {
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    fetch_staging_impl(&companion_url).await
}

/// Reads the authoritative capture list from companion RAM.
/// Falls back to staging.json if companion is unreachable.
/// Identical to fetch_staging — kept for backward compatibility.
#[tauri::command]
pub async fn read_staging() -> Vec<Capture> {
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    fetch_staging_impl(&companion_url).await
}

/// Deletes the capture at `index` (position within the CHAT_ID bucket as
/// returned by GET /staging).  Companion is the authoritative owner — we ask
/// it to delete first and use its returned list.  File-only fallback when
/// companion is unreachable.
#[tauri::command]
pub async fn delete_staging(index: usize) -> Result<Vec<Capture>, String> {
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());

    if let Ok(resp) = http_client()
        .post(format!("{companion_url}/delete_staging"))
        .json(&serde_json::json!({"index": index}))
        .send()
        .await
    {
        if resp.status().is_success() {
            if let Ok(data) = resp.json::<serde_json::Value>().await {
                if let Ok(list) = serde_json::from_value::<Vec<Capture>>(data["captures"].clone()) {
                    return Ok(list);
                }
            }
            // Companion OK but response malformed — re-fetch authoritative state
            return Ok(fetch_staging_impl(&companion_url).await);
        }
        // Companion returned an error (e.g. 404 out-of-bounds)
        return Err(format!("companion /delete_staging: index {} hors limites", index));
    }

    // Companion unreachable — fall back to direct file manipulation
    delete_from_file(index)
}

/// Confirms a non-MEMORY staging item: routes it to the appropriate companion endpoint
/// (TACHE → fils ouverts, CAPTURE_PERSO → user.md, others → memory.md "Captures confirmées").
/// Returns the updated capture list.
#[tauri::command]
pub async fn confirm_staging_item(index: usize) -> Result<Vec<Capture>, String> {
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());

    let resp = http_client()
        .post(format!("{companion_url}/staging/confirm"))
        .json(&serde_json::json!({"index": index}))
        .send()
        .await
        .map_err(|e| format!("companion injoignable: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body   = resp.text().await.unwrap_or_default();
        return Err(format!("/staging/confirm {status}: {body}"));
    }

    let data = resp.json::<serde_json::Value>().await.map_err(|e| e.to_string())?;
    serde_json::from_value::<Vec<Capture>>(data["captures"].clone())
        .map_err(|e| e.to_string())
}

/// Writes a MEMORY staging item into memory.md or user.md via the companion,
/// then removes it from staging.  Returns the updated capture list.
#[tauri::command]
pub async fn commit_memory_item(index: usize) -> Result<Vec<Capture>, String> {
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());

    let resp = http_client()
        .post(format!("{companion_url}/memory/commit"))
        .json(&serde_json::json!({"index": index}))
        .send()
        .await
        .map_err(|e| format!("companion injoignable: {e}"))?;

    if !resp.status().is_success() {
        let status = resp.status();
        let body   = resp.text().await.unwrap_or_default();
        return Err(format!("/memory/commit {status}: {body}"));
    }

    let data = resp.json::<serde_json::Value>().await.map_err(|e| e.to_string())?;
    serde_json::from_value::<Vec<Capture>>(data["captures"].clone())
        .map_err(|e| e.to_string())
}
