use base64::Engine as _;
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::{connect_async, tungstenite::Message as WsMessage};

const LIVE_WS_BASE: &str = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.BidiGenerateContent";
const LIVE_MODEL: &str = "models/gemini-2.0-flash-live-001";

#[tauri::command]
pub async fn transcribe_gemini(audio_data: Vec<u8>) -> Result<String, String> {
    let api_key = std::env::var("GEMINI_API_KEY")
        .map_err(|_| "GEMINI_API_KEY non défini".to_string())?;

    let url = format!("{LIVE_WS_BASE}?key={api_key}");
    eprintln!("[jarvis] transcribe_gemini: connexion ({} bytes)", audio_data.len());

    let (ws_stream, _) = tokio::time::timeout(
        std::time::Duration::from_secs(10),
        connect_async(url),
    )
    .await
    .map_err(|_| "Gemini Live: timeout connexion".to_string())?
    .map_err(|e| format!("Gemini Live WS connect: {e}"))?;

    let (mut write, mut read) = ws_stream.split();

    // ── Setup ──────────────────────────────────────────────────────────────────
    let setup = serde_json::json!({
        "setup": {
            "model": LIVE_MODEL,
            "generationConfig": {
                "responseModalities": [],
                "inputAudioTranscription": {}
            }
        }
    });
    write
        .send(WsMessage::Text(setup.to_string()))
        .await
        .map_err(|e| format!("WS setup send: {e}"))?;

    // Wait for setupComplete
    loop {
        match tokio::time::timeout(std::time::Duration::from_secs(10), read.next()).await {
            Ok(Some(Ok(WsMessage::Text(msg)))) => {
                eprintln!("[jarvis] transcribe_gemini: ← {}", &msg.chars().take(120).collect::<String>());
                let v: serde_json::Value = serde_json::from_str(&msg).unwrap_or_default();
                if v.get("setupComplete").is_some() {
                    break;
                }
            }
            Ok(Some(Ok(_))) => {}
            Ok(Some(Err(e))) => return Err(format!("WS error: {e}")),
            Ok(None) => return Err("WS fermé avant setupComplete".to_string()),
            Err(_) => return Err("Timeout setupComplete".to_string()),
        }
    }

    // ── Envoyer l'audio ────────────────────────────────────────────────────────
    // Gemini Live accepte audio/pcm (PCM16 16kHz) nativement.
    // On envoie audio/webm ; si l'API rejette, convertir en PCM côté frontend.
    let b64 = base64::engine::general_purpose::STANDARD.encode(&audio_data);
    let audio_msg = serde_json::json!({
        "realtimeInput": {
            "mediaChunks": [{"mimeType": "audio/webm", "data": b64}]
        }
    });
    write
        .send(WsMessage::Text(audio_msg.to_string()))
        .await
        .map_err(|e| format!("WS audio send: {e}"))?;

    let end_msg = serde_json::json!({
        "realtimeInput": {"audioStreamEnd": true}
    });
    write
        .send(WsMessage::Text(end_msg.to_string()))
        .await
        .map_err(|e| format!("WS audioStreamEnd send: {e}"))?;

    // ── Collecter le transcript ────────────────────────────────────────────────
    let mut transcript = String::new();
    let deadline =
        tokio::time::Instant::now() + std::time::Duration::from_secs(30);

    loop {
        let remaining = deadline
            .checked_duration_since(tokio::time::Instant::now())
            .unwrap_or_default();
        if remaining.is_zero() {
            eprintln!("[jarvis] transcribe_gemini: timeout global");
            break;
        }

        match tokio::time::timeout(remaining, read.next()).await {
            Ok(Some(Ok(WsMessage::Text(msg)))) => {
                eprintln!("[jarvis] transcribe_gemini: ← {}", &msg.chars().take(200).collect::<String>());
                let v: serde_json::Value = serde_json::from_str(&msg).unwrap_or_default();

                if let Some(sc) = v.get("serverContent") {
                    // Transcription du tour utilisateur
                    if let Some(t) = sc
                        .get("inputTranscription")
                        .and_then(|t| t.get("text"))
                        .and_then(|t| t.as_str())
                    {
                        transcript.push_str(t);
                    }

                    // Fallback : réponse texte du modèle (si responseModalities inclut TEXT)
                    if transcript.is_empty() {
                        if let Some(parts) = sc
                            .get("modelTurn")
                            .and_then(|mt| mt.get("parts"))
                            .and_then(|p| p.as_array())
                        {
                            for part in parts {
                                if let Some(t) = part.get("text").and_then(|t| t.as_str()) {
                                    transcript.push_str(t);
                                }
                            }
                        }
                    }

                    if sc.get("turnComplete").and_then(|v| v.as_bool()) == Some(true) {
                        eprintln!("[jarvis] transcribe_gemini: turnComplete — {:?}", transcript);
                        break;
                    }
                }
            }
            Ok(Some(Ok(_))) => {}
            Ok(Some(Err(e))) => {
                eprintln!("[jarvis] transcribe_gemini: WS error: {e}");
                break;
            }
            Ok(None) => {
                eprintln!("[jarvis] transcribe_gemini: WS fermé");
                break;
            }
            Err(_) => {
                eprintln!("[jarvis] transcribe_gemini: timeout lecture");
                break;
            }
        }
    }

    let _ = write.close().await;
    let result = transcript.trim().to_string();
    eprintln!("[jarvis] transcribe_gemini: transcript final = {:?}", result);
    Ok(result)
}
