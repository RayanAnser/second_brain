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

const CLASSIFY_SYSTEM: &str = "\
Classifie le message utilisateur. Retourne UNIQUEMENT du JSON valide, sans texte autour.\n\
Intentions : CAPTURE_IDEE, CAPTURE_PROJET, CAPTURE_CONCEPT, CAPTURE_PERSO, TACHE, DELETE_STAGING, CONVERSATION.\n\
\n\
Règles pour content :\n\
- content = nom brut de l'idée, SANS préfixe. JAMAIS \"Ne pas utiliser :\", \"Recette :\", \"Idée :\", \"Note :\" ou tout autre label.\n\
- Correct : \"Roland Garros\"  Incorrect : \"Idée : Roland Garros\"\n\
- Correct : \"boire plus d'eau\"  Incorrect : \"Note : boire plus d'eau\"\n\
\n\
Format par défaut (un seul sujet) : {\"intent\": \"...\", \"content\": \"version épurée, concise\"}\n\
\n\
DELETE_STAGING : supprimer une capture en attente (ex: \"supprime X\", \"enlève X\", \"retire ça\").\n\
- content = nom exact de la capture à chercher, un seul nom par objet.\n\
- Si l'utilisateur veut effacer PLUSIEURS captures, retourner UN objet DELETE_STAGING PAR capture.\n\
- JAMAIS combiner plusieurs noms dans un seul content.\n\
- Exemple pour \"efface Roland Garros et Club Maté\" :\n\
  [{\"intent\": \"DELETE_STAGING\", \"content\": \"Roland Garros\"}, {\"intent\": \"DELETE_STAGING\", \"content\": \"Club Maté\"}]\n\
\n\
Si le message contient plusieurs intentions distinctes (CAPTURE_*, TACHE ou DELETE_STAGING), retourne un array.\n\
N'utilise l'array que si les intentions sont vraiment distinctes. CONVERSATION : toujours un objet simple.\n\
En cas de doute : CONVERSATION.";

fn is_speakable(s: &str) -> bool {
    let t = s.trim();
    !t.starts_with('{') && !t.starts_with('[') && !t.starts_with("```")
}

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

fn fallback_stage(content: &str, hint: &str) {
    let memory_dir = std::env::var("MEMORY_DIR").unwrap_or_else(|_| "./memory".to_string());
    let staging_path = std::path::PathBuf::from(&memory_dir).join("staging.json");
    let chat_id = match std::env::var("TELEGRAM_CHAT_ID") {
        Ok(v) if !v.is_empty() && v != "0" => v,
        _ => {
            eprintln!("[jarvis] fallback_stage: TELEGRAM_CHAT_ID non défini ou 0 — abandon (ajouter dans .env)");
            return;
        }
    };
    let timestamp = chrono::Local::now().format("%Y-%m-%d %H:%M").to_string();

    let text = std::fs::read_to_string(&staging_path).unwrap_or_else(|_| "{}".to_string());
    let mut data: serde_json::Value = serde_json::from_str(&text).unwrap_or(serde_json::json!({}));

    let entry = serde_json::json!({"content": content, "hint": hint, "timestamp": timestamp});
    if let Some(obj) = data.as_object_mut() {
        let arr = obj.entry(chat_id).or_insert_with(|| serde_json::json!([]));
        if let Some(arr) = arr.as_array_mut() {
            arr.push(entry);
        }
    }

    if let Ok(serialized) = serde_json::to_string_pretty(&data) {
        let _ = std::fs::write(&staging_path, serialized);
    }
}

