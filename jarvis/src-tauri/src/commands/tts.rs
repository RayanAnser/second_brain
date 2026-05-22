use futures_util::StreamExt;

const CHARLOTTE_VOICE_ID: &str = "XB0fDUnXU5powFXDhCwa";
const ELEVENLABS_MODEL: &str = "eleven_multilingual_v2";

#[tauri::command]
pub async fn synthesize_speech(text: String) -> Result<Vec<u8>, String> {
    let api_key = std::env::var("ELEVENLABS_API_KEY")
        .map_err(|_| "ELEVENLABS_API_KEY non défini".to_string())?;

    let voice_id = std::env::var("ELEVENLABS_VOICE_ID")
        .unwrap_or_else(|_| CHARLOTTE_VOICE_ID.to_string());

    let url = format!(
        "https://api.elevenlabs.io/v1/text-to-speech/{}/stream",
        voice_id
    );

    let body = serde_json::json!({
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    });

    let client = reqwest::Client::new();
    let response = client
        .post(&url)
        .header("xi-api-key", &api_key)
        .header("content-type", "application/json")
        .header("accept", "audio/mpeg")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Erreur ElevenLabs : {}", err));
    }

    let mut stream = response.bytes_stream();
    let mut audio_bytes: Vec<u8> = Vec::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        audio_bytes.extend_from_slice(&chunk);
    }

    Ok(audio_bytes)
}
