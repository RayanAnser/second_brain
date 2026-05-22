use reqwest::multipart;

#[tauri::command]
pub async fn transcribe_audio(audio_data: Vec<u8>) -> Result<String, String> {
    let api_key = std::env::var("GROQ_API_KEY")
        .map_err(|_| "GROQ_API_KEY non défini".to_string())?;

    let part = multipart::Part::bytes(audio_data)
        .file_name("audio.webm")
        .mime_str("audio/webm")
        .map_err(|e| e.to_string())?;

    let form = multipart::Form::new()
        .text("model", "whisper-large-v3")
        .text("language", "fr")
        .text("response_format", "json")
        .part("file", part);

    let client = reqwest::Client::new();
    let response = client
        .post("https://api.groq.com/openai/v1/audio/transcriptions")
        .bearer_auth(&api_key)
        .multipart(form)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let json: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;

    json.get("text")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
        .ok_or_else(|| format!("Réponse Groq inattendue : {}", json))
}
