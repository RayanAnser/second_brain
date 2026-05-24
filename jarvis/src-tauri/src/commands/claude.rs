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

#[tauri::command]
pub async fn ask_claude(
    app:           AppHandle,
    messages:      Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("ANTHROPIC_API_KEY")
        .map_err(|_| "ANTHROPIC_API_KEY non défini".to_string())?;

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
                        if sentence.len() > 3 {
                            app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
                        }
                    }
                }
            }

            if json.get("type").and_then(|t| t.as_str()) == Some("message_stop") {
                // Flush whatever remains — no length filter here, short finals like
                // "Ok!" or "Non." are valid and must be spoken.
                let remaining = sentence_buf.trim().to_string();
                if !remaining.is_empty() {
                    app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
                }
                app.emit("claude-done", ()).map_err(|e| e.to_string())?;
                return Ok(());
            }
        }
    }

    // Fallback flush if stream ended without message_stop
    let remaining = sentence_buf.trim().to_string();
    if !remaining.is_empty() {
        app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
    }
    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    Ok(())
}
