use reqwest::multipart;
use std::sync::OnceLock;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

const STT_MODEL: &str = "whisper-large-v3-turbo";

const STT_PROMPT: &str =
    "Jarvis, idée, capture, Converteo, Rayan, staging, supprime, efface, ajoute, note";

// Detect actual audio container from magic bytes so Whisper gets the correct MIME type.
// WebKit on Windows often produces MP4/M4A even when the JS side says "audio/webm".
fn detect_format(data: &[u8]) -> (&'static str, &'static str) {
    if data.len() >= 4 {
        if data.starts_with(&[0x1a, 0x45, 0xdf, 0xa3]) {
            return ("audio.webm", "audio/webm"); // EBML / WebM
        }
        if data.starts_with(b"RIFF") {
            return ("audio.wav", "audio/wav"); // WAV
        }
        if data.starts_with(b"OggS") {
            return ("audio.ogg", "audio/ogg"); // OGG
        }
        if data.len() >= 8 && &data[4..8] == b"ftyp" {
            return ("audio.mp4", "audio/mp4"); // MP4 / M4A
        }
        if data.starts_with(&[0xff, 0xe0]) || data.starts_with(&[0xff, 0xf0]) || data.starts_with(&[0xff, 0xfb]) {
            return ("audio.mp3", "audio/mpeg"); // MP3 sync word
        }
    }
    ("audio.webm", "audio/webm") // fallback
}

#[tauri::command]
pub async fn transcribe_gemini(audio_data: Vec<u8>) -> Result<String, String> {
    let api_key = std::env::var("GROQ_API_KEY")
        .map_err(|_| "GROQ_API_KEY non défini".to_string())?;

    let (filename, mime) = detect_format(&audio_data);
    eprintln!(
        "[jarvis] transcribe_gemini: → {} ({} bytes, detected {})",
        STT_MODEL,
        audio_data.len(),
        mime,
    );

    let t0 = std::time::Instant::now();

    let part = multipart::Part::bytes(audio_data)
        .file_name(filename)
        .mime_str(mime)
        .map_err(|e| e.to_string())?;

    let form = multipart::Form::new()
        .text("model", STT_MODEL)
        .text("language", "fr")
        .text("prompt", STT_PROMPT)
        .text("response_format", "json")
        .part("file", part);

    let response = http_client()
        .post("https://api.groq.com/openai/v1/audio/transcriptions")
        .bearer_auth(&api_key)
        .multipart(form)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = response.status();
    eprintln!("[jarvis] transcribe_gemini: HTTP {}", status);

    if !status.is_success() {
        let err = response.text().await.unwrap_or_default();
        eprintln!("[jarvis] transcribe_gemini: erreur API: {}", err);
        return Err(format!("Erreur Groq STT ({}): {}", status, err));
    }

    let json: serde_json::Value = response.json().await.map_err(|e| e.to_string())?;

    let transcript = json
        .get("text")
        .and_then(|t| t.as_str())
        .unwrap_or("")
        .trim()
        .to_string();

    eprintln!("[timing] stt: {}ms", t0.elapsed().as_millis());
    eprintln!("[jarvis] transcribe_gemini: transcript = {:?}", transcript);
    Ok(transcript)
}
