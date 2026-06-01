use base64::Engine;
use futures_util::StreamExt;
use screenshots::Screen;
use std::sync::OnceLock;
use tauri::{AppHandle, Emitter};

use super::claude::ChatMessage;

static HTTP_CLIENT: OnceLock<reqwest::Client> = OnceLock::new();

fn http_client() -> &'static reqwest::Client {
    HTTP_CLIENT.get_or_init(reqwest::Client::new)
}

fn is_speakable(s: &str) -> bool {
    let t = s.trim();
    !t.starts_with('{') && !t.starts_with('[') && !t.starts_with("```")
}

fn find_sentence_end_complete(s: &str) -> Option<usize> {
    for (i, c) in s.char_indices() {
        if matches!(c, '.' | '!' | '?' | '…') {
            let end = i + c.len_utf8();
            match s.as_bytes().get(end) {
                Some(&b' ') | Some(&b'\n') => return Some(end),
                None => return Some(end),
                _ => {}
            }
        }
    }
    None
}

fn split_sentences(text: &str) -> Vec<String> {
    let mut out = Vec::new();
    let mut buf = text.trim().to_string();
    loop {
        match find_sentence_end_complete(&buf) {
            Some(boundary) => {
                let s = buf[..boundary].trim().to_string();
                buf = buf[boundary..].trim_start().to_string();
                if s.len() > 3 && is_speakable(&s) { out.push(s); }
            }
            None => {
                let tail = buf.trim().to_string();
                if tail.len() > 3 && is_speakable(&tail) { out.push(tail); }
                break;
            }
        }
    }
    out
}

pub fn is_screen_read(text: &str) -> bool {
    let lower = text.to_lowercase();
    // références explicites à l'écran
    lower.contains("mon écran")
        || lower.contains("l'écran")
        || lower.contains("sur l'écran")
        // "regarde …"
        || lower.contains("regarde ça")
        || lower.contains("regarde ce")
        || lower.contains("regardes ça")
        || lower.contains("regardes ce")
        || lower.contains("regarde mon écran")
        || lower.contains("regarde l'écran")
        // "tu vois …"
        || lower.contains("tu vois ça")
        || lower.contains("tu vois ce")
        || lower.contains("qu'est-ce que tu vois")
        || lower.contains("qu est ce que tu vois")
        || lower.contains("que vois-tu")
        || lower.contains("tu vois quoi")
        // "analyse …"
        || lower.contains("analyse ça")
        || lower.contains("analyse ce")
        || lower.contains("analyse mon écran")
        || lower.contains("analyse l'écran")
        // "c'est quoi …"
        || lower.contains("c'est quoi ça")
        || lower.contains("c'est quoi ce")
        || lower.contains("c'est quoi cette")
        || lower.contains("qu'est-ce que c'est")
        || lower.contains("qu'est-ce que c'est que ça")
        // "qu'est-ce qu'il/ça affiche/dit"
        || lower.contains("ça affiche")
        || lower.contains("s'affiche")
        || lower.contains("qu'est-ce qu'il dit")
        || lower.contains("qu'est-ce que ça dit")
        // argot / oral
        || lower.contains("kesako")
        || lower.contains("kézako")
}

fn capture_screen_base64() -> Result<String, String> {
    let screens = Screen::all()
        .map_err(|e| format!("Screen::all() error: {e}"))?;
    let screen = screens
        .into_iter()
        .next()
        .ok_or_else(|| "Aucun écran trouvé".to_string())?;
    let img = screen
        .capture()
        .map_err(|e| format!("screen.capture() error: {e}"))?;
    let mut cursor = std::io::Cursor::new(Vec::new());
    image::DynamicImage::ImageRgba8(img)
        .write_to(&mut cursor, image::ImageFormat::Png)
        .map_err(|e| format!("Impossible d'encoder le screenshot en PNG: {e}"))?;
    Ok(base64::engine::general_purpose::STANDARD.encode(cursor.get_ref()))
}

