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
DISTINCTION CRITIQUE — TACHE vs CAPTURE_IDEE :\n\
TACHE = action concrète et immédiate avec un verbe d'action (acheter, appeler, envoyer, faire, vérifier, prendre rdv).\n\
  → \"acheter des piles\" → TACHE\n\
  → \"appeler le médecin\" → TACHE\n\
  → \"faire les courses\" → TACHE\n\
  → \"envoyer le mail à Paul\" → TACHE\n\
CAPTURE_IDEE = concept créatif, idée de projet, aspiration, envie floue sans verbe d'action immédiat.\n\
  → \"faire un podcast\" → CAPTURE_IDEE (aspiration, pas une to-do)\n\
  → \"créer une app de méditation\" → CAPTURE_IDEE\n\
  → \"apprendre le piano\" → CAPTURE_IDEE\n\
  → \"voyager au Japon\" → CAPTURE_IDEE\n\
Si le message dit explicitement \"note que je veux faire X\" ou \"j'ai envie de X\" sans deadline → CAPTURE_IDEE.\n\
Si le message dit \"pense à X\", \"faut que je X\", \"rappelle-moi de X\" → TACHE.\n\
\n\
Autres intentions :\n\
CAPTURE_PROJET = projet structuré avec plusieurs étapes (\"lancer une startup\", \"écrire un livre\").\n\
CAPTURE_CONCEPT = idée intellectuelle, notion, théorie (\"le paradoxe de Fermi\", \"le stoïcisme\").\n\
CAPTURE_PERSO = information personnelle sur l'utilisateur (\"je suis gaucher\", \"j'ai 28 ans\", \"j'aime le café\").\n\
\n\
Règles pour content :\n\
- content = nom brut, SANS préfixe. JAMAIS \"Note :\", \"Idée :\", \"Tâche :\" ou tout autre label.\n\
- Correct : \"acheter des piles\"  Incorrect : \"Tâche : acheter des piles\"\n\
- Correct : \"faire un podcast\"   Incorrect : \"Idée : faire un podcast\"\n\
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

// ── Shared staging logic (used by both Claude and Gemini paths) ───────────────
async fn execute_staging(
    items: Vec<(String, String)>,
    companion_url: &str,
    app: &AppHandle,
) {
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
        eprintln!("[jarvis] classify: intent CONVERSATION, rien à stager");
        return;
    }

    if !deletes.is_empty() {
        let mut n_ok = 0usize;
        let mut last_deleted = String::new();
        for (_, query) in &deletes {
            eprintln!("[jarvis] classify: DELETE_STAGING query={query:?}");
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

    if !captures.is_empty() {
        let toast = if captures.len() == 1 {
            if captures[0].0 == "TACHE" { "📋 tâche".to_string() } else { "💡 noté".to_string() }
        } else {
            format!("💡 {} captures notées", captures.len())
        };
        let _ = app.emit("claude-capture", toast);

        for (intent, content) in &captures {
            let (endpoint, payload) = {
                // All capture types (including TACHE) go to /stage so they appear in the
                // FloatingCards UI. confirm_staging_item routes TACHE → /task on user confirm.
                ("/stage", serde_json::json!({"content": content, "hint": intent}))
            };

            let http_result = http_client()
                .post(format!("{companion_url}{endpoint}"))
                .json(&payload)
                .send()
                .await;

            match http_result {
                Ok(r) if r.status().is_success() => {}
                Ok(r) => {
                    eprintln!("[jarvis] classify: companion erreur HTTP {} — fallback", r.status());
                    fallback_stage(content, intent);
                }
                Err(e) => {
                    eprintln!("[jarvis] classify: companion down ({e}) — fallback [{intent}]");
                    fallback_stage(content, intent);
                }
            }
        }
    }
}

// ── Haiku classification (LLM_PROVIDER=claude) ────────────────────────────────
async fn classify_and_stage(text: String, api_key: String, app: AppHandle) {
    eprintln!("[jarvis] classify_and_stage(haiku): text={:?}", text.chars().take(60).collect::<String>());
    if text.is_empty() { return; }

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
        Err(e) => { eprintln!("[jarvis] classify(haiku): request failed: {e}"); return; }
    };

    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify(haiku): parse failed: {e}"); return; }
    };

    let raw = match json
        .get("content").and_then(|c| c.get(0))
        .and_then(|b| b.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] classify(haiku): unexpected response shape"); return; }
    };

    let items = parse_classify_response(&raw, &text);
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    execute_staging(items, &companion_url, &app).await;
}