async fn classify_and_stage(text: String, api_key: String, app: AppHandle) {
    eprintln!("[jarvis] classify_and_stage: démarré — text={:?}", text.chars().take(60).collect::<String>());
    if text.is_empty() {
        eprintln!("[jarvis] classify_and_stage: text vide, abandon");
        return;
    }

    let body = serde_json::json!({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "system": [{"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "messages": [{"role": "user", "content": &text}],
    });

    let resp = match http_client()
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key",         &api_key)
        .header("anthropic-version", "2023-06-01")
        .header("content-type",      "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r)  => r,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: request failed: {e}"); return; }
    };

    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: parse failed: {e}"); return; }
    };

    let raw = match json
        .get("content").and_then(|c| c.get(0))
        .and_then(|b| b.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] classify_and_stage: unexpected response shape"); return; }
    };

    let cleaned = raw
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();
    let classified: serde_json::Value = match serde_json::from_str(cleaned) {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify_and_stage: JSON parse failed — raw={raw:?} err={e}"); return; }
    };

    // Normalise la réponse Haiku en Vec<(intent, content)>.
    // Haiku retourne soit un objet {intent, content} soit un array pour les multi-captures.
    let items: Vec<(String, String)> = if classified.is_array() {
        classified.as_array().unwrap().iter()
            .filter_map(|item| {
                let intent  = item.get("intent")?.as_str()?.to_string();
                let content = item.get("content")?.as_str()?.to_string();
                Some((intent, content))
            })
            .collect()
    } else {
        let intent  = classified.get("intent").and_then(|v| v.as_str())
                          .unwrap_or("CONVERSATION").to_string();
        let content = classified.get("content").and_then(|v| v.as_str())
                          .unwrap_or(text.as_str()).to_string();
        vec![(intent, content)]
    };

    if items.is_empty() {
        eprintln!("[jarvis] classify_and_stage: array vide, abandon");
        return;
    }

    eprintln!("[jarvis] classify_and_stage: {} item(s) classifiés", items.len());

    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());

    // Sépare suppressions et captures actionnables
    let deletes:  Vec<&(String, String)> = items.iter()
        .filter(|(i, _)| i == "DELETE_STAGING")
        .collect();
    let captures: Vec<&(String, String)> = items.iter()
        .filter(|(i, _)| matches!(
            i.as_str(),
            "CAPTURE_IDEE" | "CAPTURE_PROJET" | "CAPTURE_CONCEPT" | "CAPTURE_PERSO" | "TACHE"
        ))
        .collect();

    if deletes.is_empty() && captures.is_empty() {
        eprintln!("[jarvis] classify_and_stage: intent CONVERSATION, rien à stager");
        return;
    }

    // ── Traite chaque DELETE_STAGING ──────────────────────────────────────────
    if !deletes.is_empty() {
        let mut n_ok = 0usize;
        let mut last_deleted = String::new();
        for (_, query) in &deletes {
            eprintln!("[jarvis] classify_and_stage: DELETE_STAGING query={query:?}");
            match http_client()
                .post(format!("{companion_url}/delete_staging_by_content"))
                .json(&serde_json::json!({"query": query}))
                .send()
                .await
            {
                Ok(resp) if resp.status().is_success() => {
                    match resp.json::<serde_json::Value>().await {
                        Ok(body) if body["ok"] == true => {
                            n_ok += 1;
                            last_deleted = body["deleted"].as_str().unwrap_or("?").to_string();
                            eprintln!("[jarvis] DELETE_STAGING ok — supprimé: {last_deleted:?}");
                        }
                        Ok(_)  => eprintln!("[jarvis] DELETE_STAGING ok=false — non trouvé"),
                        Err(e) => eprintln!("[jarvis] DELETE_STAGING parse error: {e}"),
                    }
                }
                Ok(resp) => eprintln!("[jarvis] DELETE_STAGING HTTP {}", resp.status()),
                Err(e)   => eprintln!("[jarvis] DELETE_STAGING companion down: {e}"),
            }
        }
        let toast = match n_ok {
            0 => "❌ non trouvé".to_string(),
            1 => format!("🗑 supprimé : {last_deleted}"),
            n => format!("🗑 {} suppressions", n),
        };
        let _ = app.emit("claude-capture", toast);
    }

    // ── Stage chaque capture/tâche ────────────────────────────────────────────
    if !captures.is_empty() {
        let toast = if captures.len() == 1 {
            if captures[0].0 == "TACHE" { "📋 tâche".to_string() } else { "💡 noté".to_string() }
        } else {
            format!("💡 {} captures notées", captures.len())
        };
        let _ = app.emit("claude-capture", toast);

        for (intent, content) in &captures {
            let (endpoint, payload) = if intent.as_str() == "TACHE" {
                ("/task",  serde_json::json!({"content": content}))
            } else {
                ("/stage", serde_json::json!({"content": content, "hint": intent}))
            };

            eprintln!("[jarvis] classify_and_stage: POST {companion_url}{endpoint} — {intent:?}");
            let http_result = http_client()
                .post(format!("{companion_url}{endpoint}"))
                .json(&payload)
                .send()
                .await;

            match http_result {
                Ok(r) if r.status().is_success() => {
                    eprintln!("[jarvis] classify_and_stage: companion OK ({} {})", r.status(), endpoint);
                }
                Ok(r) => {
                    eprintln!("[jarvis] classify_and_stage: companion erreur HTTP {} — fallback", r.status());
                    fallback_stage(content, intent);
                }
                Err(e) => {
                    eprintln!("[jarvis] classify_and_stage: companion down ({e}) — fallback [{intent}]");
                    fallback_stage(content, intent);
                }
            }
        }
    }
}

#[tauri::command]
pub async fn ask_claude(
    app:           AppHandle,
    messages:      Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("ANTHROPIC_API_KEY")
        .map_err(|_| "ANTHROPIC_API_KEY non défini".to_string())?;

    let user_text = messages.last().map(|m| m.content.clone()).unwrap_or_default();

    let vocal_system = format!("{}{}", system_prompt, VOCAL_INSTRUCTION);

    let system_blocks = serde_json::json!([{
        "type": "text",
        "text": vocal_system,
        "cache_control": {"type": "ephemeral"}
    }]);

    let body = serde_json::json!({
        "model":      "claude-sonnet-4-5-20250929",
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
                        if sentence.len() > 3 && is_speakable(&sentence) {
                            app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
                        }
                    }
                }
            }

            if json.get("type").and_then(|t| t.as_str()) == Some("message_stop") {
                // Flush whatever remains — no length filter here, short finals like
                // "Ok!" or "Non." are valid and must be spoken.
                let remaining = sentence_buf.trim().to_string();
                if !remaining.is_empty() && is_speakable(&remaining) {
                    app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
                }
                app.emit("claude-done", ()).map_err(|e| e.to_string())?;
                eprintln!("[jarvis] ask_claude: message_stop — spawn classify_and_stage");
                tokio::spawn(classify_and_stage(user_text.clone(), api_key.clone(), app.clone()));
                return Ok(());
            }
        }
    }

    // Fallback flush if stream ended without message_stop
    let remaining = sentence_buf.trim().to_string();
    if !remaining.is_empty() && is_speakable(&remaining) {
        app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
    }
    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    eprintln!("[jarvis] ask_claude: fallback flush — spawn classify_and_stage");
    tokio::spawn(classify_and_stage(user_text, api_key, app));
    Ok(())
}
