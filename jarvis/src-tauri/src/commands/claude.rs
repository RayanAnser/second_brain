use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use std::sync::OnceLock;
use tauri::{AppHandle, Emitter};

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

#[derive(Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role:    String,
    pub content: String,
}

const VOCAL_INSTRUCTION: &str = "\n\nTu es en mode vocal. Réponds en 1-3 phrases maximum, de façon naturelle et conversationnelle. Pas de listes, pas de markdown.";

const CLASSIFY_SYSTEM: &str = "\
Classifie le message utilisateur. Retourne UNIQUEMENT du JSON valide, sans texte autour.\n\
Intentions : CAPTURE_IDEE, CAPTURE_PROJET, CAPTURE_CONCEPT, CAPTURE_PERSO, TACHE, DELETE_STAGING, CONVERSATION.\n\
- DELETE_STAGING : supprimer une capture en attente (ex: \"supprime la capture X\", \"enlève X\", \"retire ça\").\n\
Format strict : {\"intent\": \"...\", \"content\": \"version épurée, concise\"}\n\
- Pour DELETE_STAGING, content = fragment de texte à chercher dans les captures.\n\
En cas de doute : CONVERSATION.";

fn is_speakable(s: &str) -> bool {
    let t = s.trim();
    !t.starts_with('{') && !t.starts_with('[') && !t.starts_with("```")
}

/// Returns the byte offset just past the first sentence-ending punctuation
/// followed by a space or newline. Returns None if no boundary is found
/// (including when punctuation is at end of buffer — wait for more tokens).
fn find_sentence_end(s: &str) -> Option<usize> {
    let bytes = s.as_bytes();
    for i in 0..bytes.len() {
        if matches!(bytes[i], b'.' | b'!' | b'?') {
            let next = i + 1;
            if next < bytes.len() && (bytes[next] == b' ' || bytes[next] == b'\n') {
                return Some(next);
            }
        }
    }
    None
}

fn fallback_stage(content: &str, hint: &str) {
    let memory_dir = std::env::var("MEMORY_DIR").unwrap_or_else(|_| "./memory".to_string());
    let staging_path = std::path::PathBuf::from(&memory_dir).join("staging.json");
    let chat_id = std::env::var("TELEGRAM_CHAT_ID").unwrap_or_else(|_| "0".to_string());
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M").to_string();

    let text = std::fs::read_to_string(&staging_path).unwrap_or_else(|_| "{}".to_string());
    let mut data: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::json!({}));

    let entry = serde_json::json!({"content": content, "hint": hint, "timestamp": timestamp});
    if let Some(obj) = data.as_object_mut() {
        let arr = obj.entry(chat_id).or_insert_with(|| serde_json::json!([]));
        if let Some(arr) = arr.as_array_mut() {
            arr.push(entry);
        }
    }

    if let Ok(serialized) = serde_json::to_string_pretty(&data) {
        let _ = std::fs::write(&staging_path, serialized);
    }
}

async fn classify_and_stage(text: String, api_key: String, app: AppHandle) {
    eprintln!("[jarvis] classify_and_stage: démarré — text={:?}", text.chars().take(60).collect::<String>());
    if text.is_empty() {
        eprintln!("[jarvis] classify_and_stage: text vide, abandon");
        return;
    }

    let body = serde_json::json!({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 150,
        "system": [{"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": &text}],
    });

    let resp = match http_client()
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key",         &api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type",      "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r)  => r,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: request failed: {e}"); return; }
    };

    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: parse failed: {e}"); return; }
    };

    let raw = match json
        .get("content").and_then(|c| c.get(0))
        .and_then(|b| b.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] classify_and_stage: unexpected response shape"); return; }
    };

    let cleaned = raw
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    let classified: serde_json::Value = match serde_json::from_str(cleaned) {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: JSON parse failed — raw={raw:?} err={e}"); return; }
    };

    let intent  = classified.get("intent").and_then(|v| v.as_str()).unwrap_or("CONVERSATION");
    let content = classified.get("content").and_then(|v| v.as_str()).unwrap_or(text.as_str());

    eprintln!("[jarvis] classify_and_stage: intent={intent:?} content={:?}", content.chars().take(60).collect::<String>());

    let is_capture = matches!(intent, "CAPTURE_IDEE" | "CAPTURE_PROJET" | "CAPTURE_CONCEPT" | "CAPTURE_PERSO");
    let is_tache   = intent == "TACHE";
    let is_delete  = intent == "DELETE_STAGING";

    if !is_capture && !is_tache && !is_delete {
        eprintln!("[jarvis] classify_and_stage: intent CONVERSATION, rien à stager");
        return;
    }

    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());

    if is_delete {
        let _ = app.emit("claude-capture", "🗑 supprimé");
        let payload = serde_json::json!({"query": content});
        eprintln!("[jarvis] classify_and_stage: DELETE_STAGING query={:?}", content);
        let _ = http_client()
            .post(format!("{companion_url}/delete_staging_by_content"))
            .json(&payload)
            .send()
            .await;
        return;
    }

    // Toast immédiat — fire-and-forget, pas bloquant
    let toast = if is_tache { "📋 tâche" } else { "💡 noté" };
    let _ = app.emit("claude-capture", toast);

    let (endpoint, payload) = if is_tache {
        ("/task",  serde_json::json!({"content": content}))
    } else {
        ("/stage", serde_json::json!({"content": content, "hint": intent}))
    };

    eprintln!("[jarvis] classify_and_stage: POST {companion_url}{endpoint}");
    let http_result = http_client()
        .post(format!("{companion_url}{endpoint}"))
        .json(&payload)
        .send()
        .await;

    match http_result {
        Ok(r) if r.status().is_success() => {
            eprintln!("[jarvis] classify_and_stage: companion OK ({} {})", r.status(), endpoint);
        }
        Ok(r) => {
            eprintln!("[jarvis] classify_and_stage: companion erreur HTTP {} — fallback", r.status());
            fallback_stage(content, intent);
        }
        Err(e) => {
            eprintln!("[jarvis] classify_and_stage: companion down ({e}) — fallback staging.json [{intent}]");
            fallback_stage(content, intent);
        }
    }
}

