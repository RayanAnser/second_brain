use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter};

#[derive(Serialize, Deserialize, Clone)]
pub struct ChatMessage {
    pub role:    String,
    pub content: String,
}

#[tauri::command]
pub async fn ask_claude(
    app:           AppHandle,
    messages:      Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("ANTHROPIC_API_KEY")
        .map_err(|_| "ANTHROPIC_API_KEY non défini".to_string())?;

    let body = serde_json::json!({
        "model":      "claude-sonnet-4-5",
        "max_tokens": 1024,
        "stream":     true,
        "system":     system_prompt,
        "messages":   messages,
    });

    let client   = reqwest::Client::new();
    let response = client
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

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        let text  = String::from_utf8_lossy(&chunk);

        for line in text.lines() {
            let Some(data) = line.strip_prefix("data: ") else { continue };
            if data == "[DONE]" {
                break;
            }
            let Ok(json) = serde_json::from_str::<serde_json::Value>(data) else { continue };

            // content_block_delta → delta.text
            if json.get("type").and_then(|t| t.as_str()) == Some("content_block_delta") {
                if let Some(token) = json
                    .get("delta")
                    .and_then(|d| d.get("text"))
                    .and_then(|t| t.as_str())
                {
                    app.emit("claude-token", token).map_err(|e| e.to_string())?;
                }
            }

            // message_stop → done
            if json.get("type").and_then(|t| t.as_str()) == Some("message_stop") {
                app.emit("claude-done", ()).map_err(|e| e.to_string())?;
                return Ok(());
            }
        }
    }

    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    Ok(())
}
