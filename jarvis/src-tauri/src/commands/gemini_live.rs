use base64::Engine as _;
use std::sync::OnceLock;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

const STT_MODEL: &str = "gemini-2.5-flash";

#[tauri::command]
pub async fn transcribe_gemini(audio_data: Vec<u8>) -> Result<String, String> {
    let api_key = std::env::var("GEMINI_API_KEY")
        .map_err(|_| "GEMINI_API_KEY non défini".to_string())?;

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent?key={}",
        STT_MODEL, api_key
    );

    eprintln!("[jarvis] transcribe_gemini: → {} ({} bytes)", STT_MODEL, audio_data.len());

    let b64 = base64::engine::general_purpose::STANDARD.encode(&audio_data);

    let body = serde_json::json!({
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "text": "Transcris exactement ce que l'utilisateur dit dans cet audio. \
                             Retourne uniquement la transcription, sans rien ajouter."
                },
                {
                    "inlineData": {"mimeType": "audio/webm", "data": b64}
                }
            ]
        }]
    });

    let response = http_client()
        .post(&url)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = response.status();
    eprintln!("[jarvis] transcribe_gemini: HTTP {}", status);

    if !status.is_success() {
        let err = response.text().await.unwrap_or_default();
        eprintln!("[jarvis] transcribe_gemini: erreur API: {}", err);
        return Err(format!("Erreur Gemini STT ({}): {}", status, err));
    }

    let json: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;
    eprintln!("[jarvis] transcribe_gemini: réponse: {}", json);

    let transcript = json
        .get("candidates")
        .and_then(|c| c.get(0))
        .and_then(|c| c.get("content"))
        .and_then(|c| c.get("parts"))
        .and_then(|p| p.get(0))
        .and_then(|p| p.get("text"))
        .and_then(|t| t.as_str())
        .unwrap_or("")
        .trim()
        .to_string();

    eprintln!("[jarvis] transcribe_gemini: transcript = {:?}", transcript);
    Ok(transcript)
}