// ── Gemini Flash classification (LLM_PROVIDER=gemini) ────────────────────────
async fn classify_and_stage_gemini(text: String, api_key: String, app: AppHandle) {
    eprintln!("[jarvis] classify_and_stage(gemini): text={:?}", text.chars().take(60).collect::<String>());
    if text.is_empty() { return; }

    let body = serde_json::json!({
        "system_instruction": {
            "parts": [{"text": CLASSIFY_SYSTEM}]
        },
        "contents": [{"role": "user", "parts": [{"text": &text}]}],
        "generationConfig": {"maxOutputTokens": 400}
    });

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={}",
        api_key
    );

    let resp = match http_client()
        .post(&url)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r)  => r,
        Err(e) => { eprintln!("[jarvis] classify(gemini): request failed: {e}"); return; }
    };

    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] classify(gemini): parse failed: {e}"); return; }
    };

    let raw = match json
        .get("candidates").and_then(|c| c.get(0))
        .and_then(|c| c.get("content"))
        .and_then(|c| c.get("parts")).and_then(|p| p.get(0))
        .and_then(|p| p.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] classify(gemini): unexpected response shape: {json:?}"); return; }
    };

    let items = parse_classify_response(&raw, &text);
    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    execute_staging(items, &companion_url, &app).await;
}

// ── Parse classification JSON (shared) ───────────────────────────────────────
fn parse_classify_response(raw: &str, fallback_text: &str) -> Vec<(String, String)> {
    let cleaned = raw
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();

    let classified: serde_json::Value = match serde_json::from_str(cleaned) {
        Ok(j)  => j,
        Err(e) => {
            eprintln!("[jarvis] classify: JSON parse failed — raw={raw:?} err={e}");
            return vec![];
        }
    };

    if classified.is_array() {
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
                          .unwrap_or(fallback_text).to_string();
        vec![(intent, content)]
    }
}

// ── RAG injection (shared) ────────────────────────────────────────────────────
async fn fetch_rag_block(user_text: &str, companion_url: &str) -> String {
    match http_client()
        .post(format!("{}/rag_search", companion_url))
        .json(&serde_json::json!({"query": user_text}))
        .timeout(std::time::Duration::from_millis(500))
        .send()
        .await
    {
        Ok(resp) => match resp.json::<serde_json::Value>().await {
            Ok(json) => json
                .get("result")
                .and_then(|r| r.as_str())
                .filter(|s| !s.is_empty())
                .map(|s| format!("\n\n<MEMORY_CONTEXT>\n{}\n</MEMORY_CONTEXT>", s))
                .unwrap_or_default(),
            Err(_) => String::new(),
        },
        Err(_) => String::new(),
    }
}

// ── Memory extraction (shared) ────────────────────────────────────────────────

const MEMORY_EXTRACT_PROMPT: &str = "\
Analyse cet échange. Extrais les faits nouveaux durables méritant mémorisation long terme.\n\
Ignore : small talk, questions banales, reformulations génériques, réponses courtes sans contenu.\n\
Si rien de mémorable, retourne [].\n\
Format JSON uniquement : [{\"content\": \"fait concis\", \"section\": \"memory\"}]\n\
section = \"user\" pour préférences/infos personnelles sur l'utilisateur.\n\
section = \"memory\" pour projets, décisions, idées importantes, concepts.\n\n";

async fn stage_memory_items(raw: &str, companion_url: &str) {
    let cleaned = raw.trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();

    let items = match serde_json::from_str::<serde_json::Value>(cleaned) {
        Ok(serde_json::Value::Array(arr)) => arr,
        _ => { eprintln!("[jarvis] extract_memory: JSON invalide — raw={raw:?}"); return; }
    };

    if items.is_empty() {
        eprintln!("[jarvis] extract_memory: rien à mémoriser");
        return;
    }

    for item in &items {
        let content = item.get("content").and_then(|v| v.as_str()).unwrap_or("").trim();
        let section = item.get("section").and_then(|v| v.as_str()).unwrap_or("memory");
        if content.is_empty() { continue; }
        eprintln!("[jarvis] extract_memory: stage [{section}] {content:?}");
        let _ = http_client()
            .post(format!("{companion_url}/stage"))
            .json(&serde_json::json!({"content": content, "hint": "MEMORY", "section": section}))
            .send()
            .await;
    }
}

async fn extract_and_stage_memory_claude(
    user_text: String,
    assistant_text: String,
    companion_url: String,
    api_key: String,
) {
    if assistant_text.trim().len() < 30 { return; }

    let prompt = format!(
        "{}USER: {}\n\nASSISTANT: {}",
        MEMORY_EXTRACT_PROMPT, user_text, assistant_text
    );
    let body = serde_json::json!({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "messages":   [{"role": "user", "content": prompt}],
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
        Err(e) => { eprintln!("[jarvis] extract_memory(claude): {e}"); return; }
    };
    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] extract_memory(claude): parse failed: {e}"); return; }
    };
    let raw = match json.get("content").and_then(|c| c.get(0))
        .and_then(|b| b.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] extract_memory(claude): unexpected shape"); return; }
    };
    stage_memory_items(&raw, &companion_url).await;
}

