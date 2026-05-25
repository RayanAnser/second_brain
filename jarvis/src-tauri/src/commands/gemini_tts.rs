use base64::Engine as _;
use std::sync::OnceLock;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

const TTS_MODEL: &str = "gemini-3.1-flash-tts-preview";

#[tauri::command]
pub async fn synthesize_speech(text: String) -> Result<Vec<u8>, String> {
    let api_key = std::env::var("GEMINI_API_KEY")
        .map_err(|_| "GEMINI_API_KEY non défini".to_string())?;

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
        TTS_MODEL, api_key
    );

    eprintln!("[jarvis] synthesize_speech: → {} — {:?} ({} chars)", TTS_MODEL, &text.chars().take(60).collect::<String>(), text.len());

    let body = serde_json::json!({
        "contents": [{"role": "user", "parts": [{"text": text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": { "voiceName": "Aoede" }
                }
            }
        }
    });

    let response = http_client()
        .post(&url)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = response.status();
    eprintln!("[jarvis] synthesize_speech: HTTP {}", status);

    if !status.is_success() {
        let err = response.text().await.unwrap_or_default();
        eprintln!("[jarvis] synthesize_speech: erreur API: {}", err);
        return Err(format!("Erreur Gemini TTS ({}): {}", status, err));
    }

    let json: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    eprintln!("[jarvis] synthesize_speech: réponse JSON: {}", json);

    // Inspecter la structure avant de tenter l'extraction
    let candidate = json.get("candidates").and_then(|c| c.get(0));
    eprintln!("[jarvis] synthesize_speech: candidate présent = {}", candidate.is_some());

    let parts = candidate
        .and_then(|c| c.get("content"))
        .and_then(|c| c.get("parts"));
    eprintln!("[jarvis] synthesize_speech: parts présent = {}", parts.is_some());

    let inline_data = parts
        .and_then(|p| p.get(0))
        .and_then(|p| p.get("inlineData"));
    eprintln!("[jarvis] synthesize_speech: inlineData présent = {}", inline_data.is_some());

    if let Some(id) = inline_data {
        eprintln!(
            "[jarvis] synthesize_speech: inlineData.mimeType = {:?}, data len = {}",
            id.get("mimeType").and_then(|m| m.as_str()).unwrap_or("?"),
            id.get("data").and_then(|d| d.as_str()).map(|s| s.len()).unwrap_or(0),
        );
    }

    let b64 = inline_data
        .and_then(|d| d.get("data"))
        .and_then(|d| d.as_str())
        .ok_or_else(|| format!("Réponse Gemini TTS inattendue — pas d'inlineData : {}", json))?;

    let bytes = base64::engine::general_purpose::STANDARD
        .decode(b64)
        .map_err(|e| format!("base64 decode: {e}"))?;

    eprintln!("[jarvis] synthesize_speech: {} bytes audio décodés", bytes.len());
    Ok(bytes)
}