#[tauri::command]
pub async fn ask_claude(
    app:           AppHandle,
    messages:      Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("ANTHROPIC_API_KEY")
        .map_err(|_| "ANTHROPIC_API_KEY non défini".to_string())?;

    let user_text = messages.last().map(|m| m.content.clone()).unwrap_or_default();

    let vocal_system = format!("{}{}", system_prompt, VOCAL_INSTRUCTION);

    let system_blocks = serde_json::json!([{
        "type": "text",
        "text": vocal_system,
        "cache_control": {"type": "ephemeral"}
    }]);

    let body = serde_json::json!({
        "model":      "claude-sonnet-4-5",
        "max_tokens": 256,
        "stream":     true,
        "system":     system_blocks,
        "messages":   messages,
    });

    let response = http_client()
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key",          &api_key)
        .header("anthropic-version",   "2023-06-01")
        .header("content-type",        "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Erreur API Anthropic : {}", err));
    }

    let mut stream = response.bytes_stream();
    let mut sentence_buf = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        let text  = String::from_utf8_lossy(&chunk);

        for line in text.lines() {
            let Some(data) = line.strip_prefix("data: ") else { continue };
            if data == "[DONE]" {
                break;
            }
            let Ok(json) = serde_json::from_str::<serde_json::Value>(data) else { continue };

            if json.get("type").and_then(|t| t.as_str()) == Some("content_block_delta") {
                if let Some(token) = json
                    .get("delta")
                    .and_then(|d| d.get("text"))
                    .and_then(|t| t.as_str())
                {
                    app.emit("claude-token", token).map_err(|e| e.to_string())?;
                    sentence_buf.push_str(token);

                    // Flush all complete sentences found in the buffer
                    while let Some(boundary) = find_sentence_end(&sentence_buf) {
                        let sentence = sentence_buf[..boundary].trim().to_string();
                        sentence_buf = sentence_buf[boundary..].trim_start().to_string();
                        if sentence.len() > 3 && is_speakable(&sentence) {
                            app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
                        }
                    }
                }
            }

            if json.get("type").and_then(|t| t.as_str()) == Some("message_stop") {
                // Flush whatever remains — no length filter here, short finals like
                // "Ok!" or "Non." are valid and must be spoken.
                let remaining = sentence_buf.trim().to_string();
                if !remaining.is_empty() && is_speakable(&remaining) {
                    app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
                }
                app.emit("claude-done", ()).map_err(|e| e.to_string())?;
                eprintln!("[jarvis] ask_claude: message_stop — spawn classify_and_stage");
                tokio::spawn(classify_and_stage(user_text.clone(), api_key.clone(), app.clone()));
                return Ok(());
            }
        }
    }

    // Fallback flush if stream ended without message_stop
    let remaining = sentence_buf.trim().to_string();
    if !remaining.is_empty() && is_speakable(&remaining) {
        app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
    }
    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    eprintln!("[jarvis] ask_claude: fallback flush — spawn classify_and_stage");
    tokio::spawn(classify_and_stage(user_text, api_key, app));
    Ok(())
}