async fn extract_and_stage_memory_gemini(
    user_text: String,
    assistant_text: String,
    companion_url: String,
    api_key: String,
) {
    if assistant_text.trim().len() < 30 { return; }

    let prompt = format!(
        "{}USER: {}\n\nASSISTANT: {}",
        MEMORY_EXTRACT_PROMPT, user_text, assistant_text
    );
    let body = serde_json::json!({
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 300}
    });
    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={}",
        api_key
    );
    let resp = match http_client()
        .post(&url)
        .header("content-type", "application/json")
        .json(&body)
        .send()
        .await
    {
        Ok(r)  => r,
        Err(e) => { eprintln!("[jarvis] extract_memory(gemini): {e}"); return; }
    };
    let json: serde_json::Value = match resp.json().await {
        Ok(j)  => j,
        Err(e) => { eprintln!("[jarvis] extract_memory(gemini): parse failed: {e}"); return; }
    };
    let raw = match json.get("candidates").and_then(|c| c.get(0))
        .and_then(|c| c.get("content"))
        .and_then(|c| c.get("parts")).and_then(|p| p.get(0))
        .and_then(|p| p.get("text")).and_then(|t| t.as_str())
    {
        Some(s) => s.to_string(),
        None    => { eprintln!("[jarvis] extract_memory(gemini): unexpected shape: {json:?}"); return; }
    };
    stage_memory_items(&raw, &companion_url).await;
}

// ── Claude Sonnet streaming ───────────────────────────────────────────────────
async fn ask_claude_stream(
    app: AppHandle,
    messages: Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("ANTHROPIC_API_KEY")
        .map_err(|_| "ANTHROPIC_API_KEY non défini".to_string())?;

    let user_text = messages.last().map(|m| m.content.clone()).unwrap_or_default();

    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    let rag_block = fetch_rag_block(&user_text, &companion_url).await;

    let vocal_system = format!("{}{}{}", system_prompt, rag_block, VOCAL_INSTRUCTION);
    eprintln!("[timing] system_prompt_len: {} chars (rag: {} chars)", vocal_system.len(), rag_block.len());

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

    let t1 = std::time::Instant::now();

    let response = http_client()
        .post("https://api.anthropic.com/v1/messages")
        .header("x-api-key",          &api_key)
        .header("anthropic-version",   "2023-06-01")
        .header("content-type",        "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    eprintln!("[timing] ask_claude: HTTP response headers: {}ms", t1.elapsed().as_millis());

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Erreur API Anthropic : {}", err));
    }

    let mut stream = response.bytes_stream();
    let mut sentence_buf   = String::new();
    let mut full_assistant = String::new();
    let mut first_sentence = true;

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        let text  = String::from_utf8_lossy(&chunk);

        for line in text.lines() {
            let Some(data) = line.strip_prefix("data: ") else { continue };
            if data == "[DONE]" { break; }
            let Ok(json) = serde_json::from_str::<serde_json::Value>(data) else { continue };

            if json.get("type").and_then(|t| t.as_str()) == Some("content_block_delta") {
                if let Some(token) = json
                    .get("delta")
                    .and_then(|d| d.get("text"))
                    .and_then(|t| t.as_str())
                {
                    app.emit("claude-token", token).map_err(|e| e.to_string())?;
                    sentence_buf.push_str(token);
                    full_assistant.push_str(token);

                    while let Some(boundary) = find_sentence_end(&sentence_buf) {
                        let sentence = sentence_buf[..boundary].trim().to_string();
                        sentence_buf = sentence_buf[boundary..].trim_start().to_string();
                        if sentence.len() > 3 && is_speakable(&sentence) {
                            if first_sentence {
                                eprintln!("[timing] claude-ttft: {}ms", t1.elapsed().as_millis());
                                first_sentence = false;
                            }
                            app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
                        }
                    }
                }
            }

            if json.get("type").and_then(|t| t.as_str()) == Some("message_stop") {
                let remaining = sentence_buf.trim().to_string();
                if !remaining.is_empty() && is_speakable(&remaining) {
                    app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
                }
                app.emit("claude-done", ()).map_err(|e| e.to_string())?;
                eprintln!("[jarvis] ask_claude: message_stop — spawn classify + extract_memory");
                tokio::spawn(classify_and_stage(user_text.clone(), api_key.clone(), app.clone()));
                tokio::spawn(extract_and_stage_memory_claude(
                    user_text.clone(), full_assistant.clone(), companion_url.clone(), api_key.clone(),
                ));
                return Ok(());
            }
        }
    }

    let remaining = sentence_buf.trim().to_string();
    if !remaining.is_empty() && is_speakable(&remaining) {
        if first_sentence {
            eprintln!("[timing] claude-ttft: {}ms", t1.elapsed().as_millis());
        }
        app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
    }
    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    tokio::spawn(classify_and_stage(user_text.clone(), api_key.clone(), app.clone()));
    tokio::spawn(extract_and_stage_memory_claude(user_text, full_assistant, companion_url, api_key));
    Ok(())
}

