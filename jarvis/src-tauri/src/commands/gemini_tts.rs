use std::sync::OnceLock;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

const TTS_MODEL: &str = "eleven_flash_v2_5";

#[tauri::command]
pub async fn synthesize_speech(text: String) -> Result<Vec<u8>, String> {
    let api_key = std::env::var("ELEVENLABS_API_KEY")
        .map_err(|_| "ELEVENLABS_API_KEY non défini".to_string())?;
    let voice_id = std::env::var("ELEVENLABS_VOICE_ID")
        .map_err(|_| "ELEVENLABS_VOICE_ID non défini".to_string())?;

    let url = format!(
        "https://api.elevenlabs.io/v1/text-to-speech/{}/stream",
        voice_id
    );

    eprintln!(
        "[jarvis] synthesize_speech: → ElevenLabs {} voice={} — {:?} ({} chars)",
        TTS_MODEL,
        &voice_id,
        &text.chars().take(60).collect::<String>(),
        text.len(),
    );

    let t0 = std::time::Instant::now();

    let body = serde_json::json!({
        "text": text,
        "model_id": TTS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    });

    let response = http_client()
        .post(&url)
        .header("xi-api-key", &api_key)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = response.status();
    eprintln!("[jarvis] synthesize_speech: HTTP {}", status);

    if !status.is_success() {
        let err = response.text().await.unwrap_or_default();
        eprintln!("[jarvis] synthesize_speech: erreur API ElevenLabs: {}", err);
        return Err(format!("Erreur ElevenLabs TTS ({}): {}", status, err));
    }

    let bytes = response.bytes().await.map_err(|e| e.to_string())?;
    let bytes_vec = bytes.to_vec();

    eprintln!("[timing] tts: {}ms — {} bytes MP3", t0.elapsed().as_millis(), bytes_vec.len());
    Ok(bytes_vec)
}