pub async fn screenshot_and_analyze_inner(
    app: AppHandle,
    messages: Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("GEMINI_API_KEY")
        .map_err(|_| "GEMINI_API_KEY non défini".to_string())?;

    let question = messages.last().map(|m| m.content.clone()).unwrap_or_default();

    eprintln!("[jarvis] screenshot_and_analyze: capture écran...");
    let b64 = capture_screen_base64()?;
    eprintln!("[jarvis] screenshot_and_analyze: {} chars base64", b64.len());

    let vocal = "\n\nTu es en mode vocal. Réponds en 1-3 phrases maximum, de façon naturelle et conversationnelle. Pas de listes, pas de markdown. Utilise une ponctuation riche — virgules, points de suspension, tirets — pour marquer les pauses et le rythme. Tu peux placer des onomatopées naturelles (\"Hm.\", \"Ah.\", \"Bon.\") en début de réponse quand ça colle. Le TTS est sensible à la ponctuation pour l'intonation : plus tu structures, plus le rendu est naturel.";
    let full_system = format!("{}{}", system_prompt, vocal);

    // Build contents: prior turns as text-only, last turn carries screenshot + question.
    let mut contents: Vec<serde_json::Value> = messages[..messages.len().saturating_sub(1)]
        .iter()
        .map(|m| {
            let role = if m.role == "assistant" { "model" } else { "user" };
            serde_json::json!({"role": role, "parts": [{"text": m.content}]})
        })
        .collect();
    contents.push(serde_json::json!({
        "role": "user",
        "parts": [
            {"inline_data": {"mime_type": "image/png", "data": b64}},
            {"text": &question}
        ]
    }));

    let body = serde_json::json!({
        "system_instruction": {"parts": [{"text": full_system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 4096}
    });

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:streamGenerateContent?alt=sse&key={}",
        api_key
    );

    let t1 = std::time::Instant::now();
    let response = http_client()
        .post(&url)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    eprintln!("[timing] vision: HTTP headers: {}ms", t1.elapsed().as_millis());

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Erreur Gemini Vision : {err}"));
    }

    let mut stream             = response.bytes_stream();
    let mut line_buf           = String::new();
    let mut full_response      = String::new();
    let mut chunk_count        = 0usize;
    let mut last_finish_reason = String::new();

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        line_buf.push_str(&String::from_utf8_lossy(&chunk));

        while let Some(nl) = line_buf.find('\n') {
            let line = line_buf[..nl].trim_end_matches('\r').to_string();
            line_buf.drain(..=nl);

            let Some(data) = line.strip_prefix("data: ") else { continue };
            let Ok(json) = serde_json::from_str::<serde_json::Value>(data) else { continue };

            chunk_count += 1;
            if let Some(reason) = json
                .get("candidates").and_then(|c| c.get(0))
                .and_then(|c| c.get("finishReason")).and_then(|r| r.as_str())
            {
                last_finish_reason = reason.to_string();
            }

            if let Some(token) = json
                .get("candidates").and_then(|c| c.get(0))
                .and_then(|c| c.get("content"))
                .and_then(|c| c.get("parts")).and_then(|p| p.get(0))
                .and_then(|p| p.get("text")).and_then(|t| t.as_str())
            {
                app.emit("claude-token", token).map_err(|e| e.to_string())?;
                full_response.push_str(token);
            }
        }
    }

    // Flush any partial SSE line that didn't end with \n
    if !line_buf.is_empty() {
        let line = line_buf.trim_end_matches(|c: char| c == '\r' || c == '\n');
        if let Some(data) = line.strip_prefix("data: ") {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(data) {
                chunk_count += 1;
                if let Some(reason) = json
                    .get("candidates").and_then(|c| c.get(0))
                    .and_then(|c| c.get("finishReason")).and_then(|r| r.as_str())
                {
                    last_finish_reason = reason.to_string();
                }
                if let Some(token) = json
                    .get("candidates").and_then(|c| c.get(0))
                    .and_then(|c| c.get("content"))
                    .and_then(|c| c.get("parts")).and_then(|p| p.get(0))
                    .and_then(|p| p.get("text")).and_then(|t| t.as_str())
                {
                    let _ = app.emit("claude-token", token);
                    full_response.push_str(token);
                }
            }
        }
    }

    eprintln!("[timing] vision: stream done in {}ms", t1.elapsed().as_millis());
    eprintln!("[jarvis] vision: chunks={chunk_count} finishReason={last_finish_reason:?} full_response={:?}", full_response.chars().take(200).collect::<String>());

    let sentences = split_sentences(&full_response);
    eprintln!("[jarvis] vision: {} phrase(s) TTS", sentences.len());
    for sentence in &sentences {
        app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
    }

    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
pub async fn screenshot_and_analyze(
    app: AppHandle,
    messages: Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    screenshot_and_analyze_inner(app, messages, system_prompt).await
}