// ── Gemini Flash streaming ────────────────────────────────────────────────────
async fn ask_gemini_stream(
    app: AppHandle,
    messages: Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let api_key = std::env::var("GEMINI_API_KEY")
        .map_err(|_| "GEMINI_API_KEY non défini".to_string())?;

    let user_text = messages.last().map(|m| m.content.clone()).unwrap_or_default();

    let companion_url = std::env::var("COMPANION_URL")
        .unwrap_or_else(|_| "http://localhost:8765".to_string());
    let rag_block = fetch_rag_block(&user_text, &companion_url).await;

    let full_system = format!("{}{}{}", system_prompt, rag_block, VOCAL_INSTRUCTION);
    eprintln!("[timing] system_prompt_len: {} chars (rag: {} chars)", full_system.len(), rag_block.len());

    // Gemini uses "model" instead of "assistant"
    let contents: Vec<serde_json::Value> = messages.iter().map(|m| {
        let role = if m.role == "assistant" { "model" } else { "user" };
        serde_json::json!({
            "role": role,
            "parts": [{"text": m.content}]
        })
    }).collect();

    let body = serde_json::json!({
        "system_instruction": {
            "parts": [{"text": full_system}]
        },
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 256}
    });

    let url = format!(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?alt=sse&key={}",
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

    eprintln!("[timing] ask_gemini: HTTP response headers: {}ms", t1.elapsed().as_millis());

    if !response.status().is_success() {
        let err = response.text().await.unwrap_or_default();
        return Err(format!("Erreur API Gemini : {}", err));
    }

    let mut stream = response.bytes_stream();
    let mut sentence_buf   = String::new();
    let mut full_assistant = String::new();
    let mut first_sentence = true;

    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        let text = String::from_utf8_lossy(&chunk);

        for line in text.lines() {
            let Some(data) = line.strip_prefix("data: ") else { continue };
            let Ok(json) = serde_json::from_str::<serde_json::Value>(data) else { continue };

            if let Some(token) = json
                .get("candidates").and_then(|c| c.get(0))
                .and_then(|c| c.get("content"))
                .and_then(|c| c.get("parts")).and_then(|p| p.get(0))
                .and_then(|p| p.get("text")).and_then(|t| t.as_str())
            {
                app.emit("claude-token", token).map_err(|e| e.to_string())?;
                sentence_buf.push_str(token);
                full_assistant.push_str(token);

                while let Some(boundary) = find_sentence_end(&sentence_buf) {
                    let sentence = sentence_buf[..boundary].trim().to_string();
                    sentence_buf = sentence_buf[boundary..].trim_start().to_string();
                    if sentence.len() > 3 && is_speakable(&sentence) {
                        if first_sentence {
                            eprintln!("[timing] gemini-ttft: {}ms", t1.elapsed().as_millis());
                            first_sentence = false;
                        }
                        app.emit("claude-sentence", sentence).map_err(|e| e.to_string())?;
                    }
                }
            }
        }
    }

    // Flush remaining buffer (Gemini stream closes naturally at finishReason=STOP)
    let remaining = sentence_buf.trim().to_string();
    if !remaining.is_empty() && is_speakable(&remaining) {
        if first_sentence {
            eprintln!("[timing] gemini-ttft: {}ms", t1.elapsed().as_millis());
        }
        app.emit("claude-sentence", remaining).map_err(|e| e.to_string())?;
    }
    app.emit("claude-done", ()).map_err(|e| e.to_string())?;
    eprintln!("[jarvis] ask_gemini: done — spawn classify + extract_memory");
    tokio::spawn(classify_and_stage_gemini(user_text.clone(), api_key.clone(), app.clone()));
    tokio::spawn(extract_and_stage_memory_gemini(user_text, full_assistant, companion_url, api_key));
    Ok(())
}

// ── Public Tauri command — routes on LLM_PROVIDER ────────────────────────────
#[tauri::command]
pub async fn ask_claude(
    app:           AppHandle,
    messages:      Vec<ChatMessage>,
    system_prompt: String,
) -> Result<(), String> {
    let provider = std::env::var("LLM_PROVIDER").unwrap_or_else(|_| "claude".to_string());
    eprintln!("[jarvis] ask_claude: LLM_PROVIDER={provider}");

    match provider.to_lowercase().as_str() {
        "gemini" => ask_gemini_stream(app, messages, system_prompt).await,
        _        => ask_claude_stream(app, messages, system_prompt).await,
    }
}
